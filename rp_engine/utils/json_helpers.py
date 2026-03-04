"""Safe JSON parsing utilities for DB columns that may be strings or already-parsed."""

from __future__ import annotations

import json


def safe_parse_json(raw: str | dict | None, default: dict | None = None) -> dict:
    """Parse a JSON string into a dict, or return as-is if already a dict.

    Returns *default* (or empty dict) on None, parse failure, or non-dict result.
    """
    if raw is None:
        return default if default is not None else {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else (default if default is not None else {})
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def safe_parse_json_array(raw: str | list | None) -> list:
    """Parse a JSON string into a list, preserving element types (dicts, etc.).

    Returns empty list on None, parse failure, or non-list result.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def safe_parse_json_list(raw: str | list | None) -> list[str]:
    """Parse a JSON string into a list of strings, or return as-is if already a list.

    Returns empty list on None, parse failure, or non-list result.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []
