"""Text chunking, hashing, and FTS5 query sanitization utilities."""

from __future__ import annotations

import hashlib
import re


def hash_content(text: str) -> str:
    """SHA-256 hash of text content for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks at natural boundaries.

    Tries paragraph > sentence > word boundaries for clean splits.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Try paragraph boundary
        boundary = text.rfind("\n\n", start + chunk_size // 2, end)
        if boundary == -1:
            # Try sentence boundary
            boundary = _find_sentence_boundary(text, start + chunk_size // 2, end)
        if boundary == -1:
            # Try word boundary
            boundary = text.rfind(" ", start + chunk_size // 2, end)
        if boundary == -1:
            boundary = end

        chunk = text[start:boundary].strip()
        if chunk:
            chunks.append(chunk)

        start = max(start + 1, boundary - overlap)

    return chunks


def _find_sentence_boundary(text: str, start: int, end: int) -> int:
    """Find the last sentence boundary (. ! ?) in range."""
    best = -1
    for i in range(end - 1, start - 1, -1):
        if text[i] in ".!?" and i + 1 < len(text) and text[i + 1] in " \n\t":
            best = i + 1
            break
    return best


# FTS5 special characters that must be stripped
_FTS5_SPECIAL = re.compile(r'[*"():^~+\-]')


def sanitize_fts_query(query: str) -> str:
    """Strip FTS5 operators, quote each word, join with OR.

    Prevents malformed FTS5 queries from crashing SQLite.
    Returns empty string if no usable words remain.
    """
    if not query:
        return ""

    # Strip special chars
    cleaned = _FTS5_SPECIAL.sub(" ", query)

    # Split into words, filter short ones
    words = [w.strip() for w in cleaned.split() if len(w.strip()) > 1]
    if not words:
        return ""

    # Quote each word and join with OR
    quoted = [f'"{w}"' for w in words]
    return " OR ".join(quoted)
