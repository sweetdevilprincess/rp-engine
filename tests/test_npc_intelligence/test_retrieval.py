"""Tests for npc_intelligence.retrieval — BehavioralRetriever scoring and ordering."""

import pytest
from datetime import datetime, timedelta
from npc_intelligence.db import BehavioralPatternDB
from npc_intelligence.retrieval import BehavioralRetriever
from npc_intelligence.types import (
    BehavioralCategory, BehavioralSignature, Direction, Pattern,
    Archetype, Modifier, TrustStage, InteractionType, SceneSignal,
)


@pytest.fixture
def db():
    d = BehavioralPatternDB(":memory:")
    yield d
    d.close()


@pytest.fixture
def retriever(db):
    return BehavioralRetriever(db)


def _make_sig(**kwargs):
    defaults = dict(
        archetype=Archetype.POWER_HOLDER,
        modifiers=[],
        trust_stage=TrustStage.HOSTILE,
        interaction_type=InteractionType.CONFRONTATION,
        scene_signals=[SceneSignal.DANGER],
    )
    defaults.update(kwargs)
    return BehavioralSignature(**defaults)


def _make_pattern(id, triggers, severity=0.8, proficiency=0.2, **kwargs):
    defaults = dict(
        id=id,
        category=BehavioralCategory.SELF_INTEREST,
        subcategory="test",
        description="Test",
        direction=Direction.AVOID,
        severity=severity,
        proficiency=proficiency,
        context_triggers=triggers,
    )
    defaults.update(kwargs)
    return Pattern(**defaults)


class TestRetrieval:
    def test_basic_retrieval(self, db, retriever):
        db.insert_pattern(_make_pattern("p1", ["power_holder", "hostile"]))
        sig = _make_sig()
        scored = retriever.retrieve(sig)
        assert len(scored) == 1
        assert scored[0].pattern.id == "p1"

    def test_no_matching_patterns(self, db, retriever):
        db.insert_pattern(_make_pattern("p1", ["neutral", "social"]))
        sig = _make_sig()  # power_holder, hostile
        scored = retriever.retrieve(sig)
        assert len(scored) == 0

    def test_ordering_by_score(self, db, retriever):
        # p1: high severity, low proficiency -> high score
        db.insert_pattern(_make_pattern("p1", ["power_holder"], severity=0.9, proficiency=0.1))
        # p2: low severity, high proficiency -> lower score
        db.insert_pattern(_make_pattern("p2", ["power_holder"], severity=0.3, proficiency=0.6,
                                        category=BehavioralCategory.ARCHETYPE_VOICE))
        sig = _make_sig()
        scored = retriever.retrieve(sig)
        assert len(scored) == 2
        assert scored[0].pattern.id == "p1"

    def test_max_results(self, db, retriever):
        for i in range(25):
            db.insert_pattern(_make_pattern(
                f"p{i}", ["power_holder"], severity=0.8, proficiency=0.2,
                category=BehavioralCategory.SELF_INTEREST,
                subcategory=f"sub{i}",
            ))
        sig = _make_sig()
        scored = retriever.retrieve(sig, max_results=5)
        assert len(scored) == 5


class TestScoring:
    def test_relevance_computation(self, retriever):
        # Pattern triggers on 2 of 4 -> relevance = 0.5
        pattern = _make_pattern("p1", ["power_holder", "hostile", "neutral", "social"])
        sig = _make_sig()  # has power_holder, hostile
        relevance = retriever._compute_relevance(pattern, sig.all_trigger_values())
        assert relevance == pytest.approx(0.5, abs=0.01)

    def test_relevance_full_overlap(self, retriever):
        pattern = _make_pattern("p1", ["power_holder"])
        sig = _make_sig()
        relevance = retriever._compute_relevance(pattern, sig.all_trigger_values())
        assert relevance == 1.0

    def test_relevance_no_triggers(self, retriever):
        pattern = _make_pattern("p1", [])
        sig = _make_sig()
        relevance = retriever._compute_relevance(pattern, sig.all_trigger_values())
        assert relevance == 0.0


class TestInjectionLevels:
    def test_critical(self, retriever):
        assert retriever._assign_injection_level(0.1) == "critical"
        assert retriever._assign_injection_level(0.39) == "critical"

    def test_moderate(self, retriever):
        assert retriever._assign_injection_level(0.4) == "moderate"
        assert retriever._assign_injection_level(0.69) == "moderate"

    def test_reminder(self, retriever):
        assert retriever._assign_injection_level(0.7) == "reminder"
        assert retriever._assign_injection_level(0.89) == "reminder"

    def test_skip(self, retriever):
        assert retriever._assign_injection_level(0.9) == "skip"
        assert retriever._assign_injection_level(1.0) == "skip"


class TestRecencyBoost:
    def test_no_correction(self, retriever):
        pattern = _make_pattern("p1", [])
        assert retriever._compute_recency_boost(pattern) == 0.0

    def test_recent_correction(self, retriever):
        pattern = _make_pattern("p1", [])
        pattern.last_corrected = datetime.utcnow()
        boost = retriever._compute_recency_boost(pattern)
        assert boost == 1.0

    def test_old_correction(self, retriever):
        pattern = _make_pattern("p1", [])
        pattern.last_corrected = datetime.utcnow() - timedelta(days=30)
        boost = retriever._compute_recency_boost(pattern)
        assert boost == 0.0


class TestSkipFiltering:
    def test_high_proficiency_skipped(self, db, retriever):
        db.insert_pattern(_make_pattern("p1", ["power_holder"], proficiency=0.95))
        sig = _make_sig()
        scored = retriever.retrieve(sig)
        assert len(scored) == 0
