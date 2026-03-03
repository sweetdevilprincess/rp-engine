from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# === TRIGGER DIMENSION ENUMS ===

class Archetype(str, Enum):
    POWER_HOLDER = "power_holder"
    TRANSACTIONAL = "transactional"
    COMMON_PEOPLE = "common_people"
    OPPOSITION = "opposition"
    SPECIALIST = "specialist"
    PROTECTOR = "protector"
    OUTSIDER = "outsider"

class Modifier(str, Enum):
    OBSESSIVE = "obsessive"
    PARANOID = "paranoid"
    FANATICAL = "fanatical"
    NARCISSISTIC = "narcissistic"
    SADISTIC = "sadistic"
    ADDICTED = "addicted"
    HONOR_BOUND = "honor_bound"
    GRIEF_CONSUMED = "grief_consumed"
    SOCIOPATHIC = "sociopathic"

class TrustStage(str, Enum):
    HOSTILE = "hostile"
    ANTAGONISTIC = "antagonistic"
    SUSPICIOUS = "suspicious"
    WARY = "wary"
    NEUTRAL = "neutral"
    FAMILIAR = "familiar"
    TRUSTED = "trusted"
    DEVOTED = "devoted"

class InteractionType(str, Enum):
    INFORMATION_REQUEST = "information_request"
    COOPERATION_REQUEST = "cooperation_request"
    CONFRONTATION = "confrontation"
    NEGOTIATION = "negotiation"
    HOSTILE_ENCOUNTER = "hostile_encounter"
    SOCIAL_INTERACTION = "social_interaction"
    DECEPTION_ATTEMPT = "deception_attempt"

class SceneSignal(str, Enum):
    DANGER = "danger"
    COMBAT = "combat"
    EMOTIONAL = "emotional"
    INTIMATE = "intimate"
    INVESTIGATION = "investigation"
    SOCIAL = "social"


# === PATTERN ENUMS ===

class BehavioralCategory(str, Enum):
    SELF_INTEREST = "self_interest"
    ARCHETYPE_VOICE = "archetype_voice"
    TRUST_MECHANICS = "trust_mechanics"
    ESCALATION = "escalation"
    MODIFIER_FIDELITY = "modifier_fidelity"
    INTERNAL_EXTERNAL_GAP = "internal_external_gap"
    HOSTILITY_PERSISTENCE = "hostility_persistence"
    COOPERATION_CEILING = "cooperation_ceiling"
    SOCIAL_HIERARCHY = "social_hierarchy"
    HYBRID_FRICTION = "hybrid_friction"
    KNOWLEDGE_BOUNDARY = "knowledge_boundary"

class Direction(str, Enum):
    AVOID = "avoid"
    PREFER = "prefer"


# === DATACLASSES ===

@dataclass
class BehavioralSignature:
    archetype: Archetype
    modifiers: list[Modifier]
    trust_stage: TrustStage
    interaction_type: InteractionType
    scene_signals: list[SceneSignal]

    def all_trigger_values(self) -> set[str]:
        """Flatten all dimension values into a set for overlap matching."""
        values = {self.archetype.value, self.trust_stage.value,
                  self.interaction_type.value}
        values.update(m.value for m in self.modifiers)
        values.update(s.value for s in self.scene_signals)
        return values

    @classmethod
    def from_dict(cls, d: dict) -> "BehavioralSignature":
        """
        Build from a dict with string values. Missing keys get defaults.
        Accepts partial dicts for RP Engine integration.
        """
        return cls(
            archetype=Archetype(d.get("archetype", "common_people")),
            modifiers=[Modifier(m) for m in d.get("modifiers", [])],
            trust_stage=TrustStage(d.get("trust_stage", "neutral")),
            interaction_type=InteractionType(d.get("interaction_type", "social_interaction")),
            scene_signals=[SceneSignal(s) for s in d.get("scene_signals", [])],
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
    category: BehavioralCategory
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
    behavioral_signature: BehavioralSignature
    npc_name: str = ""


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
