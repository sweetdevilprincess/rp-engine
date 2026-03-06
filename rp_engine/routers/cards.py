"""Story card CRUD endpoints."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from rp_engine.database import Database
from rp_engine.dependencies import (
    get_card_indexer,
    get_db,
    get_llm_client,
    get_vault_root,
)
from rp_engine.models.frontmatter import FRONTMATTER_MODELS, validate_frontmatter
from rp_engine.models.story_card import (
    AuditCardsRequest,
    AuditCardsResponse,
    AuditGap,
    CardListResponse,
    EntityConnection,
    GapEvidenceResponse,
    GapExchangeRecord,
    ReindexResponse,
    SceneEvidence,
    StoryCardCreate,
    StoryCardDetail,
    StoryCardSummary,
    StoryCardUpdate,
    SuggestCardRequest,
    SuggestCardResponse,
)
from rp_engine.services.card_indexer import CARD_TYPE_DIRS, CardIndexer
from rp_engine.services.llm_client import LLMClient
from rp_engine.utils.frontmatter import serialize_frontmatter
from rp_engine.utils.normalization import generate_card_id, normalize_key
from rp_engine.utils.scene_detection import group_into_scenes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cards", tags=["cards"])


def _normalize_url_name(name: str) -> str:
    """Normalize a URL path name — convert hyphens to spaces, then normalize."""
    return normalize_key(name.replace("-", " "))


@router.get("", response_model=CardListResponse)
async def list_cards(
    card_type: str | None = Query(None),
    rp_folder: str | None = Query(None),
    db: Database = Depends(get_db),
):
    """List all story cards, optionally filtered by type and RP folder."""
    conditions = []
    params: list = []

    if card_type:
        conditions.append("card_type = ?")
        params.append(card_type)
    if rp_folder:
        conditions.append("rp_folder = ?")
        params.append(rp_folder)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await db.fetch_all(
        f"SELECT id, rp_folder, file_path, card_type, name, importance, summary FROM story_cards{where}",
        params,
    )

    # Batch-fetch connection counts for all returned cards
    if rows:
        id_list = [row["id"] for row in rows]
        placeholders = ",".join("?" * len(id_list))
        count_rows = await db.fetch_all(
            f"SELECT from_entity, COUNT(*) as cnt FROM entity_connections WHERE from_entity IN ({placeholders}) GROUP BY from_entity",
            id_list,
        )
        connection_counts = {r["from_entity"]: r["cnt"] for r in count_rows}
    else:
        connection_counts = {}

    # Batch-fetch aliases for all cards (fixes N+1)
    if rows:
        alias_rows = await db.fetch_all(
            f"SELECT entity_id, alias FROM entity_aliases WHERE entity_id IN ({placeholders})",
            id_list,
        )
        alias_map: dict[str, list[str]] = {}
        for ar in alias_rows:
            alias_map.setdefault(ar["entity_id"], []).append(ar["alias"])

        # Batch-fetch frontmatter for tags (single query instead of N)
        fm_rows = await db.fetch_all(
            f"SELECT id, frontmatter FROM story_cards WHERE id IN ({placeholders})",
            id_list,
        )
        tags_map: dict[str, list[str]] = {}
        for fr in fm_rows:
            tags = []
            if fr["frontmatter"]:
                try:
                    fm = json.loads(fr["frontmatter"])
                    tags = fm.get("tags", [])
                except (json.JSONDecodeError, TypeError):
                    pass
            tags_map[fr["id"]] = tags if isinstance(tags, list) else []
    else:
        alias_map = {}
        tags_map = {}

    cards = [
        StoryCardSummary(
            name=row["name"],
            card_type=row["card_type"],
            importance=row["importance"],
            file_path=row["file_path"],
            summary=row["summary"],
            aliases=alias_map.get(row["id"], []),
            tags=tags_map.get(row["id"], []),
            connection_count=connection_counts.get(row["id"], 0),
        )
        for row in rows
    ]

    return CardListResponse(cards=cards, total=len(cards))


@router.get("/connections")
async def get_connections(
    rp_folder: str = Query(...),
    db: Database = Depends(get_db),
):
    """Return graph data (nodes + edges) for all cards in an RP.

    Used by the Dashboard entity graph. Queries entity_connections and
    maps entity IDs back to card names.
    """
    card_rows = await db.fetch_all(
        "SELECT id, name, card_type, importance FROM story_cards WHERE rp_folder = ?",
        [rp_folder],
    )
    if not card_rows:
        return {"nodes": [], "edges": []}

    id_to_card = {row["id"]: row for row in card_rows}

    conn_rows = await db.fetch_all(
        """SELECT ec.from_entity, ec.to_entity, ec.connection_type
           FROM entity_connections ec
           JOIN story_cards sc ON ec.from_entity = sc.id
           WHERE sc.rp_folder = ?""",
        [rp_folder],
    )

    nodes = [
        {
            "name": row["name"],
            "card_type": row["card_type"],
            "importance": row["importance"],
        }
        for row in card_rows
    ]

    edges = []
    for conn in conn_rows:
        from_card = id_to_card.get(conn["from_entity"])
        to_card = id_to_card.get(conn["to_entity"])
        if from_card and to_card:
            edges.append({
                "from": from_card["name"],
                "to": to_card["name"],
                "connection_type": conn["connection_type"],
            })

    return {"nodes": nodes, "edges": edges}


# IMPORTANT: /reindex must be defined BEFORE /{card_type} to avoid route shadowing
@router.post("/reindex", response_model=ReindexResponse)
async def reindex_all(
    rp_folder: str | None = Query(None),
    indexer: CardIndexer = Depends(get_card_indexer),
):
    """Force a full reindex of all story cards."""
    if rp_folder:
        result = await indexer.full_index(rp_folder)
    else:
        folders = indexer.get_all_rp_folders()
        totals = {"entities": 0, "connections": 0, "aliases": 0, "keywords": 0, "duration_ms": 0.0}
        for folder in folders:
            r = await indexer.full_index(folder)
            for k in ("entities", "connections", "aliases", "keywords"):
                totals[k] += r[k]
            totals["duration_ms"] += r.get("duration_ms", 0)
        result = totals

    return ReindexResponse(**result)


@router.post("/suggest", response_model=SuggestCardResponse)
async def suggest_card(
    body: SuggestCardRequest,
    db: Database = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
    vault_root: Path = Depends(get_vault_root),
):
    """Generate a draft story card for an entity by searching exchanges and using LLM."""
    entity_name = body.entity_name
    card_type = body.card_type
    rp_folder = body.rp_folder
    additional_context = body.additional_context

    branch = body.branch

    # Try scene-aware evidence first (from card_gap_exchanges)
    gap_rows = await db.fetch_all(
        """SELECT exchange_number, chunk_text, mention_type
           FROM card_gap_exchanges
           WHERE LOWER(entity_name) = LOWER(?) AND rp_folder = ?
             AND branch = ?
           ORDER BY exchange_number""",
        [entity_name, rp_folder, branch],
    )

    if gap_rows:
        # Scene-aware path: group gap exchanges into scenes
        exchange_nums = [r["exchange_number"] for r in gap_rows]
        scenes = group_into_scenes(exchange_nums)
        chunks_by_num = {r["exchange_number"]: r for r in gap_rows}

        evidence_parts = []
        for i, scene in enumerate(scenes, 1):
            scene_chunks = []
            for num in scene.exchanges:
                row = chunks_by_num.get(num)
                if row and row["chunk_text"]:
                    label = "PRIMARY" if row["mention_type"] == "primary" else "peripheral"
                    scene_chunks.append(f"[Exchange {num}, {label}]\n{row['chunk_text']}")
            if scene_chunks:
                evidence_parts.append(
                    f"## Scene {i} (Exchanges {scene.start}-{scene.end})\n"
                    + "\n---\n".join(scene_chunks)
                )

        evidence = "\n\n".join(evidence_parts)
        primary_count = sum(1 for r in gap_rows if r["mention_type"] == "primary")
        evidence += (
            f"\n\nEntity mentioned in {len(gap_rows)} exchanges total, "
            f"{primary_count} as primary focus."
        )
    else:
        # Fallback: search exchanges directly (pre-existing gaps or no gap tracking)
        rows = await db.fetch_all(
            """SELECT exchange_number, user_message, assistant_response
               FROM exchanges
               WHERE rp_folder = ? AND (
                   LOWER(user_message) LIKE ? OR LOWER(assistant_response) LIKE ?
               )
               ORDER BY exchange_number DESC LIMIT 10""",
            [rp_folder, f"%{entity_name.lower()}%", f"%{entity_name.lower()}%"],
        )
        evidence = "\n---\n".join(
            f"Exchange {r['exchange_number']}:\n{r['assistant_response'][:500]}"
            for r in rows
        )

    # Load template
    template_map = {
        "character": "Character Template.md",
        "npc": "NPC Template.md",
        "location": "Location Template.md",
        "secret": "Secret Template.md",
        "memory": "Memory Template.md",
        "knowledge": "Knowledge Template.md",
        "lore": "Lore Template.md",
        "organization": "Organization Template.md",
        "plot_thread": "Plot Thread Template.md",
        "plot_arc": "Plot Arc Template.md",
        "item": "Item Template.md",
        "chapter_summary": "Chapter Template.md",
    }
    template_name = template_map.get(card_type, "NPC Template.md")
    template_path = vault_root / "z_templates" / "Story Cards" / template_name
    template = ""
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")

    prompt = f"""Create a story card for the entity "{entity_name}" (type: {card_type}).

Use this template structure:
{template}

Based on these narrative scenes where the entity appears:
{evidence}

{f"Additional context: {additional_context}" if additional_context else ""}

Return ONLY the complete markdown card with frontmatter and content."""

    response = await llm.generate(
        messages=[{"role": "user", "content": prompt}],
        model=llm.models.card_generation,
        temperature=0.4,
        max_tokens=3000,
    )

    return SuggestCardResponse(
        entity_name=entity_name,
        card_type=card_type,
        markdown=response.content,
        model_used=response.model,
    )


@router.get("/gaps/{entity_name}/evidence", response_model=GapEvidenceResponse)
async def get_gap_evidence(
    entity_name: str,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    db: Database = Depends(get_db),
):
    """Return scene-grouped evidence for a card gap entity."""
    rows = await db.fetch_all(
        """SELECT exchange_number, chunk_text, mention_type
           FROM card_gap_exchanges
           WHERE LOWER(entity_name) = LOWER(?) AND rp_folder = ? AND branch = ?
           ORDER BY exchange_number""",
        [entity_name, rp_folder, branch],
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No gap evidence found for '{entity_name}' in '{rp_folder}'",
        )

    exchange_nums = [r["exchange_number"] for r in rows]
    scenes = group_into_scenes(exchange_nums)
    chunks_by_num = {r["exchange_number"]: r for r in rows}

    scene_list = []
    for scene in scenes:
        records = []
        for num in scene.exchanges:
            row = chunks_by_num.get(num)
            if row:
                records.append(GapExchangeRecord(
                    exchange_number=num,
                    chunk_text=row["chunk_text"],
                    mention_type=row["mention_type"],
                ))
        scene_list.append(SceneEvidence(
            start=scene.start,
            end=scene.end,
            exchange_count=scene.size,
            exchanges=records,
        ))

    return GapEvidenceResponse(
        entity_name=entity_name,
        rp_folder=rp_folder,
        total_mentions=len(rows),
        primary_mentions=sum(1 for r in rows if r["mention_type"] == "primary"),
        scenes=scene_list,
    )


@router.post("/audit", response_model=AuditCardsResponse)
async def audit_cards(
    body: AuditCardsRequest,
    db: Database = Depends(get_db),
):
    """Audit exchanges for entity mentions missing story cards.

    Quick mode: regex proper noun extraction + cross-reference vs story_cards.
    """
    import re

    rp_folder = body.rp_folder
    mode = body.mode
    session_id = body.session_id

    # Load exchanges
    if session_id:
        rows = await db.fetch_all(
            "SELECT id, assistant_response FROM exchanges WHERE rp_folder = ? AND session_id = ?",
            [rp_folder, session_id],
        )
    else:
        rows = await db.fetch_all(
            "SELECT id, assistant_response FROM exchanges WHERE rp_folder = ? ORDER BY id DESC LIMIT 50",
            [rp_folder],
        )

    # Load known entity names
    card_rows = await db.fetch_all(
        "SELECT LOWER(name) as name FROM story_cards WHERE rp_folder = ?",
        [rp_folder],
    )
    known_names = {r["name"] for r in card_rows}

    # Extract proper nouns (Title Case words that aren't common words)
    common_words = {
        "the", "and", "but", "for", "not", "you", "all", "can", "her", "was",
        "one", "our", "out", "his", "has", "its", "let", "say", "she", "too",
        "use", "him", "how", "man", "new", "now", "old", "see", "way",
        "who", "did", "get", "may", "any", "day",
    }

    entity_mentions: dict[str, list[int]] = {}
    proper_noun_re = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")

    for row in rows:
        text = row["assistant_response"]
        matches = proper_noun_re.findall(text)
        for match in matches:
            name_lower = match.lower()
            if name_lower in known_names:
                continue
            if name_lower in common_words:
                continue
            if len(match) < 3:
                continue
            entity_mentions.setdefault(match, [])
            if row["id"] not in entity_mentions[match]:
                entity_mentions[match].append(row["id"])

    gaps = [
        AuditGap(
            entity_name=name,
            mention_count=len(exchanges),
            exchanges=exchanges[:5],
        )
        for name, exchanges in sorted(
            entity_mentions.items(), key=lambda x: len(x[1]), reverse=True
        )
        if len(exchanges) >= 2  # Only report entities mentioned multiple times
    ]

    return AuditCardsResponse(
        mode=mode,
        gaps=gaps,
        total_exchanges_scanned=len(rows),
        total_gaps=len(gaps),
    )


class CardValidateRequest(BaseModel):
    card_type: str
    frontmatter: dict[str, Any]


# IMPORTANT: /schema and /validate must be defined BEFORE /{card_type} to avoid route shadowing
@router.get("/schema/{card_type}")
async def get_schema(card_type: str):
    """Return JSON schema for a card type's frontmatter."""
    model = FRONTMATTER_MODELS.get(card_type)
    if not model:
        raise HTTPException(400, detail=f"Unknown card type: {card_type}")
    return model.model_json_schema()


@router.post("/validate")
async def validate_card(body: CardValidateRequest):
    """Validate card frontmatter against schema."""
    valid, errors, warnings = validate_frontmatter(body.card_type, body.frontmatter)
    return {"valid": valid, "errors": errors, "warnings": warnings}


@router.get("/{card_type}/{name}", response_model=StoryCardDetail)
async def get_card(
    card_type: str,
    name: str,
    db: Database = Depends(get_db),
):
    """Get a single card with its frontmatter, content, and connections."""
    normalized = _normalize_url_name(name)

    # Try direct lookup by type + normalized name
    row = await db.fetch_one(
        "SELECT * FROM story_cards WHERE card_type = ? AND LOWER(name) = ?",
        [card_type, normalized],
    )

    # Fallback: search by alias (try both normalized forms)
    if not row:
        for alias_key in (normalized, normalize_key(name)):
            row = await db.fetch_one(
                """SELECT sc.* FROM story_cards sc
                   JOIN entity_aliases ea ON sc.id = ea.entity_id
                   WHERE sc.card_type = ? AND ea.alias = ?""",
                [card_type, alias_key],
            )
            if row:
                break

    if not row:
        raise HTTPException(404, detail=f"Card not found: {card_type}/{name}")

    frontmatter = {}
    if row["frontmatter"]:
        try:
            frontmatter = json.loads(row["frontmatter"])
        except (json.JSONDecodeError, TypeError):
            pass

    conn_rows = await db.fetch_all(
        "SELECT to_entity, connection_type, field, role FROM entity_connections WHERE from_entity = ?",
        [row["id"]],
    )
    connections = [
        EntityConnection(
            to_entity=c["to_entity"],
            connection_type=c["connection_type"],
            field=c["field"],
            role=c["role"],
        )
        for c in conn_rows
    ]

    return StoryCardDetail(
        name=row["name"],
        card_type=row["card_type"],
        file_path=row["file_path"],
        importance=row["importance"],
        frontmatter=frontmatter,
        content=row["content"] or "",
        connections=connections,
    )


@router.post("/{card_type}", response_model=StoryCardDetail, status_code=201)
async def create_card(
    card_type: str,
    body: StoryCardCreate,
    rp_folder: str = Query(...),
    db: Database = Depends(get_db),
    indexer: CardIndexer = Depends(get_card_indexer),
    vault_root: Path = Depends(get_vault_root),
):
    """Create a new story card. Writes .md file and indexes it."""
    if card_type not in CARD_TYPE_DIRS:
        raise HTTPException(400, detail=f"Unknown card type: {card_type}")

    # Auto-generate card_id if not provided
    card_id = body.frontmatter.get("card_id")
    if not card_id:
        card_id = generate_card_id(card_type, body.name)

    dir_name = CARD_TYPE_DIRS[card_type]
    card_dir = vault_root / rp_folder / "Story Cards" / dir_name
    card_dir.mkdir(parents=True, exist_ok=True)

    # Use card_id as filename
    file_path = card_dir / f"{card_id}.md"
    if file_path.exists():
        raise HTTPException(409, detail=f"Card already exists: {card_id}")

    frontmatter = {"type": card_type, "card_id": card_id, "name": body.name, **body.frontmatter}
    frontmatter["card_id"] = card_id  # ensure card_id wins over any provided value

    # Validate frontmatter (warn but don't block)
    valid, errors, _warnings = validate_frontmatter(card_type, frontmatter)
    if not valid:
        logger.warning("Frontmatter validation errors for %s: %s", card_id, errors)

    content = serialize_frontmatter(frontmatter, body.content)
    file_path.write_text(content, encoding="utf-8")

    await indexer.index_file(rp_folder, file_path)

    return await get_card(card_type, body.name, db)


@router.put("/{card_type}/{name}", response_model=StoryCardDetail)
async def update_card(
    card_type: str,
    name: str,
    body: StoryCardUpdate,
    db: Database = Depends(get_db),
    indexer: CardIndexer = Depends(get_card_indexer),
    vault_root: Path = Depends(get_vault_root),
):
    """Update an existing card. Writes .md file and reindexes."""
    normalized = _normalize_url_name(name)
    row = await db.fetch_one(
        "SELECT * FROM story_cards WHERE card_type = ? AND LOWER(name) = ?",
        [card_type, normalized],
    )
    if not row:
        raise HTTPException(404, detail=f"Card not found: {card_type}/{name}")

    file_path = vault_root / row["file_path"]
    if not file_path.exists():
        raise HTTPException(404, detail=f"Card file missing: {row['file_path']}")

    current_fm = {}
    if row["frontmatter"]:
        try:
            current_fm = json.loads(row["frontmatter"])
        except (json.JSONDecodeError, TypeError):
            pass

    if body.frontmatter is not None:
        current_fm.update(body.frontmatter)

    from rp_engine.utils.frontmatter import parse_frontmatter
    _, current_body = parse_frontmatter(row["content"] or "")
    new_body = body.content if body.content is not None else current_body

    content = serialize_frontmatter(current_fm, new_body)
    file_path.write_text(content, encoding="utf-8")

    rp_folder = row["rp_folder"]
    await indexer.index_file(rp_folder, file_path)

    return await get_card(card_type, row["name"], db)
