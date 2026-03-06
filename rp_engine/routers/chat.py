"""Chat endpoint — send text, get RP narrative back."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from rp_engine.database import Database
from rp_engine.dependencies import get_chat_manager, get_db
from rp_engine.models.chat import ChatRequest, ChatResponse
from rp_engine.services.chat_manager import ChatManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _resolve_active_rp(db: Database) -> tuple[str, str, str]:
    """Resolve the active RP folder, branch, and session.

    Returns (rp_folder, branch, session_id).
    Raises 400 if no active RP or session.
    """
    # Check for active session
    session = await db.fetch_one(
        "SELECT id, rp_folder, branch FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
    )
    if not session:
        raise HTTPException(400, detail="No active session. Create one via POST /api/sessions first.")
    return session["rp_folder"], session["branch"], session["id"]


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: Database = Depends(get_db),
    chat_manager: ChatManager = Depends(get_chat_manager),
):
    """Send an RP message and get a narrative response.

    Requires an active session. The endpoint chains together:
    context retrieval -> prompt assembly -> LLM call -> exchange save.
    """
    rp_folder, branch, session_id = await _resolve_active_rp(db)

    if body.stream:
        return StreamingResponse(
            chat_manager.chat_stream(
                user_message=body.user_message,
                rp_folder=rp_folder,
                branch=branch,
                session_id=session_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return await chat_manager.chat(
        user_message=body.user_message,
        rp_folder=rp_folder,
        branch=branch,
        session_id=session_id,
    )
