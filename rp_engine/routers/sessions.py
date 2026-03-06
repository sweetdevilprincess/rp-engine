"""Session management endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from fastapi import BackgroundTasks

from rp_engine.database import PRIORITY_EXCHANGE, Database
from rp_engine.dependencies import get_branch_manager, get_db, get_recap_builder, get_summary_builder
from rp_engine.services.branch_manager import BranchManager
from rp_engine.services.summary_builder import SummaryBuilder
from rp_engine.services.recap_builder import RecapBuilder
from rp_engine.models.session import (
    NewEntity,
    PlotThreadStatus,
    Recap,
    SceneProgression,
    SessionCreate,
    SessionEndResponse,
    SessionEndSummary,
    SessionResponse,
    SessionSummary,
    TrustChange,
    UpdateSessionBody,
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
    db: Database = Depends(get_db),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """Start a new RP session."""
    # Auto-create "main" branch if needed
    if branch_manager:
        await branch_manager.ensure_main_branch(body.rp_folder)

    session_id = uuid4().hex[:12]
    now = datetime.now(UTC).isoformat()

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
    body: UpdateSessionBody,
    db: Database = Depends(get_db),
):
    """Update session metadata."""
    row = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
    if not row:
        raise HTTPException(404, detail=f"Session {session_id} not found")

    future = await db.enqueue_write(
        "UPDATE sessions SET metadata = ? WHERE id = ?",
        [json.dumps(body.metadata), session_id],
        priority=PRIORITY_EXCHANGE,
    )
    await future

    updated = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
    return _session_from_row(updated)


@router.post("/{session_id}/end", response_model=SessionEndResponse)
async def end_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
    summary_builder: SummaryBuilder = Depends(get_summary_builder),
):
    """End a session. Returns accumulated summary data."""
    row = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
    if not row:
        raise HTTPException(404, detail=f"Session {session_id} not found")
    if row["ended_at"]:
        raise HTTPException(400, detail="Session already ended")

    now = datetime.now(UTC).isoformat()
    future = await db.enqueue_write(
        "UPDATE sessions SET ended_at = ? WHERE id = ?",
        [now, session_id],
        priority=PRIORITY_EXCHANGE,
    )
    await future

    # Gather summary data — parallel batch instead of 8+ sequential queries
    rp_folder = row["rp_folder"]
    branch = row["branch"]

    (event_rows, trust_rows, gap_rows, first_exchange_num,
     thread_rows, first_exchange, last_exchange, location_rows) = await asyncio.gather(
        db.fetch_all(
            """SELECT e.event FROM events e
               JOIN exchanges ex ON e.exchange_id = ex.id
               WHERE ex.session_id = ?
               ORDER BY e.created_at""",
            [session_id],
        ),
        db.fetch_all(
            """SELECT tm.change, tm.reason,
                      r.character_a, r.character_b
               FROM trust_modifications tm
               JOIN relationships r ON tm.relationship_id = r.id
               JOIN exchanges ex ON tm.exchange_id = ex.id
               WHERE ex.session_id = ?
               ORDER BY tm.created_at""",
            [session_id],
        ),
        db.fetch_all(
            """SELECT cg.entity_name, cg.suggested_type, cg.seen_count,
                      (SELECT MIN(ex.exchange_number) FROM exchanges ex
                       WHERE ex.rp_folder = cg.rp_folder AND ex.branch = cg.branch
                         AND ex.created_at >= cg.first_seen) as first_exchange
               FROM card_gaps cg WHERE cg.rp_folder = ? AND cg.branch = ?""",
            [rp_folder, branch],
        ),
        db.fetch_val(
            "SELECT MIN(exchange_number) FROM exchanges WHERE session_id = ?",
            [session_id],
        ),
        db.fetch_all(
            """SELECT tc.thread_id, pt.name, tc.current_counter
               FROM thread_counters tc
               JOIN plot_threads pt ON tc.thread_id = pt.id AND tc.rp_folder = pt.rp_folder
               WHERE tc.rp_folder = ? AND tc.branch = ?""",
            [rp_folder, branch],
        ),
        db.fetch_one(
            """SELECT in_story_timestamp, location FROM exchanges
               WHERE session_id = ? ORDER BY exchange_number ASC LIMIT 1""",
            [session_id],
        ),
        db.fetch_one(
            """SELECT in_story_timestamp, location FROM exchanges
               WHERE session_id = ? ORDER BY exchange_number DESC LIMIT 1""",
            [session_id],
        ),
        db.fetch_all(
            """SELECT DISTINCT location FROM exchanges
               WHERE session_id = ? AND location IS NOT NULL""",
            [session_id],
        ),
    )

    events = [r["event"] for r in event_rows]
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

    new_entities = [
        NewEntity(
            name=g["entity_name"],
            type=g.get("suggested_type") or "unknown",
            first_mention_exchange=g.get("first_exchange"),
        )
        for g in gap_rows
    ]

    # Plot thread status — batch start_counter lookup
    plot_thread_status = []
    for t in thread_rows:
        start_counter = 0
        if first_exchange_num:
            start_val = await db.fetch_val(
                """SELECT counter_value FROM thread_counter_entries
                   WHERE thread_id = ? AND rp_folder = ? AND branch = ?
                     AND exchange_number < ?
                   ORDER BY exchange_number DESC LIMIT 1""",
                [t["thread_id"], rp_folder, branch, first_exchange_num],
            )
            if start_val is not None:
                start_counter = start_val
        plot_thread_status.append(PlotThreadStatus(
            thread_id=t["thread_id"],
            name=t["name"],
            start_counter=start_counter,
            end_counter=t["current_counter"],
        ))
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

    # Fire background task to generate narrative summary
    if summary_builder:
        background_tasks.add_task(
            summary_builder.build_session_summary,
            session_id,
            rp_folder,
            branch,
        )

    return SessionEndResponse(session=session_resp, summary=summary)


@router.get("/{session_id}/summary", response_model=SessionSummary)
async def get_session_summary(
    session_id: str,
    db: Database = Depends(get_db),
    summary_builder: SummaryBuilder = Depends(get_summary_builder),
):
    """Get the narrative summary for a session."""
    row = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
    if not row:
        raise HTTPException(404, detail=f"Session {session_id} not found")

    summary = await summary_builder.get_summary(session_id)
    if not summary:
        raise HTTPException(404, detail="Summary not yet generated. It may still be processing.")
    return summary


@router.post("/{session_id}/summary", response_model=SessionSummary)
async def regenerate_session_summary(
    session_id: str,
    db: Database = Depends(get_db),
    summary_builder: SummaryBuilder = Depends(get_summary_builder),
):
    """Force regenerate a session summary."""
    row = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
    if not row:
        raise HTTPException(404, detail=f"Session {session_id} not found")

    return await summary_builder.build_session_summary(
        session_id=session_id,
        rp_folder=row["rp_folder"],
        branch=row["branch"],
    )


@router.get("/recap", response_model=Recap)
async def get_session_recap(
    rp_folder: str,
    branch: str = "main",
    style: str = "standard",
    recap_builder: RecapBuilder = Depends(get_recap_builder),
):
    """Generate or retrieve a "Previously on..." recap for the current story state."""
    if style not in ("quick", "standard", "detailed"):
        raise HTTPException(400, detail="Style must be 'quick', 'standard', or 'detailed'")

    return await recap_builder.generate_recap(
        rp_folder=rp_folder,
        branch=branch,
        style=style,
    )
