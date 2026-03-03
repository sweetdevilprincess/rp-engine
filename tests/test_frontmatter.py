"""Tests for YAML frontmatter parser."""

from pathlib import Path

import pytest

from rp_engine.utils.frontmatter import parse_frontmatter, parse_file, serialize_frontmatter


class TestParseFrontmatter:
    def test_basic_frontmatter(self):
        content = "---\nname: Test\ntype: character\n---\nBody text here."
        fm, body = parse_frontmatter(content)
        assert fm == {"name": "Test", "type": "character"}
        assert body == "Body text here."

    def test_no_frontmatter(self):
        content = "Just a regular markdown file.\nNo frontmatter."
        fm, body = parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_no_closing_delimiter(self):
        content = "---\nname: Test\nNo closing delimiter."
        fm, body = parse_frontmatter(content)
        assert fm is None

    def test_empty_frontmatter(self):
        content = "---\n---\nBody"
        fm, body = parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_complex_yaml(self):
        content = """---
name: Dante Moretti
aliases:
  - Beasty
  - The Boss
relationships:
  - name: Lilith
    role: love_interest
tags: [mafia, boss]
---
Character description."""
        fm, body = parse_frontmatter(content)
        assert fm["name"] == "Dante Moretti"
        assert fm["aliases"] == ["Beasty", "The Boss"]
        assert fm["relationships"][0]["name"] == "Lilith"
        assert fm["tags"] == ["mafia", "boss"]
        assert "Character description." in body

    def test_nested_dict(self):
        content = """---
who_else_remembers:
  Dante:
    perspective: Unconscious action
    memory_ref: null
---
Body."""
        fm, body = parse_frontmatter(content)
        assert fm["who_else_remembers"]["Dante"]["perspective"] == "Unconscious action"
        assert fm["who_else_remembers"]["Dante"]["memory_ref"] is None

    def test_multiline_string(self):
        content = '---\nsummary: "A long summary\\nthat spans lines"\n---\nBody'
        fm, body = parse_frontmatter(content)
        assert fm["summary"] is not None

    def test_boolean_values(self):
        content = "---\nis_player_character: false\nalways_load: true\n---\n"
        fm, body = parse_frontmatter(content)
        assert fm["is_player_character"] is False
        assert fm["always_load"] is True

    def test_numeric_values(self):
        content = "---\ntrust_score: 16\nweight: 0.7\n---\n"
        fm, body = parse_frontmatter(content)
        assert fm["trust_score"] == 16
        assert fm["weight"] == 0.7

    def test_invalid_yaml(self):
        content = "---\n: invalid yaml [[\n---\nBody"
        fm, body = parse_frontmatter(content)
        assert fm is None

    def test_non_dict_yaml(self):
        content = "---\n- just\n- a list\n---\nBody"
        fm, body = parse_frontmatter(content)
        assert fm is None

    def test_body_starts_with_newline(self):
        content = "---\nname: Test\n---\n\nBody with blank line."
        fm, body = parse_frontmatter(content)
        assert fm is not None
        assert body.startswith("\nBody")

    def test_empty_string(self):
        fm, body = parse_frontmatter("")
        assert fm is None
        assert body == ""


class TestParseFile:
    def test_reads_and_parses(self, tmp_path: Path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: Test Card\n---\nContent here.", encoding="utf-8")
        fm, body = parse_file(f)
        assert fm["name"] == "Test Card"
        assert "Content here." in body


class TestSerializeFrontmatter:
    def test_round_trip(self):
        original = {"name": "Test", "type": "character", "tags": ["a", "b"]}
        body = "Some body text."
        serialized = serialize_frontmatter(original, body)
        assert serialized.startswith("---\n")
        assert "---\n" in serialized[4:]  # Closing delimiter

        # Parse it back
        fm, parsed_body = parse_frontmatter(serialized)
        assert fm["name"] == "Test"
        assert fm["type"] == "character"
        assert fm["tags"] == ["a", "b"]
        assert "Some body text." in parsed_body

    def test_empty_body(self):
        fm = {"name": "Test"}
        result = serialize_frontmatter(fm, "")
        assert result.startswith("---\n")
        assert result.endswith("---")
