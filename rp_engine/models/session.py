"""Pydantic models for session management."""

from __future__ import annotations

from pydantic import BaseModel


class SessionCreate(BaseModel):
    rp_folder: str
    branch: str = "main"


class SessionResponse(BaseModel):
    id: str
    rp_folder: str
    branch: str
    started_at: str
    ended_at: str | None = None
    metadata: dict | None = None


class TrustChange(BaseModel):
    npc: str
    delta: int
    reason: str


class NewEntity(BaseModel):
    name: str
    type: str
    first_mention_exchange: int | None = None


class RelationshipArc(BaseModel):
    characters: list[str]
    arc_summary: str


class CharacterStateChange(BaseModel):
    character: str
    field: str
    old_value: str | None = None
    new_value: str | None = None


class SceneProgression(BaseModel):
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    locations_visited: list[str] = []


class PlotThreadStatus(BaseModel):
    thread_id: str
    name: str
    start_counter: int = 0
    end_counter: int = 0


class SessionEndSummary(BaseModel):
    significant_events: list[str] = []
    trust_changes: list[TrustChange] = []
    new_entities: list[NewEntity] = []
    relationship_arcs: list[RelationshipArc] = []
    character_state_changes: list[CharacterStateChange] = []
    scene_progression: SceneProgression | None = None
    plot_thread_status: list[PlotThreadStatus] = []


class SessionEndResponse(BaseModel):
    session: SessionResponse
    summary: SessionEndSummary
