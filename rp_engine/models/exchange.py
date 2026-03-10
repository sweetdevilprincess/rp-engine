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
    has_variants: bool = False
    variant_count: int = 0
    continue_count: int = 0
    is_bookmarked: bool = False
    bookmark_name: str | None = None
    has_annotations: bool = False
    annotation_count: int = 0


class ExchangeListResponse(BaseModel):
    exchanges: list[ExchangeDetail]
    total_count: int


# --- Search ---

class ExchangeSearchHit(BaseModel):
    exchange_number: int
    exchange_id: int
    user_message_snippet: str
    assistant_response_snippet: str
    relevance_score: float
    timestamp: str
    session_id: str | None = None
    npcs_mentioned: list[str] | None = None
    is_bookmarked: bool = False
    bookmark_name: str | None = None
    annotation_count: int = 0


class ExchangeSearchResponse(BaseModel):
    query: str
    mode: str
    total_results: int
    results: list[ExchangeSearchHit]


# --- Bookmarks ---

class BookmarkCreate(BaseModel):
    name: str | None = None
    note: str | None = None
    color: str = "default"


class BookmarkUpdate(BaseModel):
    name: str | None = None
    note: str | None = None
    color: str | None = None


class BookmarkResponse(BaseModel):
    id: int
    exchange_number: int
    exchange_id: int
    name: str
    note: str | None = None
    color: str = "default"
    created_at: str


class BookmarkListResponse(BaseModel):
    bookmarks: list[BookmarkResponse]
    total_count: int


# --- Annotations ---

class AnnotationCreate(BaseModel):
    content: str
    annotation_type: str = "note"
    include_in_context: bool = False


class AnnotationUpdate(BaseModel):
    content: str | None = None
    annotation_type: str | None = None
    include_in_context: bool | None = None


class AnnotationResponse(BaseModel):
    id: int
    exchange_number: int
    exchange_id: int
    content: str
    annotation_type: str = "note"
    include_in_context: bool = False
    resolved: bool = False
    created_at: str
    updated_at: str | None = None


class AnnotationListResponse(BaseModel):
    annotations: list[AnnotationResponse]
    total_count: int
