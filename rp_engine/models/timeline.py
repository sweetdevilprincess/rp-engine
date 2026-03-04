"""Timeline view models."""

from __future__ import annotations

from pydantic import BaseModel


class TimelineExchange(BaseModel):
    exchange_number: int
    user_snippet: str
    assistant_snippet: str
    in_story_timestamp: str | None = None
    created_at: str | None = None
    session_id: str | None = None


class TimelineBranch(BaseModel):
    name: str
    created_from: str | None = None
    branch_point: int | None = None
    is_active: bool = False
    exchange_count: int = 0
    exchanges: list[TimelineExchange] = []


class DivergencePoint(BaseModel):
    exchange_number: int
    branches: list[str]


class TimelineResponse(BaseModel):
    rp_folder: str
    branches: list[TimelineBranch]
    divergence_points: list[DivergencePoint]
