"""Tests for npc_intelligence.db — BehavioralPatternDB CRUD, sessions, output log."""

import pytest
from npc_intelligence.db import BehavioralPatternDB
from npc_intelligence.types import (
    BehavioralCategory, BehavioralSignature, CorrectionPair, Direction,
    FeedbackInput, Pattern, Archetype, Modifier, TrustStage,
    InteractionType, SceneSignal,
)


@pytest.fixture
def db():
    d = BehavioralPatternDB(":memory:")
    yield d
    d.close()


def _make_pattern(id="p1", category=BehavioralCategory.SELF_INTEREST,
                  triggers=None, proficiency=0.2, severity=0.5):
    return Pattern(
        id=id,
        category=category,
        subcategory="test",
        description="Test pattern",
        direction=Direction.AVOID,
        severity=severity,
        proficiency=proficiency,
        context_triggers=triggers or ["power_holder", "hostile"],
    )


class TestPatternCRUD:
    def test_insert_and_get(self, db):
        p = _make_pattern()
        db.insert_pattern(p)
        got = db.get_pattern("p1")
        assert got is not None
        assert got.id == "p1"
        assert got.category == BehavioralCategory.SELF_INTEREST
        assert got.direction == Direction.AVOID

    def test_get_nonexistent(self, db):
        assert db.get_pattern("nope") is None

    def test_update_pattern(self, db):
        p = _make_pattern()
        db.insert_pattern(p)
        p.severity = 0.9
        p.proficiency = 0.5
        p.frequency = 3
        db.update_pattern(p)
        got = db.get_pattern("p1")
        assert got.severity == 0.9
        assert got.proficiency == 0.5
        assert got.frequency == 3

    def test_get_all_patterns(self, db):
        db.insert_pattern(_make_pattern("p1"))
        db.insert_pattern(_make_pattern("p2", category=BehavioralCategory.ARCHETYPE_VOICE))
        all_p = db.get_all_patterns()
        assert len(all_p) == 2

    def test_get_patterns_by_triggers(self, db):
        db.insert_pattern(_make_pattern("p1", triggers=["power_holder", "hostile"]))
        db.insert_pattern(_make_pattern("p2", triggers=["neutral", "social"]))
        db.insert_pattern(_make_pattern("p3", triggers=["combat"]))

        matched = db.get_patterns_by_triggers({"power_holder", "combat"})
        ids = {p.id for p in matched}
        assert "p1" in ids
        assert "p3" in ids
        assert "p2" not in ids

    def test_get_patterns_by_triggers_no_match(self, db):
        db.insert_pattern(_make_pattern("p1", triggers=["neutral"]))
        matched = db.get_patterns_by_triggers({"combat"})
        assert len(matched) == 0

    def test_find_by_category_subcategory(self, db):
        db.insert_pattern(_make_pattern("p1"))
        found = db.find_pattern_by_category_subcategory("self_interest", "test")
        assert found is not None
        assert found.id == "p1"

    def test_find_by_category_subcategory_not_found(self, db):
        assert db.find_pattern_by_category_subcategory("nope", "nope") is None


class TestCorrectionPairs:
    def test_insert_and_get(self, db):
        db.insert_pattern(_make_pattern("p1"))
        pair = CorrectionPair(
            id="cp1",
            pattern_id="p1",
            original="Bad output",
            revised="Good output",
            critique="Explanation",
            tokens_original=2,
            tokens_revised=2,
        )
        db.insert_correction_pair(pair)
        pairs = db.get_correction_pairs("p1")
        assert len(pairs) == 1
        assert pairs[0].original == "Bad output"
        assert pairs[0].revised == "Good output"

    def test_correction_pairs_loaded_with_pattern(self, db):
        db.insert_pattern(_make_pattern("p1"))
        pair = CorrectionPair(
            id="cp1", pattern_id="p1",
            original="orig", revised="rev",
        )
        db.insert_correction_pair(pair)
        pattern = db.get_pattern("p1")
        assert len(pattern.correction_pairs) == 1


class TestOutputLog:
    def test_log_output_with_behavioral_signature(self, db):
        sig = BehavioralSignature(
            archetype=Archetype.POWER_HOLDER,
            modifiers=[Modifier.PARANOID],
            trust_stage=TrustStage.SUSPICIOUS,
            interaction_type=InteractionType.NEGOTIATION,
            scene_signals=[SceneSignal.DANGER],
        )
        oid = db.log_output("session1", sig, ["p1", "p2"], "test output")
        assert oid is not None

    def test_mark_accepted(self, db):
        sig = BehavioralSignature.from_dict({})
        oid = db.log_output("s1", sig, [], "text")
        db.mark_output_accepted(oid)  # Should not raise

    def test_mark_corrected(self, db):
        sig = BehavioralSignature.from_dict({})
        oid = db.log_output("s1", sig, [], "text")
        db.mark_output_corrected(oid, ["p1"])  # Should not raise


class TestSessions:
    def test_create_and_end_session(self, db):
        sid = db.create_session()
        assert sid is not None
        db.end_session(sid, exchanges=5, patterns_active=3, avg_proficiency=0.45)
        # Should not raise


class TestFeedbackLog:
    def test_log_feedback(self, db):
        feedback = FeedbackInput(
            original_output="some output",
            user_feedback="needs work",
        )
        fid = db.log_feedback(feedback, ["p1"])
        assert fid is not None
