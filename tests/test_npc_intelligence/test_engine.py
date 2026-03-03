"""Tests for npc_intelligence.engine — NPCIntelligence full lifecycle."""

import pytest
from npc_intelligence.engine import NPCIntelligence
from npc_intelligence.types import (
    BehavioralCategory, Direction, FeedbackInput, Pattern,
)


@pytest.fixture
def intel():
    engine = NPCIntelligence(db_path=":memory:")
    yield engine
    engine.close()


def _seed_patterns(intel):
    """Seed a few patterns for testing."""
    intel.add_pattern(Pattern(
        id="p-self",
        category=BehavioralCategory.SELF_INTEREST,
        subcategory="motivation",
        description="NPC actions require traceable motivation",
        direction=Direction.AVOID,
        severity=0.8,
        proficiency=0.2,
        context_triggers=["power_holder", "transactional", "common_people",
                          "hostile", "neutral", "familiar"],
        compressed_rule="Every action needs a self-interest reason",
    ))
    intel.add_pattern(Pattern(
        id="p-arch",
        category=BehavioralCategory.ARCHETYPE_VOICE,
        subcategory="voice",
        description="Each archetype has distinct verbal patterns",
        direction=Direction.AVOID,
        severity=0.8,
        proficiency=0.2,
        context_triggers=["power_holder", "transactional", "opposition"],
        compressed_rule="Archetype defines speech and thought patterns",
    ))
    intel.add_pattern(Pattern(
        id="p-trust",
        category=BehavioralCategory.TRUST_MECHANICS,
        subcategory="boundaries",
        description="Trust stages create hard behavioral boundaries",
        direction=Direction.AVOID,
        severity=0.8,
        proficiency=0.2,
        context_triggers=["hostile", "suspicious", "neutral", "familiar", "trusted"],
        compressed_rule="Trust stage caps cooperation level",
    ))


class TestPrepare:
    def test_prepare_returns_payload(self, intel):
        _seed_patterns(intel)
        payload = intel.prepare(
            npc_name="Aldric",
            archetype="power_holder",
            trust_stage="hostile",
            trust_score=-40,
        )
        assert payload.npc_name == "Aldric"
        assert len(payload.patterns_included) > 0
        assert "[NPC BEHAVIORAL CONSTRAINTS" in payload.text

    def test_prepare_empty_db(self, intel):
        payload = intel.prepare(npc_name="Test", archetype="common_people")
        assert payload.patterns_included == []

    def test_prepare_with_scene_signals(self, intel):
        _seed_patterns(intel)
        payload = intel.prepare(
            npc_name="Guard",
            archetype="power_holder",
            scene_signals={"danger": 0.9, "combat": 0.5},
            scene_prompt="The attacker draws a weapon",
        )
        assert payload.behavioral_signature.archetype.value == "power_holder"

    def test_prepare_with_modifiers(self, intel):
        _seed_patterns(intel)
        payload = intel.prepare(
            npc_name="Draeven",
            archetype="specialist",
            modifiers=["paranoid", "invalid_mod"],
        )
        assert len(payload.behavioral_signature.modifiers) == 1


class TestFullLifecycle:
    def test_session_lifecycle(self, intel):
        _seed_patterns(intel)

        # Start session
        sid = intel.start_session()
        assert sid is not None

        # Prepare
        payload = intel.prepare(
            npc_name="Aldric",
            archetype="power_holder",
            trust_stage="hostile",
        )
        assert len(payload.patterns_included) > 0

        # Record accepted outcome
        result = intel.record_outcome("NPC responded correctly", accepted=True)
        assert result["output_id"] is not None
        assert len(result["patterns_updated"]) > 0

        # Proficiency should have increased
        for pid in result["patterns_updated"]:
            p = intel.get_pattern(pid)
            assert p.proficiency > 0.2

        # End session
        summary = intel.end_session()
        assert summary["exchanges"] == 1
        assert summary["patterns_active"] == 3

    def test_correction_lifecycle(self, intel):
        _seed_patterns(intel)
        intel.start_session()

        payload = intel.prepare(
            npc_name="Guard",
            archetype="power_holder",
            trust_stage="hostile",
        )

        feedback = FeedbackInput(
            original_output="The guard let them through kindly",
            user_feedback="Guard should not be kind at hostile trust",
        )
        result = intel.record_outcome(
            "The guard let them through",
            accepted=False,
            feedback=feedback,
        )
        assert result["output_id"] is not None

        intel.end_session()


class TestPatternManagement:
    def test_add_and_get(self, intel):
        p = Pattern(
            id="test-1",
            category=BehavioralCategory.ESCALATION,
            subcategory="proportional",
            description="Test",
            direction=Direction.AVOID,
        )
        intel.add_pattern(p)
        got = intel.get_pattern("test-1")
        assert got is not None
        assert got.category == BehavioralCategory.ESCALATION

    def test_list_patterns(self, intel):
        _seed_patterns(intel)
        all_p = intel.list_patterns()
        assert len(all_p) == 3

    def test_list_patterns_by_category(self, intel):
        _seed_patterns(intel)
        filtered = intel.list_patterns(category="self_interest")
        assert len(filtered) == 1
        assert filtered[0].id == "p-self"

    def test_update_pattern(self, intel):
        _seed_patterns(intel)
        p = intel.get_pattern("p-self")
        p.severity = 0.95
        intel.update_pattern(p)
        updated = intel.get_pattern("p-self")
        assert updated.severity == 0.95


class TestStats:
    def test_stats_empty_db(self, intel):
        stats = intel.get_stats()
        assert stats["total_patterns"] == 0
        assert stats["avg_proficiency"] == 0.0

    def test_stats_with_patterns(self, intel):
        _seed_patterns(intel)
        stats = intel.get_stats()
        assert stats["total_patterns"] == 3
        assert stats["avg_proficiency"] == pytest.approx(0.2, abs=0.01)
        assert stats["low_proficiency_count"] == 3
        assert stats["high_severity_count"] == 3
        assert "self_interest" in stats["by_category"]


class TestContextManager:
    def test_context_manager(self):
        with NPCIntelligence(db_path=":memory:") as intel:
            intel.add_pattern(Pattern(
                id="test-cm",
                category=BehavioralCategory.SELF_INTEREST,
                subcategory="test",
                description="Test",
                direction=Direction.AVOID,
            ))
            assert intel.get_pattern("test-cm") is not None
        # After exit, db is closed (would raise on access)
