"""Tests for npc_intelligence.types — enums, BehavioralSignature, dataclasses."""

import pytest
from npc_intelligence.types import (
    Archetype, Modifier, TrustStage, InteractionType, SceneSignal,
    BehavioralCategory, Direction,
    BehavioralSignature, Pattern, CorrectionPair, ScoredPattern,
    InjectionPayload, FeedbackInput, ExtractionResult,
)


class TestEnums:
    def test_archetype_values(self):
        assert Archetype.POWER_HOLDER == "power_holder"
        assert Archetype.TRANSACTIONAL == "transactional"
        assert len(Archetype) == 7

    def test_modifier_values(self):
        assert Modifier.PARANOID == "paranoid"
        assert Modifier.HONOR_BOUND == "honor_bound"
        assert len(Modifier) == 9

    def test_trust_stage_values(self):
        assert TrustStage.HOSTILE == "hostile"
        assert TrustStage.DEVOTED == "devoted"
        assert len(TrustStage) == 8

    def test_interaction_type_values(self):
        assert InteractionType.HOSTILE_ENCOUNTER == "hostile_encounter"
        assert len(InteractionType) == 7

    def test_scene_signal_values(self):
        assert SceneSignal.DANGER == "danger"
        assert len(SceneSignal) == 6

    def test_behavioral_category_values(self):
        assert BehavioralCategory.SELF_INTEREST == "self_interest"
        assert BehavioralCategory.KNOWLEDGE_BOUNDARY == "knowledge_boundary"
        assert len(BehavioralCategory) == 11

    def test_direction_values(self):
        assert Direction.AVOID == "avoid"
        assert Direction.PREFER == "prefer"

    def test_enums_are_str(self):
        """All enums should be str subclasses for JSON serialization."""
        assert isinstance(Archetype.POWER_HOLDER, str)
        assert isinstance(Modifier.PARANOID, str)
        assert isinstance(TrustStage.HOSTILE, str)


class TestBehavioralSignature:
    def test_creation(self):
        sig = BehavioralSignature(
            archetype=Archetype.POWER_HOLDER,
            modifiers=[Modifier.PARANOID, Modifier.HONOR_BOUND],
            trust_stage=TrustStage.SUSPICIOUS,
            interaction_type=InteractionType.NEGOTIATION,
            scene_signals=[SceneSignal.DANGER],
        )
        assert sig.archetype == Archetype.POWER_HOLDER
        assert len(sig.modifiers) == 2
        assert sig.trust_stage == TrustStage.SUSPICIOUS

    def test_all_trigger_values(self):
        sig = BehavioralSignature(
            archetype=Archetype.OPPOSITION,
            modifiers=[Modifier.SADISTIC],
            trust_stage=TrustStage.HOSTILE,
            interaction_type=InteractionType.HOSTILE_ENCOUNTER,
            scene_signals=[SceneSignal.COMBAT, SceneSignal.DANGER],
        )
        triggers = sig.all_trigger_values()
        assert "opposition" in triggers
        assert "sadistic" in triggers
        assert "hostile" in triggers
        assert "hostile_encounter" in triggers
        assert "combat" in triggers
        assert "danger" in triggers
        assert len(triggers) == 6

    def test_all_trigger_values_empty_lists(self):
        sig = BehavioralSignature(
            archetype=Archetype.COMMON_PEOPLE,
            modifiers=[],
            trust_stage=TrustStage.NEUTRAL,
            interaction_type=InteractionType.SOCIAL_INTERACTION,
            scene_signals=[],
        )
        triggers = sig.all_trigger_values()
        assert triggers == {"common_people", "neutral", "social_interaction"}

    def test_from_dict_full(self):
        sig = BehavioralSignature.from_dict({
            "archetype": "power_holder",
            "modifiers": ["paranoid"],
            "trust_stage": "hostile",
            "interaction_type": "confrontation",
            "scene_signals": ["danger", "combat"],
        })
        assert sig.archetype == Archetype.POWER_HOLDER
        assert sig.modifiers == [Modifier.PARANOID]
        assert sig.trust_stage == TrustStage.HOSTILE
        assert sig.interaction_type == InteractionType.CONFRONTATION
        assert len(sig.scene_signals) == 2

    def test_from_dict_defaults(self):
        sig = BehavioralSignature.from_dict({})
        assert sig.archetype == Archetype.COMMON_PEOPLE
        assert sig.modifiers == []
        assert sig.trust_stage == TrustStage.NEUTRAL
        assert sig.interaction_type == InteractionType.SOCIAL_INTERACTION
        assert sig.scene_signals == []

    def test_from_dict_partial(self):
        sig = BehavioralSignature.from_dict({"archetype": "opposition"})
        assert sig.archetype == Archetype.OPPOSITION
        assert sig.trust_stage == TrustStage.NEUTRAL


class TestPattern:
    def test_pattern_defaults(self):
        p = Pattern(
            id="test-1",
            category=BehavioralCategory.SELF_INTEREST,
            subcategory="motivation",
            description="Test pattern",
            direction=Direction.AVOID,
        )
        assert p.severity == 0.5
        assert p.frequency == 0
        assert p.proficiency == 0.2
        assert p.context_triggers == []
        assert p.correction_pairs == []


class TestInjectionPayload:
    def test_npc_name_field(self):
        sig = BehavioralSignature.from_dict({})
        payload = InjectionPayload(
            text="test",
            token_count=5,
            patterns_included=["p1"],
            behavioral_signature=sig,
            npc_name="Aldric",
        )
        assert payload.npc_name == "Aldric"
        assert payload.behavioral_signature == sig

    def test_npc_name_default(self):
        sig = BehavioralSignature.from_dict({})
        payload = InjectionPayload(
            text="test",
            token_count=5,
            patterns_included=[],
            behavioral_signature=sig,
        )
        assert payload.npc_name == ""
