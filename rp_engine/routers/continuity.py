"""Continuity warning endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.dependencies import get_continuity_checker
from rp_engine.models.continuity import (
    ContinuityWarningResponse,
    ResolveWarningRequest,
)
from rp_engine.services.continuity_checker import ContinuityChecker

router = APIRouter(prefix="/api/continuity", tags=["continuity"])


@router.get("/warnings", response_model=ContinuityWarningResponse)
async def list_warnings(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    resolved: bool | None = Query(None),
    checker: ContinuityChecker | None = Depends(get_continuity_checker),
):
    """List continuity warnings, optionally filtered by resolved status."""
    if not checker:
        raise HTTPException(status_code=501, detail="Continuity checker not available")

    warnings = await checker.get_warnings(rp_folder, branch, resolved)
    unresolved = sum(1 for w in warnings if not w.resolved) if resolved is None else (
        0 if resolved else len(warnings)
    )

    return ContinuityWarningResponse(
        warnings=warnings,
        total=len(warnings),
        unresolved=unresolved,
    )


@router.post("/warnings/{warning_id}/resolve")
async def resolve_warning(
    warning_id: int,
    body: ResolveWarningRequest,
    checker: ContinuityChecker | None = Depends(get_continuity_checker),
):
    """Resolve/dismiss a continuity warning."""
    if not checker:
        raise HTTPException(status_code=501, detail="Continuity checker not available")

    await checker.resolve_warning(warning_id, body.reason)
    return {"status": "resolved", "warning_id": warning_id, "reason": body.reason}
