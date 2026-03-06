"""RP management endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from rp_engine.database import Database
from rp_engine.dependencies import get_card_indexer, get_db, get_vault_root
from rp_engine.models.rp import RPCreate, RPInfo, RPResponse
from rp_engine.services.card_indexer import CARD_TYPE_DIRS, CardIndexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rp", tags=["rp"])

# Directories to scaffold under Story Cards/
SCAFFOLD_DIRS = list(CARD_TYPE_DIRS.values())

GUIDELINES_TEMPLATE = """---
pov_mode: {pov_mode}
pov_character: ""
dual_characters: {dual_characters}
integrate_user_narrative: true
preserve_user_details: true
narrative_voice: first
tense: present
tone: {tone}
scene_pacing: {scene_pacing}
---
"""


@router.post("", response_model=RPResponse, status_code=201)
async def create_rp(
    body: RPCreate,
    vault_root: Path = Depends(get_vault_root),
):
    """Create a new RP with scaffolded folder structure."""
    rp_dir = vault_root / body.rp_name
    if rp_dir.exists():
        raise HTTPException(409, detail=f"RP folder already exists: {body.rp_name}")

    created_files: list[str] = []

    # Create Story Cards subdirectories
    for dir_name in SCAFFOLD_DIRS:
        d = rp_dir / "Story Cards" / dir_name
        d.mkdir(parents=True, exist_ok=True)
        created_files.append(f"Story Cards/{dir_name}/")

    # Create RP State directory + Story_Guidelines.md
    rp_state = rp_dir / "RP State"
    rp_state.mkdir(parents=True, exist_ok=True)

    guidelines_path = rp_state / "Story_Guidelines.md"
    dual_str = f"[{', '.join(body.dual_characters)}]" if body.dual_characters else "[]"
    tone_str = f'"{body.tone}"' if body.tone else "[]"
    guidelines_content = GUIDELINES_TEMPLATE.format(
        pov_mode=body.pov_mode,
        dual_characters=dual_str,
        tone=tone_str,
        scene_pacing=body.scene_pacing,
    )
    guidelines_path.write_text(guidelines_content, encoding="utf-8")
    created_files.append("RP State/Story_Guidelines.md")

    return RPResponse(rp_folder=body.rp_name, created_files=created_files)


@router.get("", response_model=list[RPInfo])
async def list_rps(
    db: Database = Depends(get_db),
    indexer: CardIndexer = Depends(get_card_indexer),
    vault_root: Path = Depends(get_vault_root),
):
    """List all discovered RP folders with basic info."""
    folders = indexer.get_all_rp_folders()
    if not folders:
        return []

    # Batch queries instead of 2N individual queries
    card_count_rows = await db.fetch_all(
        "SELECT rp_folder, COUNT(*) as cnt FROM story_cards GROUP BY rp_folder"
    )
    card_counts = {r["rp_folder"]: r["cnt"] for r in card_count_rows}

    branch_rows = await db.fetch_all(
        "SELECT rp_folder, name FROM branches"
    )
    branch_map: dict[str, list[str]] = {}
    for r in branch_rows:
        branch_map.setdefault(r["rp_folder"], []).append(r["name"])

    result = []
    for folder in folders:
        card_count = card_counts.get(folder, 0)
        guidelines_path = vault_root / folder / "RP State" / "Story_Guidelines.md"
        result.append(RPInfo(
            rp_folder=folder,
            has_story_cards=card_count > 0,
            card_count=card_count,
            has_guidelines=guidelines_path.exists(),
            branches=branch_map.get(folder, []),
        ))
    return result


@router.get("/{name}", response_model=RPInfo)
async def get_rp(
    name: str,
    db: Database = Depends(get_db),
    vault_root: Path = Depends(get_vault_root),
):
    """Get info about a specific RP."""
    rp_dir = vault_root / name
    if not rp_dir.is_dir():
        raise HTTPException(404, detail=f"RP folder not found: {name}")

    card_count = await db.fetch_val(
        "SELECT COUNT(*) FROM story_cards WHERE rp_folder = ?", [name]
    ) or 0

    guidelines_path = vault_root / name / "RP State" / "Story_Guidelines.md"
    has_guidelines = guidelines_path.exists()

    branch_rows = await db.fetch_all(
        "SELECT name FROM branches WHERE rp_folder = ?", [name]
    )
    branches = [r["name"] for r in branch_rows]

    return RPInfo(
        rp_folder=name,
        has_story_cards=card_count > 0,
        card_count=card_count,
        has_guidelines=has_guidelines,
        branches=branches,
    )
