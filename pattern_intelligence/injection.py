"""Base injection formatter — shared pattern formatting and token budget logic.

Subclasses override:
- _build_header(): domain-specific header string
- _build_wrapper(): opening/closing lines and context prefix
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Callable, Optional

from .types import Pattern, ScoredPattern


class BaseInjectionFormatter:
    """Shared injection formatting logic: token budget, section assembly, level formatting."""

    HEADER_OVERHEAD = 80
    SECTION_HEADER = 15

    SECTION_LABELS = {
        "critical": "CRITICAL (low proficiency):",
        "moderate": "MODERATE (rising proficiency):",
        "reminder": "REMINDER (high proficiency):",
    }

    def __init__(self, token_budget: int = 500,
                 count_tokens: Optional[Callable[[str], int]] = None):
        from rp_engine.utils.token_utils import default_token_counter
        self._count = count_tokens or default_token_counter
        self.token_budget = token_budget

    def format(self, scored_patterns: list[ScoredPattern], signature: Any, **kwargs: Any) -> Any:
        """Format scored patterns into an injection payload.

        Subclasses call this via super() or override to add domain-specific fields.
        """
        header = self._build_header(signature, **kwargs)
        remaining = self.token_budget - self.HEADER_OVERHEAD

        sorted_patterns = sorted(scored_patterns, key=lambda sp: sp.score, reverse=True)

        sections: dict[str, list[str]] = {"critical": [], "moderate": [], "reminder": []}
        included_ids: list[str] = []

        for sp in sorted_patterns:
            level = sp.injection_level
            text = self._format_at_level(sp.pattern, level)
            cost = self._count(text)

            if cost <= remaining:
                sections[level].append(text)
                included_ids.append(sp.pattern.id)
                remaining -= cost
            elif level == "critical":
                text = self._format_moderate(sp.pattern)
                cost = self._count(text)
                if cost <= remaining:
                    sections["moderate"].append(text)
                    included_ids.append(sp.pattern.id)
                    remaining -= cost

        open_tag, context_prefix, close_tag = self._build_wrapper(signature, **kwargs)
        lines = [open_tag, "", f"{context_prefix}{header}", ""]

        for level in ["critical", "moderate", "reminder"]:
            if sections[level]:
                lines.append(self.SECTION_LABELS[level])
                lines.extend(sections[level])
                lines.append("")

        lines.append(close_tag)

        full_text = "\n".join(lines)
        actual_tokens = self._count(full_text)

        return full_text, actual_tokens, included_ids

    # --- Level formatting (shared) ---

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

    # --- Subclass hooks ---

    @abstractmethod
    def _build_header(self, signature: Any, **kwargs: Any) -> str:
        """Build the context header string from the domain signature."""
        ...

    @abstractmethod
    def _build_wrapper(self, signature: Any, **kwargs: Any) -> tuple[str, str, str]:
        """Return (opening_tag, context_prefix, closing_tag)."""
        ...
