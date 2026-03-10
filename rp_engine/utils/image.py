"""Image constants and utilities — avatar conventions, allowed extensions, size limits.

Centralized here so RP avatars and future NPC avatars share one source of truth.
"""

from __future__ import annotations

from pathlib import Path

# Convention filenames checked (in order) when no explicit frontmatter field
AVATAR_CONVENTIONS = ("cover.png", "cover.jpg", "avatar.png", "avatar.jpg", "cover.webp", "avatar.webp")

# Allowed image extensions for upload and serving
AVATAR_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})

# Max image file size (5 MB)
AVATAR_MAX_BYTES = 5 * 1024 * 1024

# Extension → MIME type mapping
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def find_avatar(rp_dir: Path, *, frontmatter_avatar: str | None = None) -> Path | None:
    """Find the avatar image for an RP directory.

    Checks the explicit frontmatter ``avatar`` field first (with path traversal
    guard), then falls back to convention filenames.  Used by the RP router,
    export service, and anywhere else that needs to locate an avatar image.
    """
    # Check explicit frontmatter field
    if frontmatter_avatar:
        candidate = (rp_dir / frontmatter_avatar).resolve()
        if candidate.is_relative_to(rp_dir) and candidate.is_file():
            if candidate.suffix.lower() in AVATAR_EXTENSIONS:
                return candidate

    # Convention fallback
    for name in AVATAR_CONVENTIONS:
        candidate = rp_dir / name
        if candidate.is_file():
            return candidate

    return None
