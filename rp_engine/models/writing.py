"""Pydantic models for writing intelligence endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class WritingFeedbackBody(BaseModel):
    original_output: str
    user_feedback: str | None = None
    user_rewrite: str | None = None
    accepted: bool = True
