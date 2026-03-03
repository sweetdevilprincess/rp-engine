"""YAML frontmatter parser and serializer for story card .md files."""

from __future__ import annotations

from pathlib import Path

import yaml


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Split markdown content into frontmatter dict and body text.

    Frontmatter is YAML between opening and closing ``---`` delimiters.
    Returns ``(None, content)`` if no valid frontmatter is found.
    """
    if not content.startswith("---"):
        return None, content

    # Find closing delimiter (skip the opening ---)
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None, content

    yaml_text = content[3:end_idx].strip()
    if not yaml_text:
        return None, content

    try:
        frontmatter = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return None, content

    # frontmatter should be a dict
    if not isinstance(frontmatter, dict):
        return None, content

    # Body is everything after the closing ---
    body = content[end_idx + 3:]
    if body.startswith("\n"):
        body = body[1:]

    return frontmatter, body


def parse_file(file_path: Path) -> tuple[dict | None, str]:
    """Read a markdown file and parse its frontmatter.

    Returns ``(frontmatter, body)`` or ``(None, content)`` on failure.
    """
    text = file_path.read_text(encoding="utf-8")
    return parse_frontmatter(text)


def serialize_frontmatter(frontmatter: dict, body: str) -> str:
    """Serialize a frontmatter dict and body back into markdown with ``---`` delimiters."""
    yaml_text = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    # Ensure body has leading newline separation
    if body and not body.startswith("\n"):
        body = "\n" + body
    return f"---\n{yaml_text}---{body}"
