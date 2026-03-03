"""Pydantic models for story card operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class StoryCardSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    card_type: str
    importance: str | None = None
    file_path: str
    summary: str | None = None
    aliases: list[str] = []
    tags: list[str] = []


class EntityConnection(BaseModel):
    to_entity: str
    connection_type: str
    field: str | None = None
    role: str | None = None


class StoryCardDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    card_type: str
    file_path: str
    importance: str | None = None
    frontmatter: dict[str, Any]
    content: str
    connections: list[EntityConnection] = []


class StoryCardCreate(BaseModel):
    name: str
    frontmatter: dict[str, Any] = {}
    content: str = ""


class StoryCardUpdate(BaseModel):
    frontmatter: dict[str, Any] | None = None
    content: str | None = None


class CardListResponse(BaseModel):
    cards: list[StoryCardSummary]
    total: int


class ReindexResponse(BaseModel):
    entities: int
    connections: int
    aliases: int
    keywords: int
    duration_ms: float
