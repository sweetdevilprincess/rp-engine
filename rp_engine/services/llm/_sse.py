"""Shared SSE (Server-Sent Events) parser for LLM streaming responses."""

from __future__ import annotations

import json


def parse_sse_line(line: str) -> tuple[str | None, bool]:
    """Parse a single SSE line from an LLM streaming response.

    Returns:
        (content, is_done) -- content is the text delta or None,
        is_done is True when the [DONE] sentinel is received.
    """
    if not line.startswith("data: "):
        return None, False

    data = line[6:]
    if data.strip() == "[DONE]":
        return None, True

    try:
        chunk = json.loads(data)
        delta = chunk.get("choices", [{}])[0].get("delta", {})
        return delta.get("content"), False
    except (ValueError, IndexError, KeyError):
        return None, False
