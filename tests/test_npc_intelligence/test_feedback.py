"""Tests for npc_intelligence.feedback — BehavioralFeedbackProcessor."""

import json
import pytest
from npc_intelligence.db import BehavioralPatternDB
from npc_intelligence.feedback import BehavioralFeedbackProcessor
from npc_intelligence.types import (
    BehavioralCategory, BehavioralSignature, FeedbackInput,
    Archetype, TrustStage, InteractionType,
)


@pytest.fixture
def db():
    d = BehavioralPatternDB(":memory:")
    yield d
    d.close()


@pytest.fixture
def processor(db):
    return BehavioralFeedbackProcessor(db)


class TestHeuristicExtraction:
    def test_default_category_is_self_interest(self, processor):
        feedback = FeedbackInput(
            original_output="Some NPC output",
            user_feedback="This is wrong",
        )
        pattern_ids = processor.process(feedback)
        assert len(pattern_ids) == 1
        pattern = processor.db.get_pattern(pattern_ids[0])
        assert pattern.category == BehavioralCategory.SELF_INTEREST

    def test_feedback_text_in_description(self, processor):
        feedback = FeedbackInput(
            original_output="output",
            user_feedback="The NPC should not cooperate so easily",
        )
        pattern_ids = processor.process(feedback)
        pattern = processor.db.get_pattern(pattern_ids[0])
        assert "should not cooperate" in pattern.description

    def test_no_feedback_text(self, processor):
        feedback = FeedbackInput(original_output="output")
        pattern_ids = processor.process(feedback)
        assert len(pattern_ids) == 1


class TestLLMExtraction:
    def test_llm_extraction_valid_json(self, db):
        mock_response = json.dumps([{
            "category": "archetype_voice",
            "subcategory": "power_holder_speech",
            "description": "Power holder should not be apologetic",
            "direction": "avoid",
            "compressed_rule": "No apologies from power holders",
            "context_triggers": ["power_holder"],
        }])
        processor = BehavioralFeedbackProcessor(db, llm_call=lambda _: mock_response)
        feedback = FeedbackInput(
            original_output="Sorry about that",
            user_feedback="Power holders don't apologize",
        )
        pattern_ids = processor.process(feedback)
        assert len(pattern_ids) == 1
        pattern = db.get_pattern(pattern_ids[0])
        assert pattern.category == BehavioralCategory.ARCHETYPE_VOICE

    def test_llm_extraction_invalid_category_defaults(self, db):
        mock_response = json.dumps([{
            "category": "invalid_category",
            "subcategory": "test",
            "description": "Test",
            "direction": "avoid",
            "compressed_rule": "Test",
            "context_triggers": [],
        }])
        processor = BehavioralFeedbackProcessor(db, llm_call=lambda _: mock_response)
        feedback = FeedbackInput(original_output="output", user_feedback="fix")
        pattern_ids = processor.process(feedback)
        pattern = db.get_pattern(pattern_ids[0])
        assert pattern.category == BehavioralCategory.SELF_INTEREST

    def test_llm_extraction_broken_json(self, db):
        processor = BehavioralFeedbackProcessor(db, llm_call=lambda _: "not json at all")
        feedback = FeedbackInput(original_output="output", user_feedback="fix")
        pattern_ids = processor.process(feedback)
        assert len(pattern_ids) == 1
        pattern = db.get_pattern(pattern_ids[0])
        assert pattern.category == BehavioralCategory.SELF_INTEREST

    def test_llm_extraction_with_markdown_wrapper(self, db):
        response = '```json\n[{"category": "trust_mechanics", "subcategory": "ceiling", "description": "Trust ceiling violated", "direction": "avoid", "compressed_rule": "Respect trust ceiling", "context_triggers": ["hostile"]}]\n```'
        processor = BehavioralFeedbackProcessor(db, llm_call=lambda _: response)
        feedback = FeedbackInput(original_output="output", user_feedback="fix")
        pattern_ids = processor.process(feedback)
        pattern = db.get_pattern(pattern_ids[0])
        assert pattern.category == BehavioralCategory.TRUST_MECHANICS


class TestMatchOrCreate:
    def test_creates_new_pattern(self, processor):
        feedback = FeedbackInput(original_output="output", user_feedback="test")
        ids1 = processor.process(feedback)
        assert len(ids1) == 1

    def test_updates_existing_on_same_category_subcategory(self, db):
        # First creates
        proc = BehavioralFeedbackProcessor(db)
        fb1 = FeedbackInput(original_output="out1", user_feedback="fix1")
        ids1 = proc.process(fb1)

        # Second should match the existing pattern (same category/subcategory)
        fb2 = FeedbackInput(original_output="out2", user_feedback="fix2")
        ids2 = proc.process(fb2)

        # Should be the same pattern ID (updated, not new)
        assert ids1[0] == ids2[0]

        pattern = db.get_pattern(ids1[0])
        assert pattern.correction_count == 2
        assert pattern.severity > 0.5
