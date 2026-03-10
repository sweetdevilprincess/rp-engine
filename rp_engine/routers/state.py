"""State management endpoints — characters, relationships, scene, events."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.dependencies import get_state_manager, get_timestamp_tracker
from rp_engine.models.analysis import TimeAdvanceRequest, TimeAdvanceResponse
from rp_engine.models.context import SceneState
from rp_engine.models.state import (
    CharacterDetail,
    CharacterListResponse,
    CharacterUpdate,
    EventCreate,
    EventDetail,
    EventListResponse,
    RelationshipDetail,
    RelationshipGraphResponse,
    RelationshipListResponse,
    RelationshipUpdate,
    SceneUpdate,
    StateSnapshot,
)
from rp_engine.services.state_manager import StateManager
from rp_engine.services.timestamp_tracker import TimestampTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/state", tags=["state"])


# ---------------------------------------------------------------------------
# Full state snapshot
# ---------------------------------------------------------------------------


@router.get("", response_model=StateSnapshot)
async def get_full_state(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    state_manager: StateManager = Depends(get_state_manager),
):
    """Full state snapshot for an RP/branch."""
    return await state_manager.get_full_state(rp_folder, branch)


# ---------------------------------------------------------------------------
# Relationship Graph
# ---------------------------------------------------------------------------


@router.get("/relationship-graph", response_model=RelationshipGraphResponse)
async def get_relationship_graph(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    pov_character: str | None = Query(None),
    state_manager: StateManager = Depends(get_state_manager),
):
    """Get a full relationship graph with character nodes and trust edges."""
    return await state_manager.get_relationship_graph(rp_folder, branch, pov_character)


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------


@router.get("/characters", response_model=CharacterListResponse)
async def get_characters(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    location: str | None = Query(None),
    state_manager: StateManager = Depends(get_state_manager),
):
    """List all characters, optionally filtered by location."""
    if location:
        chars = await state_manager.get_characters_at_location(location, rp_folder, branch)
        return CharacterListResponse(characters={c.name: c for c in chars})
    chars = await state_manager.get_all_characters(rp_folder, branch)
    return CharacterListResponse(characters=chars)


@router.get("/characters/{name}", response_model=CharacterDetail)
async def get_character(
    name: str,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    state_manager: StateManager = Depends(get_state_manager),
):
    """Get a single character by name."""
    char = await state_manager.get_character(name, rp_folder, branch)
    if not char:
        raise HTTPException(404, detail=f"Character '{name}' not found")
    return char


@router.put("/characters/{name}", response_model=CharacterDetail)
async def update_character(
    name: str,
    body: CharacterUpdate,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    state_manager: StateManager = Depends(get_state_manager),
):
    """Update (or create) a character's state."""
    return await state_manager.update_character(name, body, rp_folder, branch)


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


@router.get("/relationships", response_model=RelationshipListResponse)
async def get_relationships(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    character: str | None = Query(None),
    state_manager: StateManager = Depends(get_state_manager),
):
    """List relationships, optionally filtered by character name."""
    rels = await state_manager.get_all_relationships(rp_folder, branch, character)
    return RelationshipListResponse(relationships=rels)


@router.put(
    "/relationships/{char_a}/{char_b}",
    response_model=RelationshipDetail,
)
async def update_trust(
    char_a: str,
    char_b: str,
    body: RelationshipUpdate,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    state_manager: StateManager = Depends(get_state_manager),
):
    """Apply a trust change between two characters."""
    return await state_manager.update_trust(
        char_a=char_a,
        char_b=char_b,
        change=body.trust_change,
        direction=body.direction,
        reason=body.reason,
        rp_folder=rp_folder,
        branch=branch,
        exchange_id=body.exchange_id,
    )


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


@router.get("/scene", response_model=SceneState)
async def get_scene(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    state_manager: StateManager = Depends(get_state_manager),
):
    """Get the current scene context."""
    return await state_manager.get_scene(rp_folder, branch)


@router.put("/scene", response_model=SceneState)
async def update_scene(
    body: SceneUpdate,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    state_manager: StateManager = Depends(get_state_manager),
):
    """Update the scene context (partial update)."""
    return await state_manager.update_scene(body, rp_folder, branch)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@router.get("/events", response_model=EventListResponse)
async def get_events(
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    limit: int = Query(15),
    significance: str | None = Query(None),
    character: str | None = Query(None),
    state_manager: StateManager = Depends(get_state_manager),
):
    """List events with optional filters."""
    events = await state_manager.get_events(
        rp_folder, branch, limit, significance, character
    )
    return EventListResponse(events=events)


@router.post("/events", response_model=EventDetail, status_code=201)
async def create_event(
    body: EventCreate,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    state_manager: StateManager = Depends(get_state_manager),
):
    """Create a new significant event."""
    return await state_manager.add_event(
        event=body.event,
        characters=body.characters,
        significance=body.significance,
        rp_folder=rp_folder,
        branch=branch,
        in_story_timestamp=body.in_story_timestamp,
    )


# ---------------------------------------------------------------------------
# Time Advancement
# ---------------------------------------------------------------------------


@router.post("/advance-time", response_model=TimeAdvanceResponse)
async def advance_time(
    body: TimeAdvanceRequest,
    rp_folder: str = Query(...),
    branch: str = Query("main"),
    tracker: TimestampTracker = Depends(get_timestamp_tracker),
):
    """Manually advance the in-story clock."""
    text = body.response_text or ""
    return await tracker.advance_time(
        text, rp_folder, branch, override_minutes=body.override_minutes
    )
