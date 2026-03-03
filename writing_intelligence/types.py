from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# === TRIGGER DIMENSION ENUMS ===

class Mode(str, Enum):
    DRAFTING = "drafting"
    CONTINUING = "continuing"
    REVISING = "revising"
    EXPANDING = "expanding"
    CONDENSING = "condensing"

class Register(str, Enum):
    ACTION = "action"
    DIALOGUE = "dialogue"
    INTROSPECTION = "introspection"
    DESCRIPTION = "description"
    EXPOSITION = "exposition"
    TRANSITION = "transition"

class Intensity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Position(str, Enum):
    OPENING = "opening"
    RISING = "rising"
    CLIMAX = "climax"
    FALLING = "falling"
    CLOSING = "closing"
    MID = "mid"

class Element(str, Enum):
    PHYSICAL_ACTION = "physical_action"
    DIALOGUE = "dialogue"
    INTERNAL_THOUGHT = "internal_thought"
    ENVIRONMENTAL_DESCRIPTION = "environmental_description"
    CHARACTER_DESCRIPTION = "character_description"
    EMOTIONAL_BEAT = "emotional_beat"
    SENSORY_DETAIL = "sensory_detail"


# === PATTERN ENUMS ===

class PatternCategory(str, Enum):
    FIGURATIVE_LANGUAGE = "figurative_language"
    NARRATIVE_DISTANCE = "narrative_distance"
    INFORMATION_ORDERING = "information_ordering"
    DETAIL_SELECTION = "detail_selection"
    READER_TRUST = "reader_trust"
    PACING = "pacing"
    DIALOGUE = "dialogue"
    WORD_CHOICE = "word_choice"
    STRUCTURE = "structure"
    EMOTIONAL_LOGIC = "emotional_logic"
    EMOTIONAL_RESISTANCE = "emotional_resistance"
    ENVIRONMENTAL_PRESSURE = "environmental_pressure"
    SENSORY_RESTRAINT = "sensory_restraint"
    PERFORMANCE_INTERIORITY = "performance_interiority"

class Direction(str, Enum):
    AVOID = "avoid"
    PREFER = "prefer"


# === DATACLASSES ===

@dataclass
class TaskSignature:
    mode: Mode
    register: Register
    intensity: Intensity
    position: Position
    elements: list[Element]

    def all_trigger_values(self) -> set[str]:
        """Flatten all dimension values into a set for overlap matching."""
        values = {self.mode.value, self.register.value,
                  self.intensity.value, self.position.value}
        values.update(e.value for e in self.elements)
        return values

    @classmethod
    def from_dict(cls, d: dict) -> "TaskSignature":
        """
        Build from a dict with string values. Missing keys get defaults.
        Accepts partial dicts for RP Engine integration.
        """
        return cls(
            mode=Mode(d.get("mode", "drafting")),
            register=Register(d.get("register", "description")),
            intensity=Intensity(d.get("intensity", "medium")),
            position=Position(d.get("position", "mid")),
            elements=[Element(e) for e in d.get("elements", [])],
        )


@dataclass
class CorrectionPair:
    id: str
    pattern_id: str
    original: str
    revised: str
    critique: Optional[str] = None
    extracted_rule: Optional[str] = None
    tokens_original: int = 0
    tokens_revised: int = 0
    created_at: Optional[datetime] = None


@dataclass
class Pattern:
    id: str
    category: PatternCategory
    subcategory: Optional[str]
    description: str
    direction: Direction
    severity: float = 0.5
    frequency: int = 0
    correction_count: int = 0
    proficiency: float = 0.2
    context_triggers: list[str] = field(default_factory=list)
    compressed_rule: Optional[str] = None
    created_at: Optional[datetime] = None
    last_triggered: Optional[datetime] = None
    last_corrected: Optional[datetime] = None
    # Populated at retrieval time, not stored in patterns table
    correction_pairs: list[CorrectionPair] = field(default_factory=list)


@dataclass
class ScoredPattern:
    """A Pattern with its computed retrieval score."""
    pattern: Pattern
    score: float
    relevance: float
    injection_level: str  # "critical", "moderate", "reminder", "skip"


@dataclass
class InjectionPayload:
    """The formatted text block ready for system prompt insertion."""
    text: str
    token_count: int
    patterns_included: list[str]  # pattern IDs
    task_signature: TaskSignature


@dataclass
class FeedbackInput:
    """What the caller provides when submitting feedback."""
    original_output: str
    user_feedback: Optional[str] = None
    user_rewrite: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class ExtractionResult:
    """What LLM-assisted pattern extraction returns per identified pattern."""
    category: str
    subcategory: Optional[str]
    description: str
    direction: str
    compressed_rule: str
    context_triggers: list[str]
    original_excerpt: Optional[str] = None
    revised_excerpt: Optional[str] = None
    critique_excerpt: Optional[str] = None
