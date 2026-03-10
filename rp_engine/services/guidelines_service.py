"""Guidelines service — loads and caches Story_Guidelines.md frontmatter."""

from __future__ import annotations

import logging
from pathlib import Path

from rp_engine.models.rp import GuidelinesResponse
from rp_engine.utils.lru_cache import LRUCache

logger = logging.getLogger(__name__)

# Module-level mtime cache: rp_folder -> (mtime, response)
_cache: LRUCache[str, tuple[float, GuidelinesResponse]] = LRUCache(maxsize=32)


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
        cached = _cache.get(rp_folder)
        if cached is not None:
            cached_mtime, cached_resp = cached
            if cached_mtime == mtime:
                return cached_resp

        try:
            frontmatter, file_body = parse_file(path)
            if frontmatter:
                resp = GuidelinesResponse(
                    pov_mode=frontmatter.get("pov_mode"),
                    pov_character=frontmatter.get("pov_character"),
                    dual_characters=frontmatter.get("dual_characters", []),
                    narrative_voice=frontmatter.get("narrative_voice"),
                    tense=frontmatter.get("tense"),
                    tone=frontmatter.get("tone"),
                    scene_pacing=frontmatter.get("scene_pacing"),
                    integrate_user_narrative=frontmatter.get("integrate_user_narrative"),
                    preserve_user_details=frontmatter.get("preserve_user_details"),
                    sensitive_themes=frontmatter.get("sensitive_themes", []),
                    hard_limits=frontmatter.get("hard_limits"),
                    response_length=frontmatter.get("response_length"),
                    include_writing_principles=frontmatter.get("include_writing_principles", True),
                    include_npc_framework=frontmatter.get("include_npc_framework", True),
                    include_output_format=frontmatter.get("include_output_format", True),
                    avatar=frontmatter.get("avatar"),
                    body=file_body.strip() if file_body and file_body.strip() else None,
                )
                _cache.put(rp_folder, (mtime, resp))
                return resp
        except Exception as e:
            logger.warning("Failed to parse guidelines: %s", e)

        return None

    def invalidate(self, rp_folder: str) -> None:
        """Clear cache for an RP folder (called after updates)."""
        _cache.pop(rp_folder, None)
