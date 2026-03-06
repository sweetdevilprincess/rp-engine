"""Guidelines service — loads and caches Story_Guidelines.md frontmatter."""

from __future__ import annotations

import logging
from pathlib import Path

from rp_engine.models.rp import GuidelinesResponse

logger = logging.getLogger(__name__)

# Module-level mtime cache: rp_folder -> (mtime, response)
_cache: dict[str, tuple[float, GuidelinesResponse]] = {}


class GuidelinesService:
    """Loads RP guidelines from Story_Guidelines.md with mtime-based caching."""

    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root

    def _guidelines_path(self, rp_folder: str) -> Path:
        return self.vault_root / rp_folder / "RP State" / "Story_Guidelines.md"

    def get_guidelines(self, rp_folder: str) -> GuidelinesResponse | None:
        """Load and cache guidelines. Returns None if file doesn't exist."""
        from rp_engine.utils.frontmatter import parse_file

        path = self._guidelines_path(rp_folder)
        if not path.exists():
            return None

        mtime = path.stat().st_mtime
        if rp_folder in _cache:
            cached_mtime, cached_resp = _cache[rp_folder]
            if cached_mtime == mtime:
                return cached_resp

        try:
            frontmatter, _ = parse_file(path)
            if frontmatter:
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
        except Exception as e:
            logger.warning("Failed to parse guidelines: %s", e)

        return None

    def invalidate(self, rp_folder: str) -> None:
        """Clear cache for an RP folder (called after updates)."""
        _cache.pop(rp_folder, None)
