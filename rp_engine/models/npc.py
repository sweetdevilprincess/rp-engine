"""Pydantic models for NPC reactions, trust, and listing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from rp_engine.models.enums import Archetype, BehavioralModifier


class TrustShift(BaseModel):
    direction: Literal["increase", "decrease", "neutral"]
    amount: int = 0
    reason: str | None = None


class NPCReaction(BaseModel):
    character: str
    internalMonologue: str
    physicalAction: str
    dialogue: str | None = None
    emotionalUndercurrent: str
    trustShift: TrustShift


class NPCReactRequest(BaseModel):
    npc_name: str
    scene_prompt: str
    pov_character: str | None = None
    model_override: str | None = None


class NPCBatchRequest(BaseModel):
    npc_names: list[str]
    scene_prompt: str
    pov_character: str | None = None


class TrustEvent(BaseModel):
    date: str
    change: int
    direction: str
    reason: str | None = None


class TrustInfo(BaseModel):
    npc_name: str
    target: str
    trust_score: int
    trust_stage: str
    session_gains: int
    session_losses: int
    history: list[TrustEvent]


class NPCListItem(BaseModel):
    name: str
    importance: str | None = None
    primary_archetype: Archetype | None = None
    secondary_archetype: Archetype | None = None
    behavioral_modifiers: list[BehavioralModifier] = []
    trust_score: int = 0
    trust_stage: str = "neutral"
    location: str | None = None
    emotional_state: str | None = None
