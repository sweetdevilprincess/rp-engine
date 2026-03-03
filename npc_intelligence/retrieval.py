from datetime import datetime
from .types import Pattern, ScoredPattern, BehavioralSignature
from .db import BehavioralPatternDB


class BehavioralRetriever:
    def __init__(self, db: BehavioralPatternDB, recency_window_days: float = 7.0):
        self.db = db
        self.recency_window_days = recency_window_days

    def retrieve(self, behavioral_sig: BehavioralSignature, max_results: int = 20) -> list[ScoredPattern]:
        trigger_values = behavioral_sig.all_trigger_values()
        patterns = self.db.get_patterns_by_triggers(trigger_values)

        scored = []
        for pattern in patterns:
            relevance = self._compute_relevance(pattern, trigger_values)
            recency_boost = self._compute_recency_boost(pattern)
            injection_level = self._assign_injection_level(pattern.proficiency)

            score = (relevance * 0.3
                     + pattern.severity * 0.3
                     + (1 - pattern.proficiency) * 0.25
                     + recency_boost * 0.15)

            scored.append(ScoredPattern(
                pattern=pattern,
                score=score,
                relevance=relevance,
                injection_level=injection_level,
            ))

        # Filter out "skip" patterns
        scored = [sp for sp in scored if sp.injection_level != "skip"]
        # Sort by score descending
        scored.sort(key=lambda sp: sp.score, reverse=True)
        return scored[:max_results]

    def _compute_relevance(self, pattern: Pattern, trigger_values: set[str]) -> float:
        if not pattern.context_triggers:
            return 0.0
        overlap = len(set(pattern.context_triggers) & trigger_values)
        return overlap / len(pattern.context_triggers)

    def _compute_recency_boost(self, pattern: Pattern) -> float:
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
