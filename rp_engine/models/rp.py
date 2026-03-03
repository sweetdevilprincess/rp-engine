"""Pydantic models for RP management and guidelines."""

from __future__ import annotations

from pydantic import BaseModel


class RPCreate(BaseModel):
    rp_name: str
    pov_mode: str = "single"
    dual_characters: list[str] = []
    tone: str = ""
    scene_pacing: str = "moderate"


class RPResponse(BaseModel):
    rp_folder: str
    created_files: list[str] = []


class RPInfo(BaseModel):
    rp_folder: str
    has_story_cards: bool
    card_count: int
    has_guidelines: bool
    branches: list[str] = []


class GuidelinesResponse(BaseModel):
    pov_mode: str | None = None
    dual_characters: list[str] = []
    narrative_voice: str | None = None
    tense: str | None = None
    tone: list[str] | str | None = None
    scene_pacing: str | None = None
    integrate_user_narrative: bool | None = None
