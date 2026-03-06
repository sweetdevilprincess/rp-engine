"""NPC brief builder — assembles behavioral briefs from pre-fetched data."""

from __future__ import annotations

from rp_engine.models.context import NPCBrief
from rp_engine.utils.json_helpers import safe_parse_json_list
from rp_engine.utils.trust import trust_stage


class NPCBriefBuilder:
    """Builds NPC behavioral briefs deterministically (no DB queries, no LLM)."""

    def build_brief(
        self,
        name: str,
        char_row: dict | None,
        pre_trust: int,
        signal_list: list[str],
    ) -> NPCBrief:
        """Build a behavioral brief using pre-fetched data."""
        archetype = char_row.get("primary_archetype") if char_row else None
        secondary = char_row.get("secondary_archetype") if char_row else None
        modifiers_raw = char_row.get("behavioral_modifiers") if char_row else None
        emotional = char_row.get("emotional_state") if char_row else None
        conditions_raw = char_row.get("conditions") if char_row else None
        importance = char_row.get("importance") if char_row else None

        modifiers = safe_parse_json_list(modifiers_raw)
        conditions = safe_parse_json_list(conditions_raw)

        stage = trust_stage(pre_trust)

        direction = self.build_behavioral_direction(
            archetype, stage, modifiers, signal_list
        )

        return NPCBrief(
            character=name,
            importance=importance,
            archetype=archetype,
            secondary_archetype=secondary,
            behavioral_modifiers=modifiers if isinstance(modifiers, list) else [],
            trust_score=pre_trust,
            trust_stage=stage,
            emotional_state=emotional,
            conditions=conditions if isinstance(conditions, list) else [],
            behavioral_direction=direction,
            scene_signals=signal_list,
        )

    def build_behavioral_direction(
        self,
        archetype: str | None,
        stage: str,
        modifiers: list[str],
        signals: list[str],
    ) -> str:
        """Build a deterministic behavioral direction string (no LLM)."""
        parts: list[str] = []

        if archetype:
            parts.append(f"Archetype: {archetype}")

        parts.append(f"Trust: {stage}")

        if modifiers:
            parts.append(f"Modifiers: {', '.join(modifiers)}")

        if signals:
            parts.append(f"Scene: {', '.join(signals)}")

        guidance_map = {
            "hostile": "Actively opposes. May betray or sabotage.",
            "antagonistic": "Open opposition. Refuses cooperation.",
            "suspicious": "Withholds information. Questions motives.",
            "wary": "Cautious engagement. Minimal vulnerability.",
            "neutral": "No strong feelings. Transactional interactions.",
            "familiar": "Willing to help. Some warmth and openness.",
            "trusted": "Confides freely. Protects and invests in relationship.",
            "devoted": "Deep loyalty. Will sacrifice for this person.",
        }
        if stage in guidance_map:
            parts.append(f"Direction: {guidance_map[stage]}")

        return " | ".join(parts)
