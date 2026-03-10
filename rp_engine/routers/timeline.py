"""Timeline API — view branches and exchanges on a shared timeline."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from rp_engine.database import Database
from rp_engine.dependencies import get_branch_manager, get_db
from rp_engine.models.timeline import (
    DivergencePoint,
    TimelineBranch,
    TimelineExchange,
    TimelineResponse,
)
from rp_engine.services.branch_manager import BranchManager
from rp_engine.utils.text import truncate_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

SNIPPET_LENGTH = 150


@router.get("", response_model=TimelineResponse)
async def get_timeline(
    rp_folder: str = Query(...),
    include_branches: str | None = Query(None, description="Comma-separated branch names"),
    snippet_length: int = Query(SNIPPET_LENGTH, ge=50, le=500),
    db: Database = Depends(get_db),
    branch_manager: BranchManager = Depends(get_branch_manager),
):
    """Get a unified timeline view across branches."""

    # Get all branches for this RP
    branch_rows = await branch_manager.get_all_branch_rows(rp_folder)

    # Filter to requested branches
    branch_filter = None
    if include_branches:
        branch_filter = set(b.strip() for b in include_branches.split(","))

    timeline_branches: list[TimelineBranch] = []
    divergence_map: dict[int, list[str]] = {}  # exchange_number -> [branch_names]

    for br in branch_rows:
        name = br["name"]
        if branch_filter and name not in branch_filter:
            continue

        # Get exchanges for this branch
        exchange_rows = await db.fetch_all(
            """SELECT exchange_number, user_message, assistant_response,
                      in_story_timestamp, created_at, session_id
               FROM exchanges
               WHERE rp_folder = ? AND branch = ?
               ORDER BY exchange_number ASC""",
            [rp_folder, name],
        )

        exchanges = [
            TimelineExchange(
                exchange_number=ex["exchange_number"],
                user_snippet=truncate_text(ex.get("user_message"), snippet_length),
                assistant_snippet=truncate_text(ex.get("assistant_response"), snippet_length),
                in_story_timestamp=ex.get("in_story_timestamp"),
                created_at=ex.get("created_at"),
                session_id=ex.get("session_id"),
            )
            for ex in exchange_rows
        ]

        branch_point = br.get("branch_point_exchange")
        created_from = br.get("created_from")

        timeline_branches.append(TimelineBranch(
            name=name,
            created_from=created_from,
            branch_point=branch_point,
            is_active=bool(br.get("is_active")),
            exchange_count=len(exchanges),
            exchanges=exchanges,
        ))

        # Track divergence points
        if branch_point is not None and created_from:
            divergence_map.setdefault(branch_point, [])
            if created_from not in divergence_map[branch_point]:
                divergence_map[branch_point].append(created_from)
            if name not in divergence_map[branch_point]:
                divergence_map[branch_point].append(name)

    divergence_points = [
        DivergencePoint(exchange_number=ex_num, branches=branches)
        for ex_num, branches in sorted(divergence_map.items())
    ]

    return TimelineResponse(
        rp_folder=rp_folder,
        branches=timeline_branches,
        divergence_points=divergence_points,
    )
