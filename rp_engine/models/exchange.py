"""Pydantic models for exchange (chat message) storage."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator


class ExchangeSave(BaseModel):
    user_message: str
    assistant_response: str
    exchange_number: int | None = None
    idempotency_key: str | None = None
    parent_exchange_number: int | None = None
    session_id: str | None = None
    in_story_timestamp: str | None = None
    location: str | None = None
    metadata: dict | None = None

    @field_validator("assistant_response")
    @classmethod
    def validate_no_meta_content(cls, v: str) -> str:
        if re.search(r"<thinking>", v, re.IGNORECASE):
            raise ValueError("Response contains <thinking> tags. Strip before saving.")
        if re.search(r'\{"tool_calls":', v):
            raise ValueError("Response contains tool call blocks. Strip before saving.")
        if re.search(r"<system-reminder>", v, re.IGNORECASE):
            raise ValueError("Response contains system instructions. Strip before saving.")
        return v


class ExchangeResponse(BaseModel):
    id: int
    exchange_number: int
    session_id: str
    created_at: str
    analysis_status: str = "pending"
    rewound_count: int | None = None
    idempotent_hit: bool | None = None


class ExchangeDetail(BaseModel):
    id: int
    exchange_number: int
    session_id: str
    user_message: str
    assistant_response: str
    in_story_timestamp: str | None = None
    location: str | None = None
    npcs_involved: list[str] | None = None
    analysis_status: str = "pending"
    created_at: str
    metadata: dict | None = None


class ExchangeListResponse(BaseModel):
    exchanges: list[ExchangeDetail]
    total_count: int
