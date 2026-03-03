"""Tests for npc_intelligence.classifier — BehavioralClassifier."""

import pytest
from npc_intelligence.classifier import BehavioralClassifier
from npc_intelligence.types import (
    Archetype, Modifier, TrustStage, InteractionType, SceneSignal,
)


@pytest.fixture
def clf():
    return BehavioralClassifier()


class TestArchetypeNormalization:
    def test_exact_match(self, clf):
        sig = clf.classify(archetype="power_holder")
        assert sig.archetype == Archetype.POWER_HOLDER

    def test_case_insensitive(self, clf):
        sig = clf.classify(archetype="POWER_HOLDER")
        assert sig.archetype == Archetype.POWER_HOLDER

    def test_spaces_to_underscores(self, clf):
        sig = clf.classify(archetype="common people")
        assert sig.archetype == Archetype.COMMON_PEOPLE

    def test_hyphens_to_underscores(self, clf):
        sig = clf.classify(archetype="honor-bound")
        # honor_bound is a modifier not archetype, should default
        sig2 = clf.classify(archetype="common-people")
        assert sig2.archetype == Archetype.COMMON_PEOPLE

    def test_unknown_defaults(self, clf):
        sig = clf.classify(archetype="unknown_type")
        assert sig.archetype == Archetype.COMMON_PEOPLE

    def test_none_defaults(self, clf):
        sig = clf.classify(archetype=None)
        assert sig.archetype == Archetype.COMMON_PEOPLE


class TestModifierNormalization:
    def test_valid_modifiers(self, clf):
        sig = clf.classify(modifiers=["paranoid", "honor_bound"])
        assert Modifier.PARANOID in sig.modifiers
        assert Modifier.HONOR_BOUND in sig.modifiers

    def test_skip_unrecognized(self, clf):
        sig = clf.classify(modifiers=["paranoid", "invalid_mod", "sadistic"])
        assert len(sig.modifiers) == 2
        assert Modifier.PARANOID in sig.modifiers
        assert Modifier.SADISTIC in sig.modifiers

    def test_empty_modifiers(self, clf):
        sig = clf.classify(modifiers=[])
        assert sig.modifiers == []


class TestTrustScoreMapping:
    @pytest.mark.parametrize("score,expected", [
        (-50, TrustStage.HOSTILE),
        (-36, TrustStage.HOSTILE),
        (-35, TrustStage.ANTAGONISTIC),
        (-21, TrustStage.ANTAGONISTIC),
        (-20, TrustStage.SUSPICIOUS),
        (-11, TrustStage.SUSPICIOUS),
        (-10, TrustStage.WARY),
        (-1, TrustStage.WARY),
        (0, TrustStage.NEUTRAL),
        (9, TrustStage.NEUTRAL),
        (10, TrustStage.FAMILIAR),
        (19, TrustStage.FAMILIAR),
        (20, TrustStage.TRUSTED),
        (34, TrustStage.TRUSTED),
        (35, TrustStage.DEVOTED),
        (50, TrustStage.DEVOTED),
    ])
    def test_trust_score_to_stage(self, clf, score, expected):
        sig = clf.classify(trust_score=score)
        assert sig.trust_stage == expected

    def test_clamping_below(self, clf):
        sig = clf.classify(trust_score=-100)
        assert sig.trust_stage == TrustStage.HOSTILE

    def test_clamping_above(self, clf):
        sig = clf.classify(trust_score=100)
        assert sig.trust_stage == TrustStage.DEVOTED

    def test_explicit_stage_overrides_score(self, clf):
        sig = clf.classify(trust_stage="hostile", trust_score=50)
        assert sig.trust_stage == TrustStage.HOSTILE

    def test_neutral_stage_falls_through_to_score(self, clf):
        sig = clf.classify(trust_stage="neutral", trust_score=-40)
        assert sig.trust_stage == TrustStage.HOSTILE


class TestInteractionDetection:
    def test_hostile_encounter(self, clf):
        sig = clf.classify(scene_prompt="He draws his weapon and prepares to attack")
        assert sig.interaction_type == InteractionType.HOSTILE_ENCOUNTER

    def test_confrontation(self, clf):
        sig = clf.classify(scene_prompt="She confronts him about the stolen goods")
        assert sig.interaction_type == InteractionType.CONFRONTATION

    def test_deception(self, clf):
        sig = clf.classify(scene_prompt="He tries to trick the guard")
        assert sig.interaction_type == InteractionType.DECEPTION_ATTEMPT

    def test_negotiation(self, clf):
        sig = clf.classify(scene_prompt="Let's negotiate the terms of the deal")
        assert sig.interaction_type == InteractionType.NEGOTIATION

    def test_cooperation(self, clf):
        sig = clf.classify(scene_prompt="Can you help me find the missing person?")
        assert sig.interaction_type == InteractionType.COOPERATION_REQUEST

    def test_information(self, clf):
        sig = clf.classify(scene_prompt="Tell me what you know about the senator")
        assert sig.interaction_type == InteractionType.INFORMATION_REQUEST

    def test_default_social(self, clf):
        sig = clf.classify(scene_prompt="They sit down for a quiet chat over dinner")
        assert sig.interaction_type == InteractionType.SOCIAL_INTERACTION

    def test_empty_prompt(self, clf):
        sig = clf.classify(scene_prompt="")
        assert sig.interaction_type == InteractionType.SOCIAL_INTERACTION

    def test_priority_order(self, clf):
        # "attack" (hostile) should win over "help" (cooperation)
        sig = clf.classify(scene_prompt="He attacks while asking for help")
        assert sig.interaction_type == InteractionType.HOSTILE_ENCOUNTER


class TestSceneSignalFiltering:
    def test_above_threshold(self, clf):
        sig = clf.classify(scene_signals={"danger": 0.8, "combat": 0.5})
        assert SceneSignal.DANGER in sig.scene_signals
        assert SceneSignal.COMBAT in sig.scene_signals

    def test_below_threshold(self, clf):
        sig = clf.classify(scene_signals={"danger": 0.2, "combat": 0.1})
        assert sig.scene_signals == []

    def test_at_threshold(self, clf):
        sig = clf.classify(scene_signals={"danger": 0.3})
        assert SceneSignal.DANGER in sig.scene_signals

    def test_unknown_signal_skipped(self, clf):
        sig = clf.classify(scene_signals={"unknown_signal": 0.9, "danger": 0.5})
        assert len(sig.scene_signals) == 1
        assert SceneSignal.DANGER in sig.scene_signals


class TestOverride:
    def test_override_archetype(self, clf):
        sig = clf.classify(archetype="common_people",
                           override={"archetype": "opposition"})
        assert sig.archetype == Archetype.OPPOSITION

    def test_override_trust_stage(self, clf):
        sig = clf.classify(trust_score=0,
                           override={"trust_stage": "devoted"})
        assert sig.trust_stage == TrustStage.DEVOTED

    def test_override_interaction_type(self, clf):
        sig = clf.classify(scene_prompt="quiet chat",
                           override={"interaction_type": "hostile_encounter"})
        assert sig.interaction_type == InteractionType.HOSTILE_ENCOUNTER

    def test_override_modifiers(self, clf):
        sig = clf.classify(modifiers=["paranoid"],
                           override={"modifiers": ["sadistic", "narcissistic"]})
        assert len(sig.modifiers) == 2
        assert Modifier.SADISTIC in sig.modifiers

    def test_override_scene_signals(self, clf):
        sig = clf.classify(scene_signals={"danger": 0.9},
                           override={"scene_signals": ["intimate"]})
        assert sig.scene_signals == [SceneSignal.INTIMATE]
