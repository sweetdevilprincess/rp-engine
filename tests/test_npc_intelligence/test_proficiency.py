"""Tests for npc_intelligence.proficiency — ProficiencyUpdater."""

import pytest
from npc_intelligence.db import BehavioralPatternDB
from npc_intelligence.proficiency import ProficiencyUpdater
from npc_intelligence.types import BehavioralCategory, Direction, Pattern


@pytest.fixture
def db():
    d = BehavioralPatternDB(":memory:")
    yield d
    d.close()


@pytest.fixture
def updater(db):
    return ProficiencyUpdater(db)


def _seed_pattern(db, id="p1", proficiency=0.5):
    p = Pattern(
        id=id,
        category=BehavioralCategory.SELF_INTEREST,
        subcategory="test",
        description="Test",
        direction=Direction.AVOID,
        proficiency=proficiency,
    )
    db.insert_pattern(p)
    return p


class TestOnAccepted:
    def test_increment(self, db, updater):
        _seed_pattern(db, "p1", proficiency=0.5)
        updater.on_accepted(["p1"])
        p = db.get_pattern("p1")
        assert p.proficiency == pytest.approx(0.6, abs=0.01)

    def test_frequency_incremented(self, db, updater):
        _seed_pattern(db, "p1")
        updater.on_accepted(["p1"])
        p = db.get_pattern("p1")
        assert p.frequency == 1

    def test_clamp_at_1(self, db, updater):
        _seed_pattern(db, "p1", proficiency=0.95)
        updater.on_accepted(["p1"])
        p = db.get_pattern("p1")
        assert p.proficiency == 1.0

    def test_nonexistent_pattern_skipped(self, db, updater):
        updater.on_accepted(["nonexistent"])  # Should not raise

    def test_multiple_patterns(self, db, updater):
        _seed_pattern(db, "p1", proficiency=0.3)
        _seed_pattern(db, "p2", proficiency=0.4)
        updater.on_accepted(["p1", "p2"])
        assert db.get_pattern("p1").proficiency == pytest.approx(0.4, abs=0.01)
        assert db.get_pattern("p2").proficiency == pytest.approx(0.5, abs=0.01)


class TestOnCorrected:
    def test_corrected_decremented(self, db, updater):
        _seed_pattern(db, "p1", proficiency=0.5)
        updater.on_corrected(["p1"], ["p1"])
        p = db.get_pattern("p1")
        assert p.proficiency == pytest.approx(0.35, abs=0.01)
        assert p.correction_count == 1

    def test_followed_incremented(self, db, updater):
        _seed_pattern(db, "p1", proficiency=0.5)
        _seed_pattern(db, "p2", proficiency=0.5)
        # p1 was corrected, p2 was injected but not corrected
        updater.on_corrected(["p1"], ["p1", "p2"])
        assert db.get_pattern("p1").proficiency == pytest.approx(0.35, abs=0.01)
        assert db.get_pattern("p2").proficiency == pytest.approx(0.6, abs=0.01)

    def test_clamp_at_0(self, db, updater):
        _seed_pattern(db, "p1", proficiency=0.05)
        updater.on_corrected(["p1"], ["p1"])
        p = db.get_pattern("p1")
        assert p.proficiency == 0.0


class TestOnRegression:
    def test_regression_penalty(self, db, updater):
        _seed_pattern(db, "p1", proficiency=0.8)
        updater.on_regression("p1")
        p = db.get_pattern("p1")
        assert p.proficiency == pytest.approx(0.5, abs=0.01)
        assert p.correction_count == 1

    def test_regression_clamp(self, db, updater):
        _seed_pattern(db, "p1", proficiency=0.1)
        updater.on_regression("p1")
        p = db.get_pattern("p1")
        assert p.proficiency == 0.0

    def test_regression_nonexistent(self, db, updater):
        updater.on_regression("nonexistent")  # Should not raise


class TestClamp:
    def test_clamp_lower(self):
        assert ProficiencyUpdater._clamp(-0.5) == 0.0

    def test_clamp_upper(self):
        assert ProficiencyUpdater._clamp(1.5) == 1.0

    def test_clamp_normal(self):
        assert ProficiencyUpdater._clamp(0.5) == 0.5
