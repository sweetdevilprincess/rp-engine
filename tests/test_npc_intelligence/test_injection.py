"""Tests for npc_intelligence.injection — BehavioralInjectionFormatter."""

import pytest
from npc_intelligence.injection import BehavioralInjectionFormatter
from npc_intelligence.types import (
    BehavioralCategory, BehavioralSignature, CorrectionPair, Direction,
    Pattern, ScoredPattern, Archetype, Modifier, TrustStage,
    InteractionType, SceneSignal,
)


@pytest.fixture
def formatter():
    return BehavioralInjectionFormatter(token_budget=500)


def _make_sig():
    return BehavioralSignature(
        archetype=Archetype.POWER_HOLDER,
        modifiers=[Modifier.PARANOID],
        trust_stage=TrustStage.SUSPICIOUS,
        interaction_type=InteractionType.NEGOTIATION,
        scene_signals=[SceneSignal.DANGER],
    )


def _make_scored(id="p1", level="critical", score=0.8, proficiency=0.2,
                 has_correction=False):
    pattern = Pattern(
        id=id,
        category=BehavioralCategory.SELF_INTEREST,
        subcategory="test",
        description="NPC actions require traceable motivation",
        direction=Direction.AVOID,
        severity=0.8,
        proficiency=proficiency,
        compressed_rule="Every action needs a self-interest reason",
    )
    if has_correction:
        pattern.correction_pairs = [CorrectionPair(
            id="cp1", pattern_id=id,
            original="The guard let them pass out of kindness",
            revised="The guard let them pass because the bribe was worth more than the risk",
            tokens_original=8, tokens_revised=14,
        )]
    return ScoredPattern(pattern=pattern, score=score,
                         relevance=0.7, injection_level=level)


class TestFormat:
    def test_npc_header(self, formatter):
        sig = _make_sig()
        scored = [_make_scored()]
        payload = formatter.format(scored, sig, npc_name="Aldric")
        assert "[NPC BEHAVIORAL CONSTRAINTS — Aldric]" in payload.text
        assert "[END NPC BEHAVIORAL CONSTRAINTS]" in payload.text

    def test_context_line(self, formatter):
        sig = _make_sig()
        scored = [_make_scored()]
        payload = formatter.format(scored, sig, npc_name="Test")
        assert "Power Holder" in payload.text
        assert "Suspicious" in payload.text
        assert "Paranoid" in payload.text
        assert "Danger" in payload.text

    def test_npc_name_in_payload(self, formatter):
        sig = _make_sig()
        payload = formatter.format([], sig, npc_name="Petra")
        assert payload.npc_name == "Petra"

    def test_behavioral_signature_in_payload(self, formatter):
        sig = _make_sig()
        payload = formatter.format([], sig)
        assert payload.behavioral_signature == sig

    def test_critical_section(self, formatter):
        sig = _make_sig()
        scored = [_make_scored(level="critical", has_correction=True)]
        payload = formatter.format(scored, sig)
        assert "CRITICAL (low proficiency):" in payload.text
        assert "EXAMPLE" in payload.text

    def test_moderate_section(self, formatter):
        sig = _make_sig()
        scored = [_make_scored(level="moderate")]
        payload = formatter.format(scored, sig)
        assert "MODERATE (rising proficiency):" in payload.text

    def test_reminder_section(self, formatter):
        sig = _make_sig()
        scored = [_make_scored(level="reminder")]
        payload = formatter.format(scored, sig)
        assert "REMINDER (high proficiency):" in payload.text

    def test_empty_patterns(self, formatter):
        sig = _make_sig()
        payload = formatter.format([], sig, npc_name="Test")
        assert payload.patterns_included == []
        assert "[NPC BEHAVIORAL CONSTRAINTS" in payload.text

    def test_token_budget_respected(self):
        # Use a tiny budget
        fmt = BehavioralInjectionFormatter(token_budget=100)
        sig = _make_sig()
        scored = [_make_scored(f"p{i}", has_correction=True) for i in range(20)]
        payload = fmt.format(scored, sig)
        # Should include fewer than all 20 patterns
        assert len(payload.patterns_included) < 20

    def test_patterns_included_tracked(self, formatter):
        sig = _make_sig()
        scored = [_make_scored("p1"), _make_scored("p2")]
        payload = formatter.format(scored, sig)
        assert "p1" in payload.patterns_included
        assert "p2" in payload.patterns_included


class TestFormatLevels:
    def test_critical_with_correction(self, formatter):
        pattern = Pattern(
            id="p1", category=BehavioralCategory.SELF_INTEREST,
            subcategory="test", description="Test desc",
            direction=Direction.AVOID,
            correction_pairs=[CorrectionPair(
                id="cp1", pattern_id="p1",
                original="bad", revised="good",
                tokens_original=1, tokens_revised=1,
            )],
        )
        text = formatter._format_critical(pattern)
        assert "Test desc" in text
        assert 'Instead of: "bad"' in text
        assert 'Write: "good"' in text

    def test_critical_without_correction_falls_back(self, formatter):
        pattern = Pattern(
            id="p1", category=BehavioralCategory.SELF_INTEREST,
            subcategory="test", description="Test desc",
            direction=Direction.AVOID,
            compressed_rule="Short rule",
        )
        text = formatter._format_critical(pattern)
        assert "Short rule" in text

    def test_moderate_uses_compressed_rule(self, formatter):
        pattern = Pattern(
            id="p1", category=BehavioralCategory.SELF_INTEREST,
            subcategory="test", description="Long description here",
            direction=Direction.AVOID,
            compressed_rule="Short rule",
        )
        text = formatter._format_moderate(pattern)
        assert text == "- Short rule"

    def test_reminder_uses_first_sentence(self, formatter):
        pattern = Pattern(
            id="p1", category=BehavioralCategory.SELF_INTEREST,
            subcategory="test",
            description="First sentence. Second sentence. Third.",
            direction=Direction.AVOID,
        )
        text = formatter._format_reminder(pattern)
        assert text == "- First sentence"
