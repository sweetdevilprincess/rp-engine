"""Pydantic models for situational trigger management."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class TriggerCondition(BaseModel):
    type: Literal["expression", "state", "signal"]
    expr: str | None = None
    path: str | None = None
    operator: str | None = None
    value: Any | None = None
    values: list[Any] | None = None
    signal: str | None = None


class TriggerCreate(BaseModel):
    name: str
    description: str | None = None
    rp_folder: str
    inject_type: Literal["context_note", "card_reference", "state_alert"]
    inject_content: str | None = None
    inject_card_path: str | None = None
    conditions: list[TriggerCondition]
    match_mode: Literal["any", "all"] = "any"
    priority: int = 0
    cooldown_turns: int = 0


class TriggerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    inject_type: Literal["context_note", "card_reference", "state_alert"] | None = None
    inject_content: str | None = None
    inject_card_path: str | None = None
    conditions: list[TriggerCondition] | None = None
    match_mode: Literal["any", "all"] | None = None
    priority: int | None = None
    cooldown_turns: int | None = None
    enabled: bool | None = None


class TriggerResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    rp_folder: str
    inject_type: str
    inject_content: str | None = None
    inject_card_path: str | None = None
    conditions: list[TriggerCondition] = []
    match_mode: str = "any"
    priority: int = 0
    cooldown_turns: int = 0
    last_fired_turn: int | None = None
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class TriggerTestRequest(BaseModel):
    trigger_id: str
    sample_text: str


class ConditionResult(BaseModel):
    condition_index: int
    condition_type: str
    matched: bool
    detail: str


class TriggerTestResult(BaseModel):
    would_fire: bool
    conditions_evaluated: list[ConditionResult] = []
    signals: dict[str, float] = {}
