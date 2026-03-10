"""Text chunking, hashing, snippet extraction, and FTS5 query sanitization utilities."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable


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


def chunk_by_character(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text at ``=== Character Name ===`` header boundaries.

    Each section between headers becomes one chunk. If a section exceeds
    ``chunk_size``, it is sub-chunked with ``chunk_text()``. The header
    line is prepended to each sub-chunk for context.
    """
    if not text or not text.strip():
        return []

    # Split at === Character Name === headers
    pattern = re.compile(r"^(===\s+.+?\s+===)\s*$", re.MULTILINE)
    parts = pattern.split(text.strip())

    # parts alternates: [pre-header text, header1, body1, header2, body2, ...]
    chunks: list[str] = []

    # Handle any text before the first header
    if parts[0].strip():
        chunks.extend(chunk_text(parts[0].strip(), chunk_size, overlap))

    # Process header + body pairs
    i = 1
    while i < len(parts) - 1:
        header = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        i += 2

        if not body:
            continue

        section = f"{header}\n{body}"
        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            # Sub-chunk large sections, prepend header to each
            sub_chunks = chunk_text(body, chunk_size - len(header) - 1, overlap)
            for sc in sub_chunks:
                chunks.append(f"{header}\n{sc}")

    return chunks if chunks else [text.strip()]


def compute_chunking_hash(
    strategy: str, chunk_size: int, chunk_overlap: int, rp_folder: str
) -> str:
    """Deterministic hash for chunking parameters. Used to detect stale chunks."""
    key = f"{strategy}:{chunk_size}:{chunk_overlap}:{rp_folder}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def get_chunker(strategy: str) -> Callable[..., list[str]]:
    """Return the chunking function for a given strategy name."""
    chunkers: dict[str, Callable[..., list[str]]] = {
        "fixed": chunk_text,
        "by_character": chunk_by_character,
    }
    return chunkers.get(strategy, chunk_text)


def snippet_around_keyword(text: str, keyword: str, window: int = 200) -> str:
    """Extract a text snippet centered on the first occurrence of *keyword*.

    Case-insensitive search.  Adds ``...`` prefix/suffix when the snippet
    is a substring of the original text.  Falls back to the first
    ``window * 2`` chars if *keyword* is not found.
    """
    if not text:
        return ""
    lower_text = text.lower()
    lower_kw = keyword.lower()
    idx = lower_text.find(lower_kw)
    if idx == -1:
        return text[: window * 2] if len(text) > window * 2 else text
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def truncate_text(text: str | None, max_len: int = 200) -> str:
    """Truncate *text* to *max_len* chars, ending at a word boundary.

    Strips newlines and collapses whitespace before truncating.
    Returns ``""`` for ``None`` / empty input.
    """
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut + "..."


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
