"""Tests for writing_intelligence.retrieval — PatternRetriever scoring and ordering."""

import pytest
from datetime import datetime, timedelta
from writing_intelligence.db import PatternDB
from writing_intelligence.retrieval import PatternRetriever
from writing_intelligence.types import (
    PatternCategory, TaskSignature, Direction, Pattern,
    Mode, Register, Intensity, Position, Element,
)


@pytest.fixture
def db():
    d = PatternDB(":memory:")
    yield d
    d.close()


@pytest.fixture
def retriever(db):
    return PatternRetriever(db)


def _make_sig(**kwargs):
    defaults = dict(
        mode=Mode.DRAFTING,
        register=Register.ACTION,
        intensity=Intensity.HIGH,
        position=Position.OPENING,
        elements=[Element.PHYSICAL_ACTION],
    )
    defaults.update(kwargs)
    return TaskSignature(**defaults)


def _make_pattern(id, triggers, severity=0.8, proficiency=0.2, **kwargs):
    defaults = dict(
        id=id,
        category=PatternCategory.FIGURATIVE_LANGUAGE,
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
        db.insert_pattern(_make_pattern("p1", ["drafting", "high"]))
        sig = _make_sig()
        scored = retriever.retrieve(sig)
        assert len(scored) == 1
        assert scored[0].pattern.id == "p1"

    def test_no_matching_patterns(self, db, retriever):
        db.insert_pattern(_make_pattern("p1", ["condensing", "low"]))
        sig = _make_sig()  # drafting, high
        scored = retriever.retrieve(sig)
        assert len(scored) == 0

    def test_ordering_by_score(self, db, retriever):
        # p1: high severity, low proficiency -> high score
        db.insert_pattern(_make_pattern("p1", ["drafting"], severity=0.9, proficiency=0.1))
        # p2: low severity, high proficiency -> lower score
        db.insert_pattern(_make_pattern("p2", ["drafting"], severity=0.3, proficiency=0.6,
                                        category=PatternCategory.NARRATIVE_DISTANCE))
        sig = _make_sig()
        scored = retriever.retrieve(sig)
        assert len(scored) == 2
        assert scored[0].pattern.id == "p1"

    def test_max_results(self, db, retriever):
        for i in range(25):
            db.insert_pattern(_make_pattern(
                f"p{i}", ["drafting"], severity=0.8, proficiency=0.2,
                category=PatternCategory.FIGURATIVE_LANGUAGE,
                subcategory=f"sub{i}",
            ))
        sig = _make_sig()
        scored = retriever.retrieve(sig, max_results=5)
        assert len(scored) == 5


class TestScoring:
    def test_relevance_computation(self, retriever):
        # Pattern triggers on 2 of 4 -> relevance = 0.5
        pattern = _make_pattern("p1", ["drafting", "high", "condensing", "low"])
        sig = _make_sig()  # has drafting, high
        relevance = retriever._compute_relevance(pattern, sig.all_trigger_values())
        assert relevance == pytest.approx(0.5, abs=0.01)

    def test_relevance_full_overlap(self, retriever):
        pattern = _make_pattern("p1", ["drafting"])
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
        db.insert_pattern(_make_pattern("p1", ["drafting"], proficiency=0.95))
        sig = _make_sig()
        scored = retriever.retrieve(sig)
        assert len(scored) == 0
