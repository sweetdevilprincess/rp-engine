"""Shared pattern retrieval for intelligence packages.

Both npc_intelligence and writing_intelligence use identical scoring,
relevance computation, recency boosting, and injection level assignment.
This module provides the shared implementation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class PatternLike(Protocol):
    """Minimal interface for a retrievable pattern."""
    context_triggers: list[str]
    severity: float
    proficiency: float
    last_corrected: datetime | None


class ScoredPatternLike(Protocol):
    """Minimal interface for a scored pattern result."""
    injection_level: str
    score: float


class PatternDBLike(Protocol):
    """Minimal interface for a pattern database with trigger lookup."""
    def get_patterns_by_triggers(self, trigger_values: set[str]) -> list: ...


class SignatureLike(Protocol):
    """Minimal interface for a signature (BehavioralSignature or TaskSignature)."""
    def all_trigger_values(self) -> set[str]: ...


class BasePatternRetriever:
    """Shared retrieval logic for both intelligence packages.

    Subclasses should provide their own `retrieve` method that calls
    `_score_and_rank` with the appropriate ScoredPattern constructor.
    """

    def __init__(self, db: PatternDBLike, recency_window_days: float = 7.0):
        self.db = db
        self.recency_window_days = recency_window_days

    def _score_patterns(self, patterns: list, trigger_values: set[str]) -> list[dict]:
        """Score patterns and return dicts with score, relevance, injection_level."""
        results = []
        for pattern in patterns:
            relevance = self._compute_relevance(pattern, trigger_values)
            recency_boost = self._compute_recency_boost(pattern)
            injection_level = self._assign_injection_level(pattern.proficiency)

            score = (relevance * 0.3
                     + pattern.severity * 0.3
                     + (1 - pattern.proficiency) * 0.25
                     + recency_boost * 0.15)

            if injection_level != "skip":
                results.append({
                    "pattern": pattern,
                    "score": score,
                    "relevance": relevance,
                    "injection_level": injection_level,
                })

        results.sort(key=lambda d: d["score"], reverse=True)
        return results

    def _compute_relevance(self, pattern: PatternLike, trigger_values: set[str]) -> float:
        if not pattern.context_triggers:
            return 0.0
        overlap = len(set(pattern.context_triggers) & trigger_values)
        return overlap / len(pattern.context_triggers)

    def _compute_recency_boost(self, pattern: PatternLike) -> float:
        if pattern.last_corrected is None:
            return 0.0
        days_ago = (datetime.utcnow() - pattern.last_corrected).total_seconds() / 86400
        if days_ago <= 1.0:
            return 1.0
        if days_ago >= self.recency_window_days:
            return 0.0
        return max(0.0, 1.0 - (days_ago - 1.0) / (self.recency_window_days - 1.0))

    def _assign_injection_level(self, proficiency: float) -> str:
        if proficiency < 0.4:
            return "critical"
        elif proficiency < 0.7:
            return "moderate"
        elif proficiency < 0.9:
            return "reminder"
        else:
            return "skip"
