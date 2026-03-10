"""Pydantic models for state management endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from rp_engine.models.context import SceneState

# ---------------------------------------------------------------------------
# Character models
# ---------------------------------------------------------------------------


class CharacterDetail(BaseModel):
    name: str
    card_path: str | None = None
    is_player_character: bool = False
    importance: str | None = None
    primary_archetype: str | None = None
    secondary_archetype: str | None = None
    behavioral_modifiers: list[str] = []
    location: str | None = None
    conditions: list[str] = []
    emotional_state: str | None = None
    last_seen: str | None = None
    updated_at: str | None = None


class CharacterUpdate(BaseModel):
    location: str | None = None
    conditions: list[str] | None = None
    emotional_state: str | None = None
    last_seen: str | None = None


class CharacterListResponse(BaseModel):
    characters: dict[str, CharacterDetail]


# ---------------------------------------------------------------------------
# Relationship / Trust models
# ---------------------------------------------------------------------------


class TrustModification(BaseModel):
    date: str | None = None
    change: int
    direction: str
    reason: str | None = None
    exchange_id: int | None = None
    branch: str | None = None
    exchange_number: int | None = None


class RelationshipDetail(BaseModel):
    character_a: str
    character_b: str
    initial_trust_score: int = 0
    trust_modification_sum: int = 0
    live_trust_score: int = 0
    trust_stage: str = "neutral"
    dynamic: str | None = None
    modifications: list[TrustModification] = []


class RelationshipUpdate(BaseModel):
    trust_change: int
    reason: str
    direction: str = "neutral"
    exchange_id: int | None = None


class RelationshipListResponse(BaseModel):
    relationships: list[RelationshipDetail]


# ---------------------------------------------------------------------------
# Scene models (SceneState reused from context.py for responses)
# ---------------------------------------------------------------------------


class SceneUpdate(BaseModel):
    location: str | None = None
    time_of_day: str | None = None
    mood: str | None = None
    in_story_timestamp: str | None = None


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


class EventDetail(BaseModel):
    id: int
    in_story_timestamp: str | None = None
    event: str
    characters: list[str] = []
    significance: str | None = None
    exchange_id: int | None = None
    created_at: str | None = None


class EventCreate(BaseModel):
    event: str
    characters: list[str] = []
    significance: str = "medium"
    in_story_timestamp: str | None = None


class EventListResponse(BaseModel):
    events: list[EventDetail]


# ---------------------------------------------------------------------------
# Full state snapshot
# ---------------------------------------------------------------------------


class StateSnapshot(BaseModel):
    characters: dict[str, CharacterDetail] = {}
    relationships: list[RelationshipDetail] = []
    scene: SceneState = SceneState()
    events: list[EventDetail] = []
    session: dict | None = None
    branch: str = "main"


# ---------------------------------------------------------------------------
# Relationship Graph models
# ---------------------------------------------------------------------------


class RelGraphNode(BaseModel):
    name: str
    is_player_character: bool = False
    importance: str | None = None
    primary_archetype: str | None = None
    trust_score: int = 0
    trust_stage: str = "neutral"
    emotional_state: str | None = None
    location: str | None = None


class RelGraphEdge(BaseModel):
    from_char: str
    to_char: str
    trust_score: int = 0
    trust_stage: str = "neutral"
    dynamic: str | None = None
    trend: str = "stable"
    modification_count: int = 0


class RelGraphMetadata(BaseModel):
    total_npcs: int = 0
    total_edges: int = 0


class RelationshipGraphResponse(BaseModel):
    nodes: list[RelGraphNode]
    edges: list[RelGraphEdge]
    metadata: RelGraphMetadata
