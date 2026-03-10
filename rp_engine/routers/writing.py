"""Writing intelligence endpoints — stats, patterns, feedback."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from rp_engine.models.writing import WritingFeedbackBody

logger = logging.getLogger(__name__)


def _get_writing_intelligence(request: Request):
    """Get writing intelligence from app state, or None if not initialized."""
    return getattr(request.app.state, "writing_intelligence", None)


router = APIRouter(tags=["writing"])


@router.get("/api/writing/intelligence/stats")
async def writing_stats(
    writing_intelligence=Depends(_get_writing_intelligence),
):
    """Get writing intelligence statistics."""
    if writing_intelligence is None:
        raise HTTPException(status_code=503, detail="Writing intelligence not initialized")
    return writing_intelligence.get_stats()


@router.get("/api/writing/intelligence/patterns")
async def writing_patterns(
    category: str | None = Query(None),
    writing_intelligence=Depends(_get_writing_intelligence),
):
    """List writing patterns, optionally filtered by category."""
    if writing_intelligence is None:
        raise HTTPException(status_code=503, detail="Writing intelligence not initialized")
    patterns = writing_intelligence.list_patterns(category=category)
    return [
        {
            "id": p.id,
            "category": p.category.value,
            "subcategory": p.subcategory,
            "description": p.description,
            "direction": p.direction.value,
            "severity": p.severity,
            "proficiency": p.proficiency,
            "frequency": p.frequency,
            "correction_count": p.correction_count,
        }
        for p in patterns
    ]


@router.post("/api/writing/intelligence/feedback")
async def writing_feedback(
    body: WritingFeedbackBody,
    writing_intelligence=Depends(_get_writing_intelligence),
):
    """Submit writing feedback for the intelligence system."""
    if writing_intelligence is None:
        raise HTTPException(status_code=503, detail="Writing intelligence not initialized")

    from writing_intelligence.types import FeedbackInput

    if body.accepted:
        result = writing_intelligence.record_outcome(body.original_output, accepted=True)
    else:
        feedback = FeedbackInput(
            original_output=body.original_output,
            user_feedback=body.user_feedback,
            user_rewrite=body.user_rewrite,
        )
        result = writing_intelligence.record_outcome(
            body.original_output, accepted=False, feedback=feedback)

    return result
