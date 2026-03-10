"""Analysis pipeline endpoints — card gaps, manifests, undo/redo."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.database import Database
from rp_engine.dependencies import get_analysis_pipeline, get_db
from rp_engine.models.analysis import (
    AnalysisPreviewResponse,
    AnalysisUndoResponse,
    CardGapItem,
    CardGapResponse,
    ManifestEntryResponse,
    ManifestListResponse,
    ManifestResponse,
)
from rp_engine.services.analysis_pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


def _require_pipeline(
    pipeline: AnalysisPipeline | None = Depends(get_analysis_pipeline),
) -> AnalysisPipeline:
    """DI wrapper that raises 503 if the analysis pipeline is not available."""
    if not pipeline:
        raise HTTPException(503, "Analysis pipeline not available")
    return pipeline


def _manifest_response(m: dict, include_entries: bool = False) -> ManifestResponse:
    """Map a manifest dict to a ManifestResponse."""
    entries = []
    if include_entries:
        entries = [
            ManifestEntryResponse(
                target_table=e["target_table"],
                target_id=e["target_id"],
                operation=e["operation"],
            )
            for e in m.get("entries", [])
        ]
    return ManifestResponse(
        id=m["id"],
        exchange_number=m["exchange_number"],
        exchange_id=m["exchange_id"],
        session_id=m.get("session_id"),
        status=m["status"],
        model_used=m.get("model_used"),
        raw_response=m.get("raw_response") if include_entries else None,
        created_at=m["created_at"],
        undone_at=m.get("undone_at"),
        entries=entries,
        entry_counts=m.get("entry_counts", {}),
    )


@router.get("/gaps", response_model=CardGapResponse)
async def get_card_gaps(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    min_seen_count: int = Query(1, ge=1),
    db: Database = Depends(get_db),
):
    """Return accumulated card gaps (entities without story cards)."""
    rows = await db.fetch_all(
        """SELECT entity_name, suggested_type, seen_count, first_seen, last_seen
           FROM card_gaps
           WHERE rp_folder = ? AND branch = ? AND seen_count >= ?
           ORDER BY seen_count DESC""",
        [rp_folder, branch, min_seen_count],
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


@router.get("/manifests", response_model=ManifestListResponse)
async def list_manifests(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    pipeline: AnalysisPipeline = Depends(_require_pipeline),
):
    """List all analysis manifests for an RP/branch."""
    manifests = await pipeline.get_manifests(rp_folder, branch)
    return ManifestListResponse(
        manifests=[_manifest_response(m) for m in manifests],
        total=len(manifests),
    )


@router.get("/{exchange_number}/manifest", response_model=ManifestResponse)
async def get_manifest(
    exchange_number: int,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    pipeline: AnalysisPipeline = Depends(_require_pipeline),
):
    """View the active analysis manifest for an exchange."""
    manifest = await pipeline.get_manifest(exchange_number, rp_folder, branch)
    if not manifest:
        raise HTTPException(404, f"No active manifest for exchange {exchange_number}")

    return _manifest_response(manifest, include_entries=True)


@router.get("/{exchange_number}/preview", response_model=AnalysisPreviewResponse)
async def preview_undo(
    exchange_number: int,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    pipeline: AnalysisPipeline = Depends(_require_pipeline),
):
    """Preview what undoing an exchange's analysis would remove."""
    preview = await pipeline.preview_undo(exchange_number, rp_folder, branch)
    if not preview:
        raise HTTPException(404, f"No active manifest for exchange {exchange_number}")

    return AnalysisPreviewResponse(**preview)


@router.post("/{exchange_number}/undo", response_model=AnalysisUndoResponse)
async def undo_analysis(
    exchange_number: int,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    cascade: bool = Query(True),
    pipeline: AnalysisPipeline = Depends(_require_pipeline),
):
    """Undo analysis for an exchange. Optionally cascades to re-analyze subsequent exchanges."""
    manifest_id, tables_affected, cascade_list = await pipeline.undo_exchange_analysis(
        exchange_number, rp_folder, branch, cascade=cascade,
    )

    if manifest_id == 0:
        return AnalysisUndoResponse(
            exchange_number=exchange_number,
            manifest_id=0,
            status="not_found",
        )

    return AnalysisUndoResponse(
        exchange_number=exchange_number,
        manifest_id=manifest_id,
        status="undone",
        entries_removed=sum(tables_affected.values()),
        tables_affected=tables_affected,
        cascade_reanalyzed=cascade_list,
    )


@router.post("/{exchange_number}/redo")
async def redo_analysis(
    exchange_number: int,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    pipeline: AnalysisPipeline = Depends(_require_pipeline),
    db: Database = Depends(get_db),
):
    """Undo and re-run analysis for an exchange."""
    exchange = await db.fetch_one(
        """SELECT id FROM exchanges
           WHERE rp_folder = ? AND branch = ? AND exchange_number = ?""",
        [rp_folder, branch, exchange_number],
    )
    if not exchange:
        raise HTTPException(404, f"Exchange {exchange_number} not found")

    await pipeline.undo_exchange_analysis(
        exchange_number, rp_folder, branch, cascade=False,
    )
    await pipeline.enqueue(exchange["id"], rp_folder, branch)

    return {"status": "enqueued", "exchange_number": exchange_number}


@router.post("/reprocess")
async def reprocess_range(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    start: int = Query(..., description="First exchange number to reprocess"),
    end: int = Query(..., description="Last exchange number to reprocess"),
    pipeline: AnalysisPipeline = Depends(_require_pipeline),
    db: Database = Depends(get_db),
):
    """Undo and re-run analysis for a range of exchanges."""
    if end < start:
        raise HTTPException(400, "end must be >= start")
    if end - start > 50:
        raise HTTPException(400, "Maximum reprocess range is 50 exchanges")

    exchanges = await db.fetch_all(
        """SELECT id, exchange_number FROM exchanges
           WHERE rp_folder = ? AND branch = ?
             AND exchange_number >= ? AND exchange_number <= ?
           ORDER BY exchange_number ASC""",
        [rp_folder, branch, start, end],
    )

    enqueued = []
    for ex in exchanges:
        await pipeline.undo_exchange_analysis(
            ex["exchange_number"], rp_folder, branch, cascade=False,
        )
        await pipeline.enqueue(ex["id"], rp_folder, branch)
        enqueued.append(ex["exchange_number"])

    return {"status": "enqueued", "exchange_numbers": enqueued, "count": len(enqueued)}
