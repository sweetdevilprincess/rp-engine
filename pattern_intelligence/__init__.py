"""Shared base classes for pattern intelligence systems.

Both npc_intelligence and writing_intelligence subclass from these bases.
"""

from .types import (
    CorrectionPair,
    Direction,
    ExtractionResult,
    FeedbackInput,
    Pattern,
    ScoredPattern,
)
from .db import BasePatternDB
from .engine import BasePatternIntelligence
from .injection import BaseInjectionFormatter
from .feedback import BaseFeedbackProcessor

__all__ = [
    # Types
    "CorrectionPair",
    "Direction",
    "ExtractionResult",
    "FeedbackInput",
    "Pattern",
    "ScoredPattern",
    # Base classes
    "BasePatternDB",
    "BasePatternIntelligence",
    "BaseInjectionFormatter",
    "BaseFeedbackProcessor",
]
