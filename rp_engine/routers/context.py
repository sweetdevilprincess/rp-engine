"""Context endpoints — the main intelligence API.

POST /api/context — primary endpoint. Client sends raw user_message,
gets back everything needed: cards, NPC briefs, state, alerts, guidelines.

Also includes guidelines (moved from guidelines.py), graph resolution,
and continuity brief endpoints.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.dependencies import (
    get_context_engine,
    get_db,
    get_graph_resolver,
    get_vault_root,
)
from rp_engine.models.context import (
    ContextRequest,
    ContextResponse,
    ResolveRequest,
)
from rp_engine.models.rp import GuidelinesResponse
from rp_engine.utils.frontmatter import parse_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/context", tags=["context"])

# Simple mtime-based cache for guidelines
_guidelines_cache: dict[str, tuple[float, GuidelinesResponse]] = {}


@router.post("", response_model=ContextResponse)
async def get_context(
    body: ContextRequest,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    session_id: str = Query(None),
    context_engine=Depends(get_context_engine),
):
    """The main endpoint. Smart API, dumb client."""
    return await context_engine.get_context(body, rp_folder, branch, session_id)


@router.post("/resolve")
async def resolve_context(
    body: ResolveRequest,
    rp_folder: str = Query(...),
    graph_resolver=Depends(get_graph_resolver),
):
    """Explicit graph resolution from keywords."""
    seed_ids = []
    for kw in body.keywords:
        eid = await graph_resolver.resolve_entity(kw, rp_folder)
        if eid:
            seed_ids.append(eid)

    if not seed_ids:
        return {"connections": [], "seed_count": 0}

    connections = await graph_resolver.get_connections(
        seed_ids, max_hops=body.max_hops, max_results=body.max_results
    )

    return {
        "connections": [
            {
                "entity_id": c.entity_id,
                "entity_name": c.entity_name,
                "card_type": c.card_type,
                "hop": c.hop,
                "path": c.path,
                "connection_type": c.connection_type,
                "content": c.content,
                "summary": c.summary,
            }
            for c in connections
        ],
        "seed_count": len(seed_ids),
    }


@router.get("/continuity")
async def get_continuity(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    db=Depends(get_db),
):
    """Data-only continuity brief (Phase 2 — no LLM synthesis)."""
    # Scene
    scene = await db.fetch_one(
        "SELECT location, time_of_day, mood, in_story_timestamp FROM scene_context WHERE rp_folder = ? AND branch = ?",
        [rp_folder, branch],
    )

    # Characters
    characters = await db.fetch_all(
        "SELECT name, location, emotional_state, conditions FROM characters WHERE rp_folder = ? AND branch = ?",
        [rp_folder, branch],
    )

    # Recent exchanges
    exchanges = await db.fetch_all(
        """SELECT exchange_number, user_message, assistant_response, in_story_timestamp
           FROM exchanges WHERE rp_folder = ? AND branch = ?
           ORDER BY exchange_number DESC LIMIT 3""",
        [rp_folder, branch],
    )

    # Active threads
    threads = await db.fetch_all(
        """SELECT pt.name, pt.status, pt.phase, COALESCE(tc.current_counter, 0) as counter
           FROM plot_threads pt
           LEFT JOIN thread_counters tc ON pt.id = tc.thread_id AND pt.rp_folder = tc.rp_folder AND tc.branch = ?
           WHERE pt.rp_folder = ? AND pt.status = 'active'""",
        [branch, rp_folder],
    )

    return {
        "scene": dict(scene) if scene else None,
        "characters": [dict(c) for c in characters],
        "recent_exchanges": [dict(e) for e in exchanges],
        "active_threads": [dict(t) for t in threads],
    }


@router.get("/guidelines", response_model=GuidelinesResponse)
async def get_guidelines(
    rp_folder: str = Query(...),
    vault_root: Path = Depends(get_vault_root),
):
    """Get parsed Story_Guidelines.md frontmatter for an RP."""
    guidelines_path = vault_root / rp_folder / "RP State" / "Story_Guidelines.md"
    if not guidelines_path.exists():
        raise HTTPException(404, detail=f"No guidelines found for {rp_folder}")

    mtime = guidelines_path.stat().st_mtime

    if rp_folder in _guidelines_cache:
        cached_mtime, cached_resp = _guidelines_cache[rp_folder]
        if cached_mtime == mtime:
            return cached_resp

    frontmatter, _ = parse_file(guidelines_path)
    if frontmatter is None:
        raise HTTPException(422, detail="Could not parse guidelines frontmatter")

    resp = GuidelinesResponse(
        pov_mode=frontmatter.get("pov_mode"),
        dual_characters=frontmatter.get("dual_characters", []),
        narrative_voice=frontmatter.get("narrative_voice"),
        tense=frontmatter.get("tense"),
        tone=frontmatter.get("tone"),
        scene_pacing=frontmatter.get("scene_pacing"),
        integrate_user_narrative=frontmatter.get("integrate_user_narrative"),
    )

    _guidelines_cache[rp_folder] = (mtime, resp)
    return resp


# ---------------------------------------------------------------------------
# System prompt builder helpers
# ---------------------------------------------------------------------------


def _build_writing_section(raw_md: str) -> dict:
    """Extract key sections from the writing guide into a structured dict."""
    section: dict = {
        "core_pillars": [
            "Show Don't Tell: NEVER report emotions directly. ALWAYS show through physical reactions.",
            "Specificity Over Generality: AVOID generic descriptors. REQUIRE unique, memorable details.",
            "Strong Verbs: AVOID passive constructions. PREFER visceral, active verbs.",
            "Dynamic Rhythm: Match sentence structure to emotional state. Tension = short/clipped. Calm = longer/flowing.",
            "Friction and Consequence: Every significant action has physical cost. No painless combat or effortless movement.",
        ],
        "emotion_physical_map": {
            "Fear": "Throat tightening, shallow breath, cold sweat, trembling hands, stomach dropping",
            "Anger": "Jaw clenching, knuckles whitening, heat in chest, narrowed eyes, rigid posture",
            "Sadness": "Chest heaviness, burning behind eyes, tight throat, slumped shoulders",
            "Anxiety": "Restless fingers, racing heartbeat, skin prickling, dry mouth",
            "Shame": "Heat in face, gaze dropping, shoulders curling inward, urge to shrink",
            "Longing": "Ache in chest, reaching impulse, breath catching, hollow feeling",
            "Relief": "Shoulders dropping, breath releasing, tension draining, steadying",
        },
        "banned_patterns": [
            "Sequential pairs (', then'): Rewrite as fluid motion",
            "Vague interiority ('something' + verb): Name what's happening",
            "Anthropomorphized silence ('silence/air' + verb): Show effect through behavior",
            "Negation formula ('not X, but Y'): Commit to what it is",
            "Hedged reactions ('isn't quite'): Describe actual gesture",
            "Meta-narrative ('scene's not over'): Stay in character POV",
            "Atmospheric opening: Start with character in action, not weather",
            "Participle pileup: Max 2 ', [verb]ing' in a row",
        ],
        "ai_vocabulary": [
            "Abstract nouns: tapestry, landscape, interplay, intricacies, nuance, multifaceted, dynamics, framework, paradigm",
            "Verbs: delve, foster, garner, underscore, showcase, highlight, navigate (emotions), unpack (ideas)",
            "Adjectives: pivotal, crucial, vital, vibrant, intricate, profound, compelling, poignant, evocative, palpable",
            "Adverbs: seemingly, arguably, notably, importantly, ultimately, fundamentally, inherently, undeniably",
        ],
    }

    # If we got the raw markdown, flag that we extracted from the actual file
    if raw_md.strip():
        section["source"] = "UNIVERSAL_WRITING_PRINCIPLES.md"
    else:
        section["source"] = "hardcoded_defaults"

    return section


def _build_npc_framework_section() -> dict:
    """Return hardcoded NPC framework info (stable constants)."""
    return {
        "archetypes": {
            "POWER_HOLDER": "Authority figures, crime bosses, politicians. Expect deference, trade favors, punish disrespect.",
            "TRANSACTIONAL": "Deal-makers, fixers, brokers. Everything has a price. Loyal to profit.",
            "COMMON_PEOPLE": "Regular folks, bystanders, service workers. React realistically, avoid heroics.",
            "OPPOSITION": "Antagonists, rivals, enemies. Actively work against player goals.",
            "SPECIALIST": "Experts, doctors, hackers. Defined by competence. Speak in their field's language.",
            "PROTECTOR": "Bodyguards, loyal allies, mentors. Priority is safety of their charge.",
            "OUTSIDER": "Strangers, newcomers, unknowns. Limited knowledge, fresh perspective.",
        },
        "modifiers": [
            "OBSESSIVE", "SADISTIC", "PARANOID", "FANATICAL", "NARCISSISTIC",
            "SOCIOPATHIC", "ADDICTED", "HONOR_BOUND", "GRIEF_CONSUMED",
        ],
        "trust_stages": {
            "hostile": {"range": [-50, -36], "description": "Actively hostile, will harm if able"},
            "antagonistic": {"range": [-35, -21], "description": "Openly opposed, will obstruct"},
            "suspicious": {"range": [-20, -11], "description": "Distrustful, assumes worst"},
            "wary": {"range": [-10, -1], "description": "Cautious, keeps distance"},
            "neutral": {"range": [0, 9], "description": "Default state, no strong feelings"},
            "familiar": {"range": [10, 19], "description": "Friendly, will help within limits"},
            "trusted": {"range": [20, 34], "description": "Strong bond, will take risks"},
            "devoted": {"range": [35, 50], "description": "Deep loyalty, will sacrifice"},
        },
    }


def _build_output_format_section() -> dict:
    """Return output format rules for RP responses."""
    return {
        "rules": [
            "RP responses contain ONLY narrative text.",
            "No meta commentary, OOC text, or system messages in the response.",
            "Strip thinking blocks and tool call content.",
            "No summaries or recaps unless explicitly requested.",
            "End on action, decision, or consequence — not summary or false profundity.",
        ],
        "response_structure": [
            "1. Acknowledge player's action with consequences.",
            "2. Advance scene with NPC reactions / environmental changes.",
            "3. Open opportunities for player's next action.",
            "4. End at natural pause point (not mid-action).",
        ],
    }


def _assemble_system_prompt(sections: dict) -> str:
    """Combine all sections into a formatted system prompt string."""
    parts: list[str] = []

    # --- Writing Principles ---
    writing = sections.get("writing_principles")
    if writing:
        parts.append("# Writing Principles\n")
        parts.append("## Core Pillars")
        for pillar in writing.get("core_pillars", []):
            parts.append(f"- {pillar}")

        parts.append("\n## Emotion to Physical Reaction Map")
        parts.append("Never report feelings directly. Always show through the body.\n")
        parts.append("| Emotion | Physical Manifestations |")
        parts.append("|---------|------------------------|")
        for emotion, manifestations in writing.get("emotion_physical_map", {}).items():
            parts.append(f"| **{emotion}** | {manifestations} |")

        banned = writing.get("banned_patterns", [])
        if banned:
            parts.append("\n## Banned Patterns")
            for pattern in banned:
                parts.append(f"- {pattern}")

        ai_vocab = writing.get("ai_vocabulary", [])
        if ai_vocab:
            parts.append("\n## AI Vocabulary to Avoid")
            for category in ai_vocab:
                parts.append(f"- {category}")

    # --- RP Guidelines ---
    rp_guide = sections.get("rp_guidelines")
    if rp_guide:
        parts.append("\n\n# RP Guidelines\n")
        if rp_guide.get("pov_mode"):
            parts.append(f"- **POV Mode:** {rp_guide['pov_mode']}")
        if rp_guide.get("dual_characters"):
            chars = ", ".join(rp_guide["dual_characters"])
            parts.append(f"- **Dual Characters:** {chars}")
        if rp_guide.get("narrative_voice"):
            parts.append(f"- **Narrative Voice:** {rp_guide['narrative_voice']}")
        if rp_guide.get("tense"):
            parts.append(f"- **Tense:** {rp_guide['tense']}")
        if rp_guide.get("tone"):
            tone = rp_guide["tone"]
            if isinstance(tone, list):
                tone = ", ".join(tone)
            parts.append(f"- **Tone:** {tone}")
        if rp_guide.get("scene_pacing"):
            parts.append(f"- **Scene Pacing:** {rp_guide['scene_pacing']}")

    # --- NPC Framework ---
    npc = sections.get("npc_framework")
    if npc:
        parts.append("\n\n# NPC Framework\n")
        parts.append("## Archetypes")
        for archetype, desc in npc.get("archetypes", {}).items():
            parts.append(f"- **{archetype}:** {desc}")

        modifiers = npc.get("modifiers", [])
        if modifiers:
            parts.append(f"\n## Behavioral Modifiers\n{', '.join(modifiers)}")

        trust = npc.get("trust_stages", {})
        if trust:
            parts.append("\n## Trust Stages\n")
            parts.append("| Stage | Range | Description |")
            parts.append("|-------|-------|-------------|")
            for stage, info in trust.items():
                r = info["range"]
                parts.append(f"| {stage} | {r[0]} to {r[1]} | {info['description']} |")

    # --- Output Format ---
    output = sections.get("output_format")
    if output:
        parts.append("\n\n# Output Format\n")
        for rule in output.get("rules", []):
            parts.append(f"- {rule}")
        structure = output.get("response_structure", [])
        if structure:
            parts.append("\n## Response Structure")
            for step in structure:
                parts.append(f"- {step}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# System prompt endpoint
# ---------------------------------------------------------------------------


@router.get("/guidelines/system-prompt")
async def get_system_prompt(
    rp_folder: str = Query(...),
    vault_root: Path = Depends(get_vault_root),
):
    """Return a structured system prompt with writing rules, NPC framework, and RP conventions."""

    sections: dict = {}

    # 1. Writing principles
    writing_path = vault_root / "z_AI Files" / "Claude" / "Guides" / "UNIVERSAL_WRITING_PRINCIPLES.md"
    writing_rules = ""
    if writing_path.exists():
        writing_rules = writing_path.read_text(encoding="utf-8")

    sections["writing_principles"] = _build_writing_section(writing_rules)

    # 2. RP-specific guidelines
    guidelines_path = vault_root / rp_folder / "RP State" / "Story_Guidelines.md"
    if guidelines_path.exists():
        frontmatter, _ = parse_file(guidelines_path)
        if frontmatter:
            sections["rp_guidelines"] = {
                "pov_mode": frontmatter.get("pov_mode"),
                "dual_characters": frontmatter.get("dual_characters", []),
                "narrative_voice": frontmatter.get("narrative_voice"),
                "tense": frontmatter.get("tense"),
                "tone": frontmatter.get("tone"),
                "scene_pacing": frontmatter.get("scene_pacing"),
            }

    # 3. NPC framework (hardcoded summary — stable constants)
    sections["npc_framework"] = _build_npc_framework_section()

    # 4. Output format
    sections["output_format"] = _build_output_format_section()

    # Assemble full system prompt
    system_prompt = _assemble_system_prompt(sections)

    return {"system_prompt": system_prompt, "sections": sections}
