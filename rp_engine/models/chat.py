"""Pydantic models for the chat endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_message: str
    stream: bool = False


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
