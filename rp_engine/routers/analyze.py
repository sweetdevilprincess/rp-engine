"""Analysis pipeline endpoints — card gaps."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from rp_engine.database import Database
from rp_engine.dependencies import get_db
from rp_engine.models.analysis import CardGapItem, CardGapResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


@router.get("/gaps", response_model=CardGapResponse)
async def get_card_gaps(
    rp_folder: str = Query(...),
    min_seen_count: int = Query(1, ge=1),
    db: Database = Depends(get_db),
):
    """Return accumulated card gaps (entities without story cards)."""
    rows = await db.fetch_all(
        """SELECT entity_name, suggested_type, seen_count, first_seen, last_seen
           FROM card_gaps
           WHERE rp_folder = ? AND seen_count >= ?
           ORDER BY seen_count DESC""",
        [rp_folder, min_seen_count],
    )

    gaps = [
        CardGapItem(
            entity_name=r["entity_name"],
            suggested_type=r.get("suggested_type"),
            seen_count=r["seen_count"],
            first_seen=r.get("first_seen"),
            last_seen=r.get("last_seen"),
        )
        for r in rows
    ]

    return CardGapResponse(gaps=gaps, total=len(gaps))
