"""Pydantic models for branch management."""

from __future__ import annotations

from pydantic import BaseModel


class BranchCreate(BaseModel):
    name: str
    rp_folder: str
    description: str | None = None
    branch_from: str | None = None
    branch_point_exchange: int | None = None


class BranchInfo(BaseModel):
    name: str
    rp_folder: str
    created_from: str | None = None
    branch_point_session: str | None = None
    branch_point_exchange: int | None = None
    description: str | None = None
    is_active: bool = False
    is_archived: bool = False
    created_at: str | None = None
    exchange_count: int = 0


class BranchArchiveRequest(BaseModel):
    archived: bool = True


class BranchListResponse(BaseModel):
    active_branch: str | None = None
    branches: list[BranchInfo]


class BranchSwitchRequest(BaseModel):
    name: str


class BranchSwitchResponse(BaseModel):
    active_branch: str
    previous_branch: str | None = None


class CheckpointCreate(BaseModel):
    name: str
    description: str | None = None


class CheckpointInfo(BaseModel):
    name: str
    branch: str
    exchange_number: int
    description: str | None = None
    created_at: str


class CheckpointRestoreRequest(BaseModel):
    checkpoint_name: str


class CheckpointRestoreResponse(BaseModel):
    restored_from: str
    exchange_number: int
    new_branch: str | None = None
    rewound_count: int | None = None  # deprecated, kept for backward compat
