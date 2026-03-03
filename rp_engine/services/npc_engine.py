"""NPC reaction engine — character acting, trust management, archetype loading.

Ported from .claude/mcp-servers/npc-agent/server.py. Produces structured
NPC reactions via LLM calls using the NPC Actor Agent system prompt +
character-specific context built from DB state and framework files.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from rp_engine.config import RPEngineConfig
from rp_engine.database import Database
from rp_engine.models.npc import (
    NPCListItem,
    NPCReaction,
    TrustEvent,
    TrustInfo,
    TrustShift,
)
from rp_engine.services.context_engine import trust_stage
from rp_engine.services.graph_resolver import GraphResolver
from rp_engine.services.llm_client import LLMClient
from rp_engine.services.vector_search import VectorSearch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trimming constants
# ---------------------------------------------------------------------------

ARCHETYPE_TRIM_SECTIONS = [
    "Setting Examples",
    "Dialogue Samples",
    "Internal Voice Patterns",
    "Interaction Modifiers",
    "Trust Behavior by Stage",
]

MODIFIER_TRIM_SECTIONS = [
    "Setting Applications",
    "Dialogue Patterns",
    "Red Flags in Behavior",
    "Differences From Similar Modifiers",
    "Interaction with Other Modifiers",
]

INTIMATE_KEYWORDS = {
    "kiss", "bite", "touch", "grab", "pull", "tease", "provoke",
    "lips", "mouth", "tongue", "jaw", "throat", "neck", "hair",
    "dare", "challenge", "prove", "show me",
    "bedroom", "hotel", "penthouse", "bed",
    "chain", "leash", "collar", "wrist", "pin",
    "sex", "intimate", "naked", "undress", "skin",
}

# Stop words for scene enrichment keyword extraction
_STOP_WORDS = frozenset({
    "that", "this", "with", "from", "what", "when", "where",
    "they", "them", "their", "then", "than", "been", "have",
    "will", "would", "could", "should", "about", "which",
    "there", "were", "being", "does", "doing", "into",
    "just", "only", "very", "also", "some", "scene",
    "react", "output", "valid", "json",
})


class NPCEngine:
    """NPC reaction pipeline: context building, LLM call, response parsing."""

    def __init__(
        self,
        db: Database,
        llm_client: LLMClient,
        graph_resolver: GraphResolver,
        vector_search: VectorSearch,
        config: RPEngineConfig,
        vault_root: Path,
        npc_intelligence=None,
        scene_classifier=None,
    ) -> None:
        self.db = db
        self.llm_client = llm_client
        self.graph_resolver = graph_resolver
        self.vector_search = vector_search
        self.config = config
        self.vault_root = vault_root
        self.npc_intelligence = npc_intelligence
        self._scene_classifier = scene_classifier

        # Framework caches (loaded on init)
        self._archetypes: dict[str, str] = {}
        self._modifiers: dict[str, str] = {}
        self._trust_framework: str = ""
        self._system_prompt: str = ""
        self._load_framework()

    # ------------------------------------------------------------------
    # Framework loading
    # ------------------------------------------------------------------

    def _load_framework(self) -> None:
        """Load archetype, modifier, trust, and system prompt files into memory."""
        framework_dir = Path(__file__).parent.parent / "framework"

        archetypes_dir = framework_dir / "archetypes"
        if archetypes_dir.exists():
            for f in archetypes_dir.glob("*.md"):
                self._archetypes[f.stem.upper()] = f.read_text(encoding="utf-8")
            logger.info("Loaded %d archetypes", len(self._archetypes))

        modifiers_dir = framework_dir / "modifiers"
        if modifiers_dir.exists():
            for f in modifiers_dir.glob("*.md"):
                self._modifiers[f.stem.upper()] = f.read_text(encoding="utf-8")
            logger.info("Loaded %d modifiers", len(self._modifiers))

        trust_path = framework_dir / "trust-stages.md"
        if trust_path.exists():
            self._trust_framework = trust_path.read_text(encoding="utf-8")

        prompt_path = framework_dir / "system-prompt.md"
        if prompt_path.exists():
            self._system_prompt = prompt_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Core reaction pipeline
    # ------------------------------------------------------------------

    async def get_reaction(
        self,
        npc_name: str,
        scene_prompt: str,
        pov_character: str = "Lilith",
        rp_folder: str = "",
        branch: str = "main",
        model_override: str | None = None,
        recent_exchanges: list[dict] | None = None,
        scene_enrichment: str | None = None,
    ) -> NPCReaction:
        """Full NPC reaction pipeline: load state → build context → call LLM → parse."""

        # 1. Load NPC story card
        card_row = await self.db.fetch_one(
            "SELECT name, content, frontmatter FROM story_cards WHERE rp_folder = ? AND LOWER(name) = LOWER(?)",
            [rp_folder, npc_name],
        )
        if not card_row:
            raise ValueError(f"NPC '{npc_name}' not found in '{rp_folder}'")

        card_content = card_row["content"] or ""
        card_name = card_row["name"]

        # Parse frontmatter for archetype/modifiers if character row doesn't have them
        card_fm = {}
        if card_row.get("frontmatter"):
            try:
                card_fm = json.loads(card_row["frontmatter"]) if isinstance(card_row["frontmatter"], str) else card_row["frontmatter"]
            except (json.JSONDecodeError, TypeError):
                card_fm = {}

        # 2. Load character state
        char_row = await self.db.fetch_one(
            """SELECT primary_archetype, secondary_archetype, behavioral_modifiers,
                      emotional_state, conditions, importance
               FROM characters WHERE rp_folder = ? AND branch = ? AND LOWER(name) = LOWER(?)""",
            [rp_folder, branch, npc_name],
        )

        archetype = (char_row["primary_archetype"] if char_row else None) or card_fm.get("primary_archetype")
        modifiers_raw = (char_row["behavioral_modifiers"] if char_row else None) or card_fm.get("behavioral_modifiers", [])
        modifiers: list[str] = []
        if modifiers_raw:
            if isinstance(modifiers_raw, str):
                try:
                    modifiers = json.loads(modifiers_raw)
                except (json.JSONDecodeError, TypeError):
                    modifiers = [modifiers_raw]
            elif isinstance(modifiers_raw, list):
                modifiers = modifiers_raw

        # 3. Load trust data
        trust_score = 0
        trust_stage_name = "neutral"
        dynamic = None
        session_gained = 0
        session_lost = 0
        trust_history: list[dict] = []

        rel_row = await self.db.fetch_one(
            """SELECT id, initial_trust_score + trust_modification_sum as score,
                      trust_stage, dynamic, session_trust_gained, session_trust_lost
               FROM relationships
               WHERE rp_folder = ? AND branch = ?
                 AND ((LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?))
                   OR (LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?)))""",
            [rp_folder, branch, npc_name, pov_character, pov_character, npc_name],
        )
        if rel_row:
            trust_score = rel_row["score"] or 0
            trust_stage_name = trust_stage(trust_score)
            dynamic = rel_row.get("dynamic")
            session_gained = rel_row.get("session_trust_gained") or 0
            session_lost = rel_row.get("session_trust_lost") or 0

            # Load recent trust history
            history_rows = await self.db.fetch_all(
                "SELECT date, change, direction, reason FROM trust_modifications WHERE relationship_id = ? ORDER BY created_at DESC LIMIT 5",
                [rel_row["id"]],
            )
            trust_history = [dict(r) for r in history_rows]

        # 4. Detect intimate context
        intimate = self._detect_intimate(scene_prompt)

        # 5. Build character context (user message for LLM)
        character_context = self._build_character_context(
            card_name=card_name,
            card_content=card_content,
            archetype=archetype,
            modifiers=modifiers,
            trust_score=trust_score,
            trust_stage_name=trust_stage_name,
            dynamic=dynamic,
            trust_history=trust_history,
            pov_character=pov_character,
            intimate=intimate,
            recent_exchanges=recent_exchanges,
            scene_enrichment=scene_enrichment,
            rp_folder=rp_folder,
            branch=branch,
            scene_prompt=scene_prompt,
        )

        # 5b. NPC Behavioral Intelligence injection
        behavioral_constraints = ""
        if self.npc_intelligence:
            try:
                signals = {}
                if self._scene_classifier:
                    signals = await self._scene_classifier.classify(
                        scene_prompt, None, rp_folder, branch)
                payload = self.npc_intelligence.prepare(
                    npc_name=card_name,
                    archetype=archetype or "common_people",
                    modifiers=modifiers,
                    trust_stage=trust_stage_name,
                    trust_score=trust_score,
                    scene_signals=signals,
                    scene_prompt=scene_prompt,
                )
                if payload.patterns_included:
                    behavioral_constraints = payload.text
            except Exception:
                logger.warning("NPC intelligence failed for %s", card_name, exc_info=True)

        # 6. Load secrets this NPC knows
        secrets_text = await self._load_npc_secrets(npc_name, rp_folder)

        # 7. Load recent exchanges if not pre-loaded (batch provides them)
        exchanges_text = ""
        if recent_exchanges is not None:
            exchanges_text = self._format_exchanges(recent_exchanges)
        else:
            exchanges = await self._load_recent_exchanges(rp_folder, branch)
            exchanges_text = self._format_exchanges(exchanges)

        # 8. Get scene enrichment if not pre-loaded
        if scene_enrichment is None:
            scene_enrichment = await self._get_scene_enrichment(scene_prompt, rp_folder)

        # Build final prompt
        full_context = character_context
        if exchanges_text:
            full_context += f"\n## Recent Conversation\nThese are the most recent exchanges. Use this for continuity.\n\n{exchanges_text}\n"
        if secrets_text:
            full_context += f"\n## CANON FACTS — Secrets You Know\nThese are ESTABLISHED FACTS. Use exact details. Do NOT invent alternatives.\n\n{secrets_text}\n"
        if scene_enrichment:
            full_context += f"\n## Scene-Relevant Context\n{scene_enrichment}\n"

        full_context += f"\n---\n## What Just Happened\n{scene_prompt}\n"

        # 9. Call LLM
        effective_system = self._system_prompt
        if behavioral_constraints:
            effective_system = f"{self._system_prompt}\n\n{behavioral_constraints}"

        model = model_override or self.llm_client.models.npc_reactions
        response = await self.llm_client.generate(
            messages=[
                {"role": "system", "content": effective_system},
                {"role": "user", "content": full_context},
            ],
            model=model,
            temperature=0.6,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )

        # 10. Parse response
        return self._parse_reaction(response.content, card_name)

    async def get_batch_reactions(
        self,
        npc_names: list[str],
        scene_prompt: str,
        pov_character: str = "Lilith",
        rp_folder: str = "",
        branch: str = "main",
    ) -> list[NPCReaction]:
        """Get reactions from multiple NPCs, sharing context and running in parallel."""
        # Load shared context once
        exchanges = await self._load_recent_exchanges(rp_folder, branch, limit=2, max_chars=1200)
        enrichment = await self._get_scene_enrichment(scene_prompt, rp_folder)

        # Run reactions in parallel
        tasks = [
            self.get_reaction(
                name, scene_prompt, pov_character, rp_folder, branch,
                recent_exchanges=exchanges, scene_enrichment=enrichment,
            )
            for name in npc_names
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions, log them
        reactions: list[NPCReaction] = []
        for name, result in zip(npc_names, results):
            if isinstance(result, Exception):
                logger.error("NPC reaction failed for %s: %s", name, result)
            else:
                reactions.append(result)

        return reactions

    # ------------------------------------------------------------------
    # Trust + listing
    # ------------------------------------------------------------------

    async def get_trust(
        self,
        npc_name: str,
        target: str = "Lilith",
        rp_folder: str = "",
        branch: str = "main",
    ) -> TrustInfo:
        """Get full trust information for an NPC-target relationship."""
        rel_row = await self.db.fetch_one(
            """SELECT id, initial_trust_score + trust_modification_sum as score,
                      trust_stage, dynamic, session_trust_gained, session_trust_lost
               FROM relationships
               WHERE rp_folder = ? AND branch = ?
                 AND ((LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?))
                   OR (LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?)))""",
            [rp_folder, branch, npc_name, target, target, npc_name],
        )

        score = 0
        session_gains = 0
        session_losses = 0
        history: list[TrustEvent] = []

        if rel_row:
            score = rel_row["score"] or 0
            session_gains = rel_row.get("session_trust_gained") or 0
            session_losses = rel_row.get("session_trust_lost") or 0

            history_rows = await self.db.fetch_all(
                "SELECT date, change, direction, reason FROM trust_modifications WHERE relationship_id = ? ORDER BY created_at DESC LIMIT 10",
                [rel_row["id"]],
            )
            history = [
                TrustEvent(
                    date=r.get("date") or "",
                    change=r.get("change") or 0,
                    direction=r.get("direction") or "neutral",
                    reason=r.get("reason"),
                )
                for r in history_rows
            ]

        return TrustInfo(
            npc_name=npc_name,
            target=target,
            trust_score=score,
            trust_stage=trust_stage(score),
            session_gains=session_gains,
            session_losses=session_losses,
            history=history,
        )

    async def list_npcs(
        self,
        rp_folder: str,
        branch: str = "main",
        pov_character: str = "Lilith",
    ) -> list[NPCListItem]:
        """List all NPCs in an RP with their state."""
        # Get all NPC/character cards
        card_rows = await self.db.fetch_all(
            "SELECT name, card_type, importance, frontmatter FROM story_cards WHERE rp_folder = ? AND card_type IN ('npc', 'character')",
            [rp_folder],
        )

        results: list[NPCListItem] = []
        for card in card_rows:
            fm = {}
            if card.get("frontmatter"):
                try:
                    fm = json.loads(card["frontmatter"]) if isinstance(card["frontmatter"], str) else card["frontmatter"]
                except (json.JSONDecodeError, TypeError):
                    fm = {}

            # Skip player characters
            if fm.get("is_player_character"):
                continue

            name = card["name"]

            # Load character state
            char_row = await self.db.fetch_one(
                """SELECT primary_archetype, secondary_archetype, behavioral_modifiers,
                          emotional_state, location
                   FROM characters WHERE rp_folder = ? AND branch = ? AND LOWER(name) = LOWER(?)""",
                [rp_folder, branch, name],
            )

            archetype = (char_row["primary_archetype"] if char_row else None) or fm.get("primary_archetype")
            secondary = (char_row["secondary_archetype"] if char_row else None) or fm.get("secondary_archetype")
            modifiers_raw = (char_row["behavioral_modifiers"] if char_row else None) or fm.get("behavioral_modifiers", [])
            modifiers: list[str] = []
            if modifiers_raw:
                if isinstance(modifiers_raw, str):
                    try:
                        modifiers = json.loads(modifiers_raw)
                    except (json.JSONDecodeError, TypeError):
                        modifiers = [modifiers_raw]
                elif isinstance(modifiers_raw, list):
                    modifiers = modifiers_raw

            # Load trust score
            trust_score = 0
            rel_row = await self.db.fetch_one(
                """SELECT initial_trust_score + trust_modification_sum as score
                   FROM relationships
                   WHERE rp_folder = ? AND branch = ?
                     AND ((LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?))
                       OR (LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?)))""",
                [rp_folder, branch, name, pov_character, pov_character, name],
            )
            if rel_row:
                trust_score = rel_row["score"] or 0

            results.append(NPCListItem(
                name=name,
                importance=card.get("importance") or fm.get("importance"),
                primary_archetype=archetype,
                secondary_archetype=secondary,
                behavioral_modifiers=modifiers if isinstance(modifiers, list) else [],
                trust_score=trust_score,
                trust_stage=trust_stage(trust_score),
                location=char_row["location"] if char_row else None,
                emotional_state=char_row["emotional_state"] if char_row else None,
            ))

        return results

    # ------------------------------------------------------------------
    # Context building helpers
    # ------------------------------------------------------------------

    def _build_character_context(
        self,
        card_name: str,
        card_content: str,
        archetype: str | None,
        modifiers: list[str],
        trust_score: int,
        trust_stage_name: str,
        dynamic: str | None,
        trust_history: list[dict],
        pov_character: str,
        intimate: bool,
        recent_exchanges: list[dict] | None,
        scene_enrichment: str | None,
        rp_folder: str,
        branch: str,
        scene_prompt: str,
    ) -> str:
        """Build the character-specific user message for the LLM."""
        # Trim trust framework to relevant stage
        trust_section = self._extract_trust_stage_section(trust_stage_name, modifiers)

        # Load and trim archetype
        archetype_content = ""
        if archetype and archetype.upper() in self._archetypes:
            raw = self._archetypes[archetype.upper()]
            trim_list = list(ARCHETYPE_TRIM_SECTIONS)
            if not intimate:
                trim_list.append("Intimate/Romantic Behavior")
            archetype_content = self._trim_sections(raw, trim_list, keep_intimate=intimate)

        # Load and trim modifiers
        modifier_parts = []
        for m in modifiers:
            if m and m.upper() in self._modifiers:
                raw = self._modifiers[m.upper()]
                trim_list = list(MODIFIER_TRIM_SECTIONS)
                if not intimate:
                    trim_list.append("Intimate/Romantic Behavior")
                modifier_parts.append(self._trim_sections(raw, trim_list, keep_intimate=intimate))

        # Format trust history
        history_str = "None"
        if trust_history:
            history_lines = []
            for h in trust_history:
                direction = h.get("direction", "?")
                change = h.get("change", 0)
                reason = h.get("reason", "")
                history_lines.append(f"  - {direction} {change:+d}: {reason}" if reason else f"  - {direction} {change:+d}")
            history_str = "\n".join(history_lines)

        prompt = f"""## Your Character Card
{card_content}

## Trust System
{trust_section}

## Your Archetype: {archetype or 'None'}
{archetype_content}

## Your Behavioral Modifiers
{''.join(modifier_parts) if modifier_parts else 'None'}

## Current Relationship with {pov_character}
- Trust Score: {trust_score}
- Trust Stage: {trust_stage_name}
- Dynamic: {dynamic or 'Unknown'}
- Recent History:
{history_str}"""

        return prompt

    def _extract_trust_stage_section(self, stage_name: str, modifiers: list[str]) -> str:
        """Extract only the relevant trust stage + quick reference from the full trust doc."""
        if not self._trust_framework:
            return f"Trust Stage: {stage_name}"

        parts = re.split(r"\n(?=## )", self._trust_framework)
        result: list[str] = []

        for part in parts:
            first_line = part.strip().split("\n")[0]

            # Always keep: score range table, gain/loss rules, quick reference
            if any(k in first_line for k in ["Score Range", "Trust Gain", "Trust Loss", "Quick Reference"]):
                result.append(part.strip())
                continue

            # Skip: Positive Event Examples, Tracking in Character Cards
            if any(k in first_line for k in ["Positive Event", "Tracking"]):
                continue

            # Stage Behaviors: extract only the relevant ### subsection
            if "Stage" in first_line and "###" not in first_line:
                substages = re.split(r"\n(?=### )", part)
                for sub in substages:
                    if sub.startswith("### ") and stage_name.lower() in sub.split("\n")[0].lower():
                        result.append(f"## Your Current Stage: {stage_name}\n\n{sub.strip()}")
                        break
                continue

            # Modifier Interactions: keep only entries for active modifiers
            if "Modifier" in first_line and modifiers:
                lines = part.split("\n")
                kept = [lines[0], ""]
                capturing = False
                for line in lines[1:]:
                    if line.startswith("**"):
                        capturing = any(m.upper() in line.upper() for m in modifiers)
                    if capturing:
                        kept.append(line)
                if len(kept) > 2:
                    result.append("\n".join(kept))
                continue

        return "\n\n".join(result) if result else f"Trust Stage: {stage_name}"

    # ------------------------------------------------------------------
    # Trimming
    # ------------------------------------------------------------------

    @staticmethod
    def _trim_sections(content: str, sections: list[str], keep_intimate: bool = False) -> str:
        """Remove named ## sections from markdown content."""
        if not content or not sections:
            return content

        lines = content.split("\n")
        result: list[str] = []
        skipping = False

        for line in lines:
            if line.startswith("## ") and not line.startswith("### "):
                heading = line[3:].strip()
                skipping = any(s.lower() in heading.lower() for s in sections)

            if not skipping:
                result.append(line)

        return "\n".join(result)

    @staticmethod
    def _detect_intimate(scene_prompt: str) -> bool:
        """Check if scene involves intimate/physical dynamics."""
        if not scene_prompt:
            return False
        lower = scene_prompt.lower()
        return any(kw in lower for kw in INTIMATE_KEYWORDS)

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    async def _load_recent_exchanges(
        self,
        rp_folder: str,
        branch: str,
        limit: int = 3,
        max_chars: int = 1500,
    ) -> list[dict]:
        """Load recent exchanges from DB."""
        rows = await self.db.fetch_all(
            """SELECT user_message, assistant_response FROM exchanges
               WHERE rp_folder = ? AND branch = ?
               ORDER BY exchange_number DESC LIMIT ?""",
            [rp_folder, branch, limit],
        )
        # Reverse so oldest is first
        return list(reversed(rows))

    def _format_exchanges(self, exchanges: list[dict], max_chars: int = 1500) -> str:
        """Format exchanges into text, capped at max_chars."""
        parts: list[str] = []
        total = 0
        for ex in exchanges:
            user = (ex.get("user_message") or "").strip()
            asst = (ex.get("assistant_response") or "").strip()
            # Strip OOC markers
            user = re.sub(r"\[OOC:.*?\]", "", user).strip()
            asst = re.sub(r"\[OOC:.*?\]", "", asst).strip()
            chunk = f"User: {user}\nAssistant: {asst}"
            if total + len(chunk) > max_chars:
                remaining = max_chars - total
                if remaining > 50:
                    parts.append(chunk[:remaining] + "...")
                break
            parts.append(chunk)
            total += len(chunk)
        return "\n\n".join(parts)

    async def _load_npc_secrets(
        self,
        npc_name: str,
        rp_folder: str,
        max_secrets: int = 3,
        max_chars: int = 5000,
    ) -> str:
        """Load secret cards that this NPC knows about from the DB."""
        rows = await self.db.fetch_all(
            "SELECT name, content, frontmatter FROM story_cards WHERE rp_folder = ? AND card_type = 'secret'",
            [rp_folder],
        )

        npc_lower = npc_name.lower()
        secrets: list[str] = []
        total_chars = 0

        for row in rows:
            fm = {}
            if row.get("frontmatter"):
                try:
                    fm = json.loads(row["frontmatter"]) if isinstance(row["frontmatter"], str) else row["frontmatter"]
                except (json.JSONDecodeError, TypeError):
                    continue

            known_by = fm.get("known_by", [])
            if isinstance(known_by, str):
                known_by = [known_by]
            if not isinstance(known_by, list):
                continue

            # Case-insensitive substring match (e.g., "Dante" matches "Dante Moretti")
            if not any(npc_lower in kb.lower() for kb in known_by):
                continue

            body = row.get("content") or ""
            if total_chars + len(body) > max_chars and secrets:
                break

            secrets.append(f"### {row['name']}\n{body}")
            total_chars += len(body)

            if len(secrets) >= max_secrets:
                break

        return "\n\n".join(secrets)

    async def _get_scene_enrichment(self, scene_prompt: str, rp_folder: str) -> str:
        """Get scene-relevant context using graph resolver."""
        if not scene_prompt:
            return ""

        # Extract keywords from scene prompt
        words = re.findall(r"\b[A-Z][a-zA-Z]+\b", scene_prompt)
        words += [
            w for w in re.findall(r"\b[a-z]{4,}\b", scene_prompt.lower())
            if w not in _STOP_WORDS
        ]

        if not words:
            return ""

        # Resolve keywords to entity IDs
        seed_ids: list[str] = []
        for word in words[:10]:
            eid = await self.graph_resolver.resolve_entity(word, rp_folder)
            if eid:
                seed_ids.append(eid)

        if not seed_ids:
            return ""

        connections = await self.graph_resolver.get_connections(
            seed_ids, max_hops=2, max_results=5
        )

        if not connections:
            return ""

        lines: list[str] = []
        for c in connections:
            summary = c.summary or c.entity_name
            lines.append(f"- {c.entity_name} ({c.card_type}): {summary}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Response parsing (robust fallback chain)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_reaction(content: str, npc_name: str) -> NPCReaction:
        """Parse LLM response into NPCReaction with progressive fallbacks."""
        if not content or not content.strip():
            return _fallback_reaction(npc_name)

        # 1. Direct JSON parse
        try:
            data = json.loads(content)
            return NPCReaction(**data)
        except (json.JSONDecodeError, Exception):
            pass

        # 2. Strip markdown fences
        stripped = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`")
        try:
            data = json.loads(stripped)
            return NPCReaction(**data)
        except (json.JSONDecodeError, Exception):
            pass

        # 3. Extract JSON object from text
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return NPCReaction(**data)
            except (json.JSONDecodeError, Exception):
                pass

        # 4. Truncated JSON repair
        for suffix in ["}", "}}", "null}}", 'null"}}', '"}}']:
            try:
                data = json.loads(content.rstrip(",").rstrip() + suffix)
                return NPCReaction(**data)
            except (json.JSONDecodeError, Exception):
                continue

        # 5. Fallback
        logger.warning("Failed to parse NPC reaction for %s, returning fallback", npc_name)
        return _fallback_reaction(npc_name)


def _fallback_reaction(npc_name: str) -> NPCReaction:
    """Return a minimal fallback reaction when parsing fails."""
    return NPCReaction(
        character=npc_name,
        internalMonologue="[Parse error — reaction could not be generated]",
        physicalAction="Stands motionless.",
        dialogue=None,
        emotionalUndercurrent="neutral",
        trustShift=TrustShift(direction="neutral", amount=0, reason=None),
    )
