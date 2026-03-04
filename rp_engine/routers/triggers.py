"""Trigger CRUD + test endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.database import PRIORITY_ANALYSIS
from rp_engine.dependencies import get_db, get_scene_classifier, get_trigger_evaluator
from rp_engine.models.trigger import (
    TriggerCreate,
    TriggerResponse,
    TriggerTestRequest,
    TriggerTestResult,
    TriggerUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/triggers", tags=["triggers"])


def _row_to_response(row: dict) -> TriggerResponse:
    """Convert DB row to TriggerResponse."""
    conditions = []
    if row.get("conditions"):
        try:
            conditions = json.loads(row["conditions"]) if isinstance(row["conditions"], str) else row["conditions"]
        except (json.JSONDecodeError, TypeError):
            conditions = []

    return TriggerResponse(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        rp_folder=row["rp_folder"],
        inject_type=row["inject_type"],
        inject_content=row.get("inject_content"),
        inject_card_path=row.get("inject_card_path"),
        conditions=conditions,
        match_mode=row.get("match_mode", "any"),
        priority=row.get("priority", 0) or 0,
        cooldown_turns=row.get("cooldown_turns", 0) or 0,
        last_fired_turn=row.get("last_fired_turn"),
        enabled=bool(row.get("enabled", True)),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.post("", response_model=TriggerResponse, status_code=201)
async def create_trigger(body: TriggerCreate, db=Depends(get_db)):
    """Create a new situational trigger."""
    trigger_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    conditions_json = json.dumps([c.model_dump() for c in body.conditions])

    future = await db.enqueue_write(
        """INSERT INTO situational_triggers
               (id, rp_folder, name, description, inject_type, inject_content,
                inject_card_path, conditions, match_mode, priority,
                cooldown_turns, enabled, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        [
            trigger_id, body.rp_folder, body.name, body.description,
            body.inject_type, body.inject_content, body.inject_card_path,
            conditions_json, body.match_mode, body.priority,
            body.cooldown_turns, now, now,
        ],
        priority=PRIORITY_ANALYSIS,
    )
    await future

    row = await db.fetch_one(
        "SELECT * FROM situational_triggers WHERE id = ?", [trigger_id]
    )
    return _row_to_response(row)


@router.get("", response_model=list[TriggerResponse])
async def list_triggers(
    rp_folder: str = Query(None),
    enabled: bool = Query(None),
    db=Depends(get_db),
):
    """List triggers, optionally filtered by rp_folder and enabled status."""
    sql = "SELECT * FROM situational_triggers WHERE 1=1"
    params = []

    if rp_folder:
        sql += " AND rp_folder = ?"
        params.append(rp_folder)
    if enabled is not None:
        sql += " AND enabled = ?"
        params.append(1 if enabled else 0)

    sql += " ORDER BY priority DESC, name"
    rows = await db.fetch_all(sql, params)
    return [_row_to_response(r) for r in rows]


@router.get("/{trigger_id}", response_model=TriggerResponse)
async def get_trigger(trigger_id: str, db=Depends(get_db)):
    """Get a single trigger by ID."""
    row = await db.fetch_one(
        "SELECT * FROM situational_triggers WHERE id = ?", [trigger_id]
    )
    if not row:
        raise HTTPException(404, detail=f"Trigger {trigger_id} not found")
    return _row_to_response(row)


@router.put("/{trigger_id}", response_model=TriggerResponse)
async def update_trigger(
    trigger_id: str, body: TriggerUpdate, db=Depends(get_db)
):
    """Partial update of a trigger."""
    existing = await db.fetch_one(
        "SELECT * FROM situational_triggers WHERE id = ?", [trigger_id]
    )
    if not existing:
        raise HTTPException(404, detail=f"Trigger {trigger_id} not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return _row_to_response(existing)

    now = datetime.now(UTC).isoformat()
    set_clauses = []
    params = []

    for key, value in updates.items():
        if key == "conditions":
            set_clauses.append("conditions = ?")
            params.append(json.dumps([c.model_dump() for c in value]))
        elif key == "enabled":
            set_clauses.append("enabled = ?")
            params.append(1 if value else 0)
        else:
            set_clauses.append(f"{key} = ?")
            params.append(value)

    set_clauses.append("updated_at = ?")
    params.append(now)
    params.append(trigger_id)

    sql = f"UPDATE situational_triggers SET {', '.join(set_clauses)} WHERE id = ?"
    future = await db.enqueue_write(sql, params, priority=PRIORITY_ANALYSIS)
    await future

    row = await db.fetch_one(
        "SELECT * FROM situational_triggers WHERE id = ?", [trigger_id]
    )
    return _row_to_response(row)


@router.delete("/{trigger_id}", status_code=204)
async def delete_trigger(trigger_id: str, db=Depends(get_db)):
    """Delete a trigger."""
    existing = await db.fetch_one(
        "SELECT id FROM situational_triggers WHERE id = ?", [trigger_id]
    )
    if not existing:
        raise HTTPException(404, detail=f"Trigger {trigger_id} not found")

    future = await db.enqueue_write(
        "DELETE FROM situational_triggers WHERE id = ?",
        [trigger_id],
        priority=PRIORITY_ANALYSIS,
    )
    await future


@router.post("/test", response_model=TriggerTestResult)
async def test_trigger(
    body: TriggerTestRequest,
    rp_folder: str = Query(None),
    branch: str = Query("main"),
    trigger_evaluator=Depends(get_trigger_evaluator),
    scene_classifier=Depends(get_scene_classifier),
):
    """Test a trigger against sample text. Returns detailed condition results + signal scores."""
    # Classify signals from sample text
    signals = await scene_classifier.classify(body.sample_text, None, rp_folder or "", branch)

    result = await trigger_evaluator.evaluate_single(
        body.trigger_id, body.sample_text, signals, rp_folder, branch
    )
    return result
