"""Pydantic models for the context engine pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from rp_engine.models.npc import NPCReaction
from rp_engine.models.rp import GuidelinesResponse

# ---------------------------------------------------------------------------
# API Request / Response
# ---------------------------------------------------------------------------


class ContextRequest(BaseModel):
    user_message: str
    last_response: str | None = None
    include_npc_reactions: bool = True


class ContextDocument(BaseModel):
    name: str
    card_type: str
    file_path: str
    source: Literal["keyword", "semantic", "graph", "trigger", "always_load"]
    relevance_score: float
    content: str | None = None
    summary: str | None = None
    status: Literal["new", "updated"]


class ContextReference(BaseModel):
    name: str
    card_type: str
    status: Literal["already_loaded"] = "already_loaded"
    sent_at_turn: int


class NPCBrief(BaseModel):
    character: str
    importance: str | None = None
    archetype: str | None = None
    secondary_archetype: str | None = None
    behavioral_modifiers: list[str] = []
    trust_score: int = 0
    trust_stage: str | None = None
    emotional_state: str | None = None
    conditions: list[str] = []
    behavioral_direction: str = ""
    scene_signals: list[str] = []


class FlaggedNPC(BaseModel):
    character: str
    importance: str | None = None
    reason: str


class SceneState(BaseModel):
    location: str | None = None
    time_of_day: str | None = None
    mood: str | None = None
    in_story_timestamp: str | None = None


class CharacterState(BaseModel):
    location: str | None = None
    conditions: list[str] = []
    emotional_state: str | None = None


class ThreadAlert(BaseModel):
    thread_id: str
    name: str
    level: Literal["gentle", "moderate", "strong"]
    counter: int
    threshold: int
    consequence: str


class TriggeredNote(BaseModel):
    trigger_id: str
    trigger_name: str
    inject_type: Literal["context_note", "state_alert"]
    content: str
    priority: int = 0
    signals_matched: list[str] = []


class CardGap(BaseModel):
    entity_name: str
    seen_count: int
    suggested_type: str | None = None


class StalenessWarning(BaseModel):
    type: str = "stale_analysis"
    exchange: int
    failed_at: str
    stale_fields: list[str] = []


class WritingConstraints(BaseModel):
    text: str
    patterns_included: list[str] = []
    task_context: str = ""
    token_count: int = 0


class ContextResponse(BaseModel):
    current_exchange: int
    documents: list[ContextDocument] = []
    references: list[ContextReference] = []
    npc_briefs: list[NPCBrief] = []
    npc_reactions: list[NPCReaction] = []
    flagged_npcs: list[FlaggedNPC] = []
    guidelines: GuidelinesResponse | None = None
    scene_state: SceneState = SceneState()
    character_states: dict[str, CharacterState] = {}
    thread_alerts: list[ThreadAlert] = []
    triggered_notes: list[TriggeredNote] = []
    card_gaps: list[CardGap] = []
    warnings: list[StalenessWarning] = []
    writing_constraints: WritingConstraints | None = None


# ---------------------------------------------------------------------------
# Internal Types (used between services, not in API response)
# ---------------------------------------------------------------------------


class MatchedEntity(BaseModel):
    entity_id: str
    match_source: Literal["alias", "keyword", "name"]
    match_term: str
    score: float  # name=1.0, alias=0.8, keyword=0.5


class DetectedNPC(BaseModel):
    entity_id: str
    name: str
    detection_reason: str


class ExtractionResult(BaseModel):
    matched_entities: list[MatchedEntity] = []
    active_npcs: list[DetectedNPC] = []
    referenced_npcs: list[DetectedNPC] = []
    detected_locations: list[str] = []


# ---------------------------------------------------------------------------
# Graph resolution request (for /api/context/resolve)
# ---------------------------------------------------------------------------


class ResolveRequest(BaseModel):
    scene_description: str
    keywords: list[str] = []
    max_hops: int = 2
    max_results: int = 15
