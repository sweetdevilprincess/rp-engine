"""Pydantic models for the chat endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class SceneOverride(BaseModel):
    location: str | None = None
    mood: str | None = None


class ChatRequest(BaseModel):
    user_message: str
    stream: bool = False
    ooc: bool = False
    attach_card_ids: list[str] = []
    scene_override: SceneOverride | None = None


class ChatResponse(BaseModel):
    response: str
    exchange_id: int
    exchange_number: int
    session_id: str
    context_summary: dict | None = None


class ChatStreamEvent(BaseModel):
    type: str  # "token", "done", "error"
    content: str | None = None
    exchange_id: int | None = None
    exchange_number: int | None = None


# --- Regenerate / Swipe ---

class RegenerateRequest(BaseModel):
    exchange_number: int | None = None  # defaults to latest
    temperature: float | None = None
    model: str | None = None
    stream: bool = False


class RegenerateResponse(BaseModel):
    response: str
    exchange_id: int
    exchange_number: int
    session_id: str
    variant_id: int
    variant_index: int
    total_variants: int


class SwipeRequest(BaseModel):
    exchange_number: int
    variant_index: int


class SwipeResponse(BaseModel):
    exchange_number: int
    active_variant: int
    total_variants: int
    response: str


class VariantInfo(BaseModel):
    id: int
    variant_index: int
    is_active: bool
    model_used: str | None = None
    temperature: float | None = None
    continue_count: int = 0
    created_at: str


class VariantsResponse(BaseModel):
    exchange_number: int
    exchange_id: int
    variants: list[VariantInfo]
    total: int


# --- Continue ---

class ContinueRequest(BaseModel):
    exchange_number: int | None = None  # defaults to latest
    max_tokens: int | None = None
    stream: bool = False


class ContinueResponse(BaseModel):
    continuation: str
    full_response: str
    exchange_id: int
    exchange_number: int
    session_id: str
    continue_count: int
