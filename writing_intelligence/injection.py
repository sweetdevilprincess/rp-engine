from typing import Optional, Callable

from .types import Pattern, ScoredPattern, TaskSignature, InjectionPayload
from ._token_utils import default_token_counter


class InjectionFormatter:
    HEADER_OVERHEAD = 80
    SECTION_HEADER = 15

    def __init__(self, token_budget: int = 600,
                 count_tokens: Optional[Callable[[str], int]] = None):
        self._count = count_tokens or default_token_counter
        self.token_budget = token_budget

    def format(self, scored_patterns: list[ScoredPattern],
               task_sig: TaskSignature) -> InjectionPayload:
        header = self._build_header(task_sig)
        remaining = self.token_budget - self.HEADER_OVERHEAD

        # Sort all by score descending (should already be sorted, but ensure)
        sorted_patterns = sorted(scored_patterns, key=lambda sp: sp.score, reverse=True)

        # Group by injection level for output assembly
        sections = {"critical": [], "moderate": [], "reminder": []}
        included_ids = []

        for sp in sorted_patterns:
            level = sp.injection_level
            # Format at assigned level
            text = self._format_at_level(sp.pattern, level)
            cost = self._count(text)

            if cost <= remaining:
                sections[level].append(text)
                included_ids.append(sp.pattern.id)
                remaining -= cost
            elif level == "critical":
                # Try moderate format for critical that doesn't fit
                text = self._format_moderate(sp.pattern)
                cost = self._count(text)
                if cost <= remaining:
                    sections["moderate"].append(text)
                    included_ids.append(sp.pattern.id)
                    remaining -= cost
            # Otherwise skip

        # Assemble final text
        lines = ["[WRITING CONSTRAINTS — THIS PASSAGE]", "", f"Scene context: {header}", ""]

        section_labels = {
            "critical": "CRITICAL (low proficiency):",
            "moderate": "MODERATE (rising proficiency):",
            "reminder": "REMINDER (high proficiency):",
        }

        for level in ["critical", "moderate", "reminder"]:
            if sections[level]:
                lines.append(section_labels[level])
                lines.extend(sections[level])
                lines.append("")

        lines.append("[END WRITING CONSTRAINTS]")

        full_text = "\n".join(lines)
        actual_tokens = self._count(full_text)

        return InjectionPayload(
            text=full_text,
            token_count=actual_tokens,
            patterns_included=included_ids,
            task_signature=task_sig,
        )

    def _format_at_level(self, pattern: Pattern, level: str) -> str:
        if level == "critical":
            return self._format_critical(pattern)
        elif level == "moderate":
            return self._format_moderate(pattern)
        else:
            return self._format_reminder(pattern)

    def _format_critical(self, pattern: Pattern) -> str:
        """Rule description + best correction pair example."""
        if not pattern.correction_pairs:
            return self._format_moderate(pattern)

        # Pick the correction pair with smallest combined token cost
        best_pair = min(pattern.correction_pairs,
                        key=lambda p: p.tokens_original + p.tokens_revised)

        return (f"- {pattern.description}\n"
                f'  EXAMPLE — Instead of: "{best_pair.original}"\n'
                f'  Write: "{best_pair.revised}"')

    def _format_moderate(self, pattern: Pattern) -> str:
        """Compressed rule only."""
        text = pattern.compressed_rule or pattern.description
        return f"- {text}"

    def _format_reminder(self, pattern: Pattern) -> str:
        """Brief one-liner."""
        text = pattern.compressed_rule or pattern.description.split(".")[0]
        return f"- {text}"

    def _build_header(self, task_sig: TaskSignature) -> str:
        element_names = {
            "physical_action": "physical",
            "dialogue": "dialogue",
            "internal_thought": "internal thought",
            "environmental_description": "environmental",
            "character_description": "character",
            "emotional_beat": "emotional",
            "sensory_detail": "sensory",
        }

        parts = [f"{task_sig.intensity.value.capitalize()}-intensity {task_sig.register.value}"]

        if task_sig.position != task_sig.position.MID:
            parts[0] += f", {task_sig.position.value}"

        if task_sig.elements:
            element_strs = [element_names.get(e.value, e.value) for e in task_sig.elements]
            if len(element_strs) == 1:
                parts.append(f"{element_strs[0]} focus.")
            else:
                parts.append(" + ".join(element_strs) + " focus.")
        else:
            parts[0] += "."

        return " ".join(parts) if len(parts) > 1 else parts[0]
