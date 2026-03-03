"""Exchange (chat message) storage endpoints."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.database import Database, PRIORITY_EXCHANGE
from rp_engine.dependencies import get_analysis_pipeline, get_branch_manager, get_db, get_state_manager
from rp_engine.services.analysis_pipeline import AnalysisPipeline
from rp_engine.services.branch_manager import BranchManager
from rp_engine.services.state_manager import StateManager
from rp_engine.models.exchange import (
    ExchangeDetail,
    ExchangeListResponse,
    ExchangeResponse,
    ExchangeSave,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])


def _detail_from_row(row: dict) -> ExchangeDetail:
    metadata = None
    if row.get("metadata"):
        try:
            metadata = json.loads(row["metadata"])
        except (json.JSONDecodeError, TypeError):
            pass
    npcs = None
    if row.get("npcs_involved"):
        try:
            npcs = json.loads(row["npcs_involved"])
        except (json.JSONDecodeError, TypeError):
            pass
    return ExchangeDetail(
        id=row["id"],
        exchange_number=row["exchange_number"],
        session_id=row["session_id"],
        user_message=row["user_message"],
        assistant_response=row["assistant_response"],
        in_story_timestamp=row.get("in_story_timestamp"),
        location=row.get("location"),
        npcs_involved=npcs,
        analysis_status=row.get("analysis_status", "pending"),
        created_at=row["created_at"],
        metadata=metadata,
    )


@router.post("", response_model=ExchangeResponse, status_code=201)
async def save_exchange(
    body: ExchangeSave,
    db: Database = Depends(get_db),
    pipeline: AnalysisPipeline | None = Depends(get_analysis_pipeline),
    state_manager: StateManager = Depends(get_state_manager),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """Save a user+assistant exchange. Handles idempotency and rewinds.

    Rewind = creating a new branch from the conflict point (append-only).
    """
    # 1. Resolve session
    session_id = body.session_id
    if not session_id:
        active = await db.fetch_one(
            "SELECT id, rp_folder, branch FROM sessions "
            "WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
        )
        if not active:
            raise HTTPException(404, detail="No active session")
        session_id = active["id"]
        rp_folder = active["rp_folder"]
        branch = active["branch"]
    else:
        session = await db.fetch_one(
            "SELECT * FROM sessions WHERE id = ?", [session_id]
        )
        if not session:
            raise HTTPException(404, detail=f"Session {session_id} not found")
        rp_folder = session["rp_folder"]
        branch = session["branch"]

    # 2. Idempotency check
    if body.idempotency_key:
        existing = await db.fetch_one(
            "SELECT * FROM exchanges WHERE metadata LIKE ?",
            [f'%"idempotency_key": "{body.idempotency_key}"%'],
        )
        if existing:
            return ExchangeResponse(
                id=existing["id"],
                exchange_number=existing["exchange_number"],
                session_id=existing["session_id"],
                created_at=existing["created_at"],
                analysis_status=existing.get("analysis_status", "pending"),
                idempotent_hit=True,
            )

    # 3. Parent validation
    if body.parent_exchange_number is not None:
        latest = await db.fetch_val(
            "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder=? AND branch=?",
            [rp_folder, branch],
        )
        if latest is not None and latest != body.parent_exchange_number:
            raise HTTPException(409, detail={
                "error": "exchange_conflict",
                "message": f"Expected parent {body.parent_exchange_number}, latest is {latest}",
                "latest_exchange": latest,
            })

    # 4. Determine exchange_number + rewind (via branch creation)
    exchange_number = body.exchange_number
    rewound_count = None

    if exchange_number is not None:
        conflicting = await db.fetch_one(
            "SELECT id FROM exchanges WHERE rp_folder=? AND branch=? AND exchange_number=?",
            [rp_folder, branch, exchange_number],
        )
        if conflicting:
            # Rewind = create a new branch from exchange_number - 1
            rewind_point = exchange_number - 1
            new_branch_name = body.metadata.get("branch_name") if body.metadata else None
            if not new_branch_name:
                new_branch_name = f"{branch}-rewind-{rewind_point}"
                counter = 1
                while True:
                    exists = await db.fetch_one(
                        "SELECT 1 FROM branches WHERE name = ? AND rp_folder = ?",
                        [new_branch_name, rp_folder],
                    )
                    if not exists:
                        break
                    counter += 1
                    new_branch_name = f"{branch}-rewind-{rewind_point}-{counter}"

            now_ts = datetime.now(timezone.utc).isoformat()
            # Create the rewind branch
            future = await db.enqueue_write(
                """INSERT INTO branches (name, rp_folder, created_from, created_at,
                       branch_point_exchange, description, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, FALSE)""",
                [new_branch_name, rp_folder, branch, now_ts,
                 rewind_point, f"Rewind from exchange {exchange_number}"],
                priority=PRIORITY_EXCHANGE,
            )
            await future

            # Switch to new branch
            await branch_manager.switch_branch(new_branch_name, rp_folder)
            branch = new_branch_name
            # Exchange number 1 on the new branch (or the provided exchange_number)
            exchange_number = exchange_number

            to_delete_count = await db.fetch_val(
                "SELECT COUNT(*) FROM exchanges WHERE rp_folder=? AND branch=? AND exchange_number>=?",
                [rp_folder, branch, exchange_number],
            )
            rewound_count = to_delete_count or 0
    else:
        latest = await db.fetch_val(
            "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder=? AND branch=?",
            [rp_folder, branch],
        )
        exchange_number = (latest or 0) + 1

    # 5. Insert
    now = datetime.now(timezone.utc).isoformat()
    metadata = body.metadata or {}
    if body.idempotency_key:
        metadata["idempotency_key"] = body.idempotency_key

    future = await db.enqueue_write(
        """INSERT INTO exchanges (session_id, rp_folder, branch, exchange_number,
           user_message, assistant_response, in_story_timestamp, location,
           analysis_status, created_at, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        [
            session_id, rp_folder, branch, exchange_number,
            body.user_message, body.assistant_response,
            body.in_story_timestamp, body.location,
            now, json.dumps(metadata) if metadata else None,
        ],
        priority=PRIORITY_EXCHANGE,
    )
    exchange_id = await future

    # Enqueue for async analysis pipeline (Phase 5)
    if pipeline is not None:
        await pipeline.enqueue(exchange_id, rp_folder, branch)

    return ExchangeResponse(
        id=exchange_id,
        exchange_number=exchange_number,
        session_id=session_id,
        created_at=now,
        analysis_status="pending",
        rewound_count=rewound_count,
    )


@router.get("", response_model=ExchangeListResponse)
async def list_exchanges(
    session_id: str | None = Query(None),
    branch: str | None = Query(None),
    rp_folder: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_db),
):
    """List exchanges with optional filters."""
    conditions = []
    params: list = []

    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)
    if branch:
        conditions.append("branch = ?")
        params.append(branch)
    if rp_folder:
        conditions.append("rp_folder = ?")
        params.append(rp_folder)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    total = await db.fetch_val(f"SELECT COUNT(*) FROM exchanges{where}", params)

    rows = await db.fetch_all(
        f"SELECT * FROM exchanges{where} ORDER BY exchange_number DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )

    return ExchangeListResponse(
        exchanges=[_detail_from_row(r) for r in rows],
        total_count=total or 0,
    )


@router.get("/recent", response_model=ExchangeListResponse)
async def recent_exchanges(
    limit: int = Query(10, ge=1, le=100),
    db: Database = Depends(get_db),
):
    """Get the most recent N exchanges across all sessions."""
    rows = await db.fetch_all(
        "SELECT * FROM exchanges ORDER BY created_at DESC LIMIT ?",
        [limit],
    )
    return ExchangeListResponse(
        exchanges=[_detail_from_row(r) for r in rows],
        total_count=len(rows),
    )


@router.delete("/{exchange_id}")
async def delete_exchange(
    exchange_id: int,
    db: Database = Depends(get_db),
):
    """Delete an exchange (deprecated — prefer rewind via branch creation).

    In the CoW system, exchanges are append-only. This endpoint is kept
    for backward compatibility but only removes the exchange record itself.
    State changes made by the exchange persist in CoW entries.
    """
    row = await db.fetch_one("SELECT * FROM exchanges WHERE id = ?", [exchange_id])
    if not row:
        raise HTTPException(404, detail=f"Exchange {exchange_id} not found")

    future = await db.enqueue_write(
        "DELETE FROM exchanges WHERE id=?",
        [exchange_id],
        priority=PRIORITY_EXCHANGE,
    )
    await future

    return {"deleted": True, "exchange_id": exchange_id}
