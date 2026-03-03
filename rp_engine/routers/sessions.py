"""Session management endpoints."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from rp_engine.database import Database, PRIORITY_EXCHANGE
from rp_engine.dependencies import get_db
from rp_engine.models.session import (
    NewEntity,
    PlotThreadStatus,
    SceneProgression,
    SessionCreate,
    SessionEndResponse,
    SessionEndSummary,
    SessionResponse,
    TrustChange,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_from_row(row: dict) -> SessionResponse:
    metadata = None
    if row.get("metadata"):
        try:
            metadata = json.loads(row["metadata"])
        except (json.JSONDecodeError, TypeError):
            pass
    return SessionResponse(
        id=row["id"],
        rp_folder=row["rp_folder"],
        branch=row["branch"],
        started_at=row["started_at"],
        ended_at=row.get("ended_at"),
        metadata=metadata,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreate,
    request: Request,
    db: Database = Depends(get_db),
):
    """Start a new RP session."""
    # Auto-create "main" branch if needed
    branch_manager = getattr(request.app.state, "branch_manager", None)
    if branch_manager:
        await branch_manager.ensure_main_branch(body.rp_folder)

    session_id = uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()

    future = await db.enqueue_write(
        """INSERT INTO sessions (id, rp_folder, branch, started_at)
           VALUES (?, ?, ?, ?)""",
        [session_id, body.rp_folder, body.branch, now],
        priority=PRIORITY_EXCHANGE,
    )
    await future

    return SessionResponse(
        id=session_id,
        rp_folder=body.rp_folder,
        branch=body.branch,
        started_at=now,
    )


@router.get("/active", response_model=SessionResponse)
async def get_active_session(db: Database = Depends(get_db)):
    """Get the most recent active (un-ended) session."""
    row = await db.fetch_one(
        "SELECT * FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
    )
    if not row:
        raise HTTPException(404, detail="No active session")
    return _session_from_row(row)


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    metadata: dict,
    db: Database = Depends(get_db),
):
    """Update session metadata."""
    row = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
    if not row:
        raise HTTPException(404, detail=f"Session {session_id} not found")

    future = await db.enqueue_write(
        "UPDATE sessions SET metadata = ? WHERE id = ?",
        [json.dumps(metadata), session_id],
        priority=PRIORITY_EXCHANGE,
    )
    await future

    updated = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
    return _session_from_row(updated)


@router.post("/{session_id}/end", response_model=SessionEndResponse)
async def end_session(
    session_id: str,
    request: Request,
    db: Database = Depends(get_db),
):
    """End a session. Returns accumulated summary data."""
    row = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
    if not row:
        raise HTTPException(404, detail=f"Session {session_id} not found")
    if row["ended_at"]:
        raise HTTPException(400, detail="Session already ended")

    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        "UPDATE sessions SET ended_at = ? WHERE id = ?",
        [now, session_id],
        priority=PRIORITY_EXCHANGE,
    )
    await future

    # Gather summary data
    # Events from this session's exchanges
    event_rows = await db.fetch_all(
        """SELECT e.event FROM events e
           JOIN exchanges ex ON e.exchange_id = ex.id
           WHERE ex.session_id = ?
           ORDER BY e.created_at""",
        [session_id],
    )
    events = [r["event"] for r in event_rows]

    # Trust changes from this session's exchanges
    trust_rows = await db.fetch_all(
        """SELECT tm.change, tm.reason,
                  r.character_a, r.character_b
           FROM trust_modifications tm
           JOIN relationships r ON tm.relationship_id = r.id
           JOIN exchanges ex ON tm.exchange_id = ex.id
           WHERE ex.session_id = ?
           ORDER BY tm.created_at""",
        [session_id],
    )
    trust_changes = [
        TrustChange(
            npc=r["character_b"],
            delta=r["change"],
            reason=r["reason"] or "",
        )
        for r in trust_rows
    ]

    session_resp = SessionResponse(
        id=row["id"],
        rp_folder=row["rp_folder"],
        branch=row["branch"],
        started_at=row["started_at"],
        ended_at=now,
    )

    rp_folder = row["rp_folder"]
    branch = row["branch"]

    # New entities from card_gaps
    gap_rows = await db.fetch_all(
        "SELECT entity_name, suggested_type, seen_count FROM card_gaps WHERE rp_folder = ?",
        [rp_folder],
    )
    new_entities = [
        NewEntity(name=g["entity_name"], type=g.get("suggested_type") or "unknown")
        for g in gap_rows
    ]

    # Plot thread status from thread_counters
    thread_rows = await db.fetch_all(
        """SELECT tc.thread_id, pt.name, tc.current_counter
           FROM thread_counters tc
           JOIN plot_threads pt ON tc.thread_id = pt.id AND tc.rp_folder = pt.rp_folder
           WHERE tc.rp_folder = ? AND tc.branch = ?""",
        [rp_folder, branch],
    )
    plot_thread_status = [
        PlotThreadStatus(
            thread_id=t["thread_id"],
            name=t["name"],
            end_counter=t["current_counter"],
        )
        for t in thread_rows
    ]

    # Scene progression
    first_exchange = await db.fetch_one(
        """SELECT in_story_timestamp, location FROM exchanges
           WHERE session_id = ? ORDER BY exchange_number ASC LIMIT 1""",
        [session_id],
    )
    last_exchange = await db.fetch_one(
        """SELECT in_story_timestamp, location FROM exchanges
           WHERE session_id = ? ORDER BY exchange_number DESC LIMIT 1""",
        [session_id],
    )
    location_rows = await db.fetch_all(
        """SELECT DISTINCT location FROM exchanges
           WHERE session_id = ? AND location IS NOT NULL""",
        [session_id],
    )
    scene_progression = SceneProgression(
        first_timestamp=first_exchange.get("in_story_timestamp") if first_exchange else None,
        last_timestamp=last_exchange.get("in_story_timestamp") if last_exchange else None,
        locations_visited=[r["location"] for r in location_rows],
    )

    # Cards are read-only in CoW system — trust lives only in DB.
    # No writeback to card files.

    summary = SessionEndSummary(
        significant_events=events,
        trust_changes=trust_changes,
        new_entities=new_entities,
        relationship_arcs=[],
        plot_thread_status=plot_thread_status,
        scene_progression=scene_progression,
    )

    return SessionEndResponse(session=session_resp, summary=summary)


