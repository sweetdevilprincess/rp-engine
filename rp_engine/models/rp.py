"""Pydantic models for RP management and guidelines."""

from __future__ import annotations

from pydantic import BaseModel

from rp_engine.models.enums import (
    NarrativeVoice,
    PovMode,
    ResponseLength,
    ScenePacing,
    Tense,
)


class RPCreate(BaseModel):
    rp_name: str
    pov_mode: PovMode = "single"
    dual_characters: list[str] = []
    tone: str = ""
    scene_pacing: ScenePacing = "moderate"


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
    pov_mode: PovMode | None = None
    dual_characters: list[str] = []
    narrative_voice: NarrativeVoice | None = None
    tense: Tense | None = None
    tone: list[str] | str | None = None
    scene_pacing: ScenePacing | None = None
    integrate_user_narrative: bool | None = None
    pov_character: str | None = None
    preserve_user_details: bool | None = None
    sensitive_themes: list[str] = []
    hard_limits: str | list[str] | None = None
    response_length: ResponseLength | None = None
