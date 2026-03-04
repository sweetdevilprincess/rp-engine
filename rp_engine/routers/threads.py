"""Plot thread tracking endpoints."""

from __future__ import annotations

import logging
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.dependencies import get_thread_tracker
from rp_engine.models.analysis import (
    ThreadCounterUpdate,
    ThreadDetail,
    ThreadListResponse,
)
from rp_engine.models.context import ThreadAlert
from rp_engine.services.thread_tracker import ThreadTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    tracker: ThreadTracker = Depends(get_thread_tracker),
):
    """List all plot threads with current counter values."""
    threads = await tracker.get_all_threads(rp_folder, branch)
    return ThreadListResponse(threads=threads, total=len(threads))


@router.get("/alerts", response_model=list[ThreadAlert])
async def get_alerts(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    tracker: ThreadTracker = Depends(get_thread_tracker),
):
    """Get plot threads that have crossed alert thresholds."""
    return await tracker.get_alerts(rp_folder, branch)


@router.get("/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: str,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    tracker: ThreadTracker = Depends(get_thread_tracker),
):
    """Get a single plot thread with its current counter."""
    thread = await tracker.get_thread(thread_id, rp_folder, branch)
    if not thread:
        raise HTTPException(404, detail=f"Thread '{thread_id}' not found")
    return thread


@router.post("/{thread_id}/update-counter", response_model=ThreadDetail)
async def update_counter(
    thread_id: str,
    body: ThreadCounterUpdate,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    tracker: ThreadTracker = Depends(get_thread_tracker),
):
    """Manually set a thread counter value."""
    thread = await tracker.get_thread(thread_id, rp_folder, branch)
    if not thread:
        raise HTTPException(404, detail=f"Thread '{thread_id}' not found")

    from datetime import datetime

    from rp_engine.database import PRIORITY_ANALYSIS

    now = datetime.now(UTC).isoformat()
    await tracker.db.enqueue_write(
        """INSERT INTO thread_counters (thread_id, rp_folder, branch, current_counter, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(thread_id, rp_folder, branch)
           DO UPDATE SET current_counter = excluded.current_counter,
                         updated_at = excluded.updated_at""",
        [thread_id, rp_folder, branch, body.counter, now],
        priority=PRIORITY_ANALYSIS,
    )

    return await tracker.get_thread(thread_id, rp_folder, branch)
