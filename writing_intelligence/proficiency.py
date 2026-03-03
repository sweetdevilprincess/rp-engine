from datetime import datetime
from .types import Pattern
from .db import PatternDB


class ProficiencyUpdater:
    def __init__(self, db: PatternDB,
                 increment_step: float = 0.1,
                 decrement_step: float = 0.15,
                 regression_penalty: float = 0.3):
        self.db = db
        self.increment_step = increment_step
        self.decrement_step = decrement_step
        self.regression_penalty = regression_penalty

    def on_accepted(self, pattern_ids: list[str]) -> None:
        """User accepted the output without correction."""
        for pattern_id in pattern_ids:
            pattern = self.db.get_pattern(pattern_id)
            if pattern is None:
                continue
            pattern.proficiency = self._clamp(pattern.proficiency + self.increment_step)
            pattern.frequency += 1
            pattern.last_triggered = datetime.utcnow()
            self.db.update_pattern(pattern)

    def on_corrected(self, corrected_pattern_ids: list[str],
                     injected_pattern_ids: list[str]) -> None:
        """User corrected the output."""
        corrected_set = set(corrected_pattern_ids)

        for pattern_id in corrected_pattern_ids:
            pattern = self.db.get_pattern(pattern_id)
            if pattern is None:
                continue
            pattern.proficiency = self._clamp(pattern.proficiency - self.decrement_step)
            pattern.correction_count += 1
            pattern.last_corrected = datetime.utcnow()
            pattern.last_triggered = datetime.utcnow()
            self.db.update_pattern(pattern)

        # Injected but NOT corrected = LLM followed guidance, increment
        for pattern_id in injected_pattern_ids:
            if pattern_id in corrected_set:
                continue
            pattern = self.db.get_pattern(pattern_id)
            if pattern is None:
                continue
            pattern.proficiency = self._clamp(pattern.proficiency + self.increment_step)
            pattern.frequency += 1
            pattern.last_triggered = datetime.utcnow()
            self.db.update_pattern(pattern)

    def on_regression(self, pattern_id: str) -> None:
        """A high-proficiency pattern was skipped but the user corrected that issue."""
        pattern = self.db.get_pattern(pattern_id)
        if pattern is None:
            return
        pattern.proficiency = self._clamp(pattern.proficiency - self.regression_penalty)
        pattern.last_corrected = datetime.utcnow()
        pattern.correction_count += 1
        self.db.update_pattern(pattern)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
