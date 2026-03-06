"""Pydantic models for continuity checking."""

from __future__ import annotations

from pydantic import BaseModel


class ContinuityFact(BaseModel):
    """A checkable fact extracted from an exchange."""
    entity_name: str
    category: str  # location, status, possession, relationship, timeline
    claim: str
    exchange_number: int


class ContinuityWarning(BaseModel):
    """A detected contradiction between current and past claims."""
    id: int | None = None
    rp_folder: str
    branch: str = "main"
    entity_name: str
    category: str
    current_claim: str
    current_exchange: int
    past_claim: str
    past_exchange: int
    severity: str = "warning"  # info, warning, conflict
    explanation: str | None = None
    resolved: bool = False
    resolved_reason: str | None = None


class ContinuityWarningResponse(BaseModel):
    """Response for listing continuity warnings."""
    warnings: list[ContinuityWarning]
    total: int
    unresolved: int


class ResolveWarningRequest(BaseModel):
    """Request to resolve/dismiss a continuity warning."""
    reason: str  # legitimate_change, character_lied, false_positive, other
