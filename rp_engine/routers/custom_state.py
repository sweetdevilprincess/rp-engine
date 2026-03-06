"""Custom state API — manage custom tracked fields and their values."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException

logger = logging.getLogger(__name__)

from rp_engine.dependencies import get_custom_state_manager
from rp_engine.models.custom_state import (
    CustomStateSchema,
    CustomStateSchemaCreate,
    CustomStateSet,
    CustomStateSnapshot,
    CustomStateValue,
    PresetInfo,
)
from rp_engine.services.custom_state_manager import CustomStateManager

router = APIRouter(prefix="/api/custom-state", tags=["custom-state"])


@router.get("/schemas", response_model=list[CustomStateSchema])
async def list_schemas(
    rp_folder: str = Query(...),
    mgr: CustomStateManager = Depends(get_custom_state_manager),
):
    return await mgr.list_schemas(rp_folder)


@router.post("/schemas", response_model=CustomStateSchema)
async def create_schema(
    body: CustomStateSchemaCreate,
    mgr: CustomStateManager = Depends(get_custom_state_manager),
):
    schema = CustomStateSchema(**body.model_dump())
    return await mgr.create_schema(schema, body.rp_folder)


@router.delete("/schemas/{schema_id}")
async def delete_schema(
    schema_id: str,
    rp_folder: str = Query(...),
    mgr: CustomStateManager = Depends(get_custom_state_manager),
):
    await mgr.delete_schema(schema_id, rp_folder)
    return {"deleted": True}


@router.get("", response_model=CustomStateSnapshot)
async def get_all_state(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    mgr: CustomStateManager = Depends(get_custom_state_manager),
):
    return await mgr.get_snapshot(rp_folder, branch)


@router.get("/{schema_id}", response_model=CustomStateValue | None)
async def get_value(
    schema_id: str,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    entity_id: str | None = Query(None),
    mgr: CustomStateManager = Depends(get_custom_state_manager),
):
    return await mgr.get_value(schema_id, rp_folder, branch, entity_id)


@router.post("/{schema_id}", response_model=CustomStateValue)
async def set_value(
    schema_id: str,
    body: CustomStateSet,
    mgr: CustomStateManager = Depends(get_custom_state_manager),
):
    return await mgr.set_value(
        schema_id=schema_id,
        value=body.value,
        rp_folder=body.rp_folder,
        branch=body.branch,
        entity_id=body.entity_id,
        reason=body.reason,
    )


@router.get("/presets/list", response_model=list[PresetInfo])
async def list_presets(
    mgr: CustomStateManager = Depends(get_custom_state_manager),
):
    return mgr.list_presets()


@router.post("/presets/{preset_name}/apply", response_model=list[CustomStateSchema])
async def apply_preset(
    preset_name: str,
    rp_folder: str = Query(...),
    mgr: CustomStateManager = Depends(get_custom_state_manager),
):
    try:
        return await mgr.apply_preset(preset_name, rp_folder)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
