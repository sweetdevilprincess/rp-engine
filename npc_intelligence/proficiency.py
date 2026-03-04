"""NPC behavioral proficiency updater — delegates to shared implementation."""
from rp_engine.utils.proficiency import BaseProficiencyUpdater
from .db import BehavioralPatternDB


class ProficiencyUpdater(BaseProficiencyUpdater):
    """NPC-specific proficiency updater (type alias for the shared base)."""

    def __init__(self, db: BehavioralPatternDB,
                 increment_step: float = 0.1,
                 decrement_step: float = 0.15,
                 regression_penalty: float = 0.3):
        super().__init__(db, increment_step, decrement_step, regression_penalty)
