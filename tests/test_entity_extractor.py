"""Tests for EntityExtractor service."""

from __future__ import annotations

import pytest

from rp_engine.services.entity_extractor import EntityExtractor


@pytest.fixture
def extractor(card_indexer, db):
    """EntityExtractor backed by the indexed test data."""
    return EntityExtractor(db)


class TestTokenize:
    def test_single_words(self, extractor):
        tokens = extractor._tokenize("Hello world")
        assert "hello" in tokens
        assert "world" in tokens

    def test_bigrams(self, extractor):
        tokens = extractor._tokenize("Dante Moretti walked")
        assert "dante moretti" in tokens
        assert "moretti walked" in tokens

    def test_trigrams(self, extractor):
        tokens = extractor._tokenize("the big bad wolf")
        assert "the big bad" in tokens
        assert "big bad wolf" in tokens

    def test_strips_punctuation_keeps_apostrophes(self, extractor):
        tokens = extractor._tokenize("Dante's place, really?")
        assert "dante's" in tokens
        assert "place" in tokens

    def test_short_words_filtered(self, extractor):
        tokens = extractor._tokenize("I am a test")
        assert "i" not in tokens  # single char filtered


class TestMatchEntities:
    @pytest.mark.asyncio
    async def test_match_by_name(self, extractor):
        result = await extractor.extract(
            "Dante Moretti entered the room",
            None,
            "TestRP",
        )
        entity_ids = [m.entity_id for m in result.matched_entities]
        assert any("dante moretti" in eid for eid in entity_ids)

    @pytest.mark.asyncio
    async def test_match_by_alias(self, extractor):
        result = await extractor.extract("Beasty was angry", None, "TestRP")
        matched_aliases = [
            m for m in result.matched_entities if m.match_source == "alias"
        ]
        assert len(matched_aliases) > 0

    @pytest.mark.asyncio
    async def test_match_by_keyword(self, extractor):
        result = await extractor.extract(
            "The pillow wall was broken",
            None,
            "TestRP",
        )
        matched_kw = [
            m for m in result.matched_entities if m.match_source == "keyword"
        ]
        assert len(matched_kw) > 0

    @pytest.mark.asyncio
    async def test_name_match_highest_score(self, extractor):
        result = await extractor.extract(
            "Dante Moretti spoke to Beasty",
            None,
            "TestRP",
        )
        # Name match should score 1.0 (highest)
        for m in result.matched_entities:
            if m.match_source == "name":
                assert m.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, extractor):
        result = await extractor.extract(
            "Nothing relevant here xyz123",
            None,
            "TestRP",
        )
        assert len(result.matched_entities) == 0


class TestActiveNPCDetection:
    @pytest.mark.asyncio
    async def test_dialogue_detection(self, extractor):
        result = await extractor.extract(
            "What now?",
            'Dante leaned forward. "We need to talk," he said.',
            "TestRP",
        )
        active_names = [n.name for n in result.active_npcs]
        assert "Dante Moretti" in active_names

    @pytest.mark.asyncio
    async def test_action_subject_detection(self, extractor):
        result = await extractor.extract(
            "I waited.",
            "Dante walked across the room and opened the door.",
            "TestRP",
        )
        active_names = [n.name for n in result.active_npcs]
        assert "Dante Moretti" in active_names

    @pytest.mark.asyncio
    async def test_pov_header_detection(self, extractor):
        result = await extractor.extract(
            "Continue",
            "=== Dante Moretti ===\nHe sat in the dark office.",
            "TestRP",
        )
        active = [n for n in result.active_npcs if n.detection_reason == "pov_header"]
        assert len(active) > 0

    @pytest.mark.asyncio
    async def test_no_active_on_first_turn(self, extractor):
        result = await extractor.extract(
            "Lilith walked into the warehouse",
            None,
            "TestRP",
        )
        assert len(result.active_npcs) == 0


class TestReferencedNPCDetection:
    @pytest.mark.asyncio
    async def test_referenced_not_active(self, extractor):
        result = await extractor.extract(
            "I remembered what Dante told me last week",
            None,
            "TestRP",
        )
        ref_names = [n.name for n in result.referenced_npcs]
        assert "Dante Moretti" in ref_names
        active_names = [n.name for n in result.active_npcs]
        assert "Dante Moretti" not in active_names


class TestLocationDetection:
    @pytest.mark.asyncio
    async def test_detect_location_by_name(self, extractor):
        result = await extractor.extract(
            "She arrived at Dante's Penthouse",
            None,
            "TestRP",
        )
        assert "Dante's Penthouse" in result.detected_locations

    @pytest.mark.asyncio
    async def test_detect_location_by_alias(self, extractor):
        result = await extractor.extract(
            "She returned to the penthouse",
            None,
            "TestRP",
        )
        assert "Dante's Penthouse" in result.detected_locations
