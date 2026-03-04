"""Custom state API — manage custom tracked fields and their values."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.exceptions import HTTPException

from rp_engine.models.custom_state import (
    CustomStateSchema,
    CustomStateSchemaCreate,
    CustomStateSet,
    CustomStateSnapshot,
    CustomStateValue,
    PresetInfo,
)

router = APIRouter(prefix="/api/custom-state", tags=["custom-state"])


@router.get("/schemas", response_model=list[CustomStateSchema])
async def list_schemas(request: Request, rp_folder: str = Query(...)):
    mgr = request.app.state.custom_state_manager
    return await mgr.list_schemas(rp_folder)


@router.post("/schemas", response_model=CustomStateSchema)
async def create_schema(request: Request, body: CustomStateSchemaCreate):
    mgr = request.app.state.custom_state_manager
    schema = CustomStateSchema(**body.model_dump())
    return await mgr.create_schema(schema, body.rp_folder)


@router.delete("/schemas/{schema_id}")
async def delete_schema(request: Request, schema_id: str, rp_folder: str = Query(...)):
    mgr = request.app.state.custom_state_manager
    await mgr.delete_schema(schema_id, rp_folder)
    return {"deleted": True}


@router.get("", response_model=CustomStateSnapshot)
async def get_all_state(
    request: Request,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
):
    mgr = request.app.state.custom_state_manager
    return await mgr.get_snapshot(rp_folder, branch)


@router.get("/{schema_id}", response_model=CustomStateValue | None)
async def get_value(
    request: Request,
    schema_id: str,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    entity_id: str | None = Query(None),
):
    mgr = request.app.state.custom_state_manager
    return await mgr.get_value(schema_id, rp_folder, branch, entity_id)


@router.post("/{schema_id}", response_model=CustomStateValue)
async def set_value(request: Request, schema_id: str, body: CustomStateSet):
    mgr = request.app.state.custom_state_manager
    return await mgr.set_value(
        schema_id=schema_id,
        value=body.value,
        rp_folder=body.rp_folder,
        branch=body.branch,
        entity_id=body.entity_id,
        reason=body.reason,
    )


@router.get("/presets/list", response_model=list[PresetInfo])
async def list_presets(request: Request):
    mgr = request.app.state.custom_state_manager
    return mgr.list_presets()


@router.post("/presets/{preset_name}/apply", response_model=list[CustomStateSchema])
async def apply_preset(
    request: Request,
    preset_name: str,
    rp_folder: str = Query(...),
):
    mgr = request.app.state.custom_state_manager
    try:
        return await mgr.apply_preset(preset_name, rp_folder)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
