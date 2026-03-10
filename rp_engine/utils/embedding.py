"""Embedding blob utilities."""

from __future__ import annotations

import struct


def has_real_embedding(blob: bytes | None) -> bool:
    """Check if a blob contains a real (non-zero) embedding vector."""
    if not blob:
        return False
    try:
        values = struct.unpack(f"{len(blob) // 4}f", blob)
        return not all(v == 0.0 for v in values)
    except Exception:
        return False
