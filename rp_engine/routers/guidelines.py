"""Guidelines endpoint — parsed Story_Guidelines.md frontmatter."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from rp_engine.dependencies import get_vault_root
from rp_engine.models.rp import GuidelinesResponse
from rp_engine.utils.frontmatter import parse_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/context", tags=["context"])

# Simple mtime-based cache: (rp_folder, mtime) → parsed guidelines
_cache: dict[str, tuple[float, GuidelinesResponse]] = {}


@router.get("/guidelines", response_model=GuidelinesResponse)
async def get_guidelines(
    rp_folder: str = Query(...),
    vault_root: Path = Depends(get_vault_root),
):
    """Get parsed Story_Guidelines.md frontmatter for an RP."""
    guidelines_path = vault_root / rp_folder / "RP State" / "Story_Guidelines.md"
    if not guidelines_path.exists():
        raise HTTPException(404, detail=f"No guidelines found for {rp_folder}")

    mtime = guidelines_path.stat().st_mtime

    # Check cache
    if rp_folder in _cache:
        cached_mtime, cached_resp = _cache[rp_folder]
        if cached_mtime == mtime:
            return cached_resp

    frontmatter, _ = parse_file(guidelines_path)
    if frontmatter is None:
        raise HTTPException(422, detail="Could not parse guidelines frontmatter")

    resp = GuidelinesResponse(
        pov_mode=frontmatter.get("pov_mode"),
        dual_characters=frontmatter.get("dual_characters", []),
        narrative_voice=frontmatter.get("narrative_voice"),
        tense=frontmatter.get("tense"),
        tone=frontmatter.get("tone"),
        scene_pacing=frontmatter.get("scene_pacing"),
        integrate_user_narrative=frontmatter.get("integrate_user_narrative"),
    )

    _cache[rp_folder] = (mtime, resp)
    return resp
