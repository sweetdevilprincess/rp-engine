"""Branch management endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.dependencies import get_branch_manager
from rp_engine.models.branch import (
    BranchCreate,
    BranchInfo,
    BranchListResponse,
    BranchSwitchRequest,
    BranchSwitchResponse,
    CheckpointCreate,
    CheckpointInfo,
    CheckpointRestoreRequest,
    CheckpointRestoreResponse,
)
from rp_engine.services.branch_manager import BranchManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/branches", tags=["branches"])


@router.get("", response_model=BranchListResponse)
async def list_branches(
    rp_folder: str = Query(...),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """List all branches for an RP folder."""
    return await branch_manager.list_branches(rp_folder)


@router.post("", response_model=BranchInfo, status_code=201)
async def create_branch(
    body: BranchCreate,
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """Create a new branch by snapshotting state from a source branch."""
    try:
        return await branch_manager.create_branch(
            name=body.name,
            rp_folder=body.rp_folder,
            description=body.description,
            branch_from=body.branch_from,
        )
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            raise HTTPException(409, detail=msg) from None
        if "not found" in msg:
            raise HTTPException(404, detail=msg) from None
        raise HTTPException(400, detail=msg) from None


@router.put("/active", response_model=BranchSwitchResponse)
async def switch_branch(
    body: BranchSwitchRequest,
    rp_folder: str = Query(...),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """Switch the active branch for an RP folder."""
    try:
        previous = await branch_manager.switch_branch(body.name, rp_folder)
        return BranchSwitchResponse(
            active_branch=body.name,
            previous_branch=previous,
        )
    except ValueError as e:
        raise HTTPException(404, detail=str(e)) from None


@router.get("/{name}", response_model=BranchInfo)
async def get_branch(
    name: str,
    rp_folder: str = Query(...),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """Get details for a specific branch."""
    try:
        return await branch_manager.get_branch(name, rp_folder)
    except ValueError as e:
        raise HTTPException(404, detail=str(e)) from None


@router.post("/{name}/checkpoint", response_model=CheckpointInfo, status_code=201)
async def create_checkpoint(
    name: str,
    body: CheckpointCreate,
    rp_folder: str = Query(...),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """Create a named checkpoint on a branch."""
    try:
        return await branch_manager.create_checkpoint(
            name=body.name,
            rp_folder=rp_folder,
            branch=name,
            description=body.description,
        )
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            raise HTTPException(409, detail=msg) from None
        raise HTTPException(400, detail=msg) from None


@router.get("/{name}/checkpoints", response_model=list[CheckpointInfo])
async def list_checkpoints(
    name: str,
    rp_folder: str = Query(...),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """List all checkpoints on a branch."""
    return await branch_manager.list_checkpoints(rp_folder, name)


@router.post("/{name}/restore", response_model=CheckpointRestoreResponse)
async def restore_checkpoint(
    name: str,
    body: CheckpointRestoreRequest,
    rp_folder: str = Query(...),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """Restore to a checkpoint by creating a new branch from that point.

    Append-only: the old timeline remains intact and accessible.
    """
    try:
        return await branch_manager.restore_checkpoint(
            checkpoint_name=body.checkpoint_name,
            rp_folder=rp_folder,
            branch=name,
        )
    except ValueError as e:
        raise HTTPException(404, detail=str(e)) from None
