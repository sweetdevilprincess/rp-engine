"""Key normalization utilities for entity matching.

Ported from .claude/scripts/lib/frontmatter-index.js lines 56-77.
"""

from __future__ import annotations

import re


def normalize_key(name: str) -> str:
    """Normalize an entity name to a canonical lowercase key."""
    if not name:
        return ""
    return str(name).lower().strip()


def file_to_key(filename: str) -> str:
    """Convert a filename (with or without .md) to a normalized key."""
    if not filename:
        return ""
    name = str(filename)
    if name.lower().endswith(".md"):
        name = name[:-3]
    return name.lower().strip()


def id_to_key(id_str: str) -> str:
    """Convert an ID string (underscored) to a normalized key.

    Example: ``memory_lilith_wakes_with_dante`` → ``memory lilith wakes with dante``
    """
    if not id_str:
        return ""
    return str(id_str).replace("_", " ").lower().strip()


def strip_parenthetical(name: str) -> str:
    """Remove trailing parenthetical notes from a name.

    Example: ``Dante Moretti (resident)`` → ``Dante Moretti``
    """
    if not name:
        return ""
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(name)).strip()
