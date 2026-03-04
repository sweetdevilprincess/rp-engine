"""Tests for TriggerEvaluator service."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from rp_engine.services.trigger_evaluator import TriggerEvaluator


@pytest.fixture
def evaluator(db):
    return TriggerEvaluator(db)


# ---------------------------------------------------------------------------
# Helper to insert triggers
# ---------------------------------------------------------------------------


async def _insert_trigger(db, trigger_id, rp_folder, name, conditions,
                          match_mode="any", inject_type="context_note",
                          inject_content="test", priority=0, cooldown=0):
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        """INSERT INTO situational_triggers
               (id, rp_folder, name, conditions, match_mode, inject_type,
                inject_content, priority, cooldown_turns, enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        [trigger_id, rp_folder, name, json.dumps(conditions), match_mode,
         inject_type, inject_content, priority, cooldown, now],
    )
    await future


# ---------------------------------------------------------------------------
# Expression function tests
# ---------------------------------------------------------------------------


class TestExpressionAny:
    def test_matches(self, evaluator):
        passed, _ = evaluator._eval_expression('any("gun","knife")', "He pulled a gun")
        assert passed is True

    def test_no_match(self, evaluator):
        passed, _ = evaluator._eval_expression('any("gun","knife")', "She smiled warmly")
        assert passed is False

    def test_case_insensitive(self, evaluator):
        passed, _ = evaluator._eval_expression('any("GUN")', "he had a gun")
        assert passed is True


class TestExpressionAll:
    def test_all_present(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'all("gun","blood")', "The gun lay in a pool of blood"
        )
        assert passed is True

    def test_one_missing(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'all("gun","blood")', "He pulled a gun"
        )
        assert passed is False


class TestExpressionNone:
    def test_none_present(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'none("gun","knife")', "She sat quietly"
        )
        assert passed is True

    def test_one_present(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'none("gun","knife")', "She picked up the knife"
        )
        assert passed is False


class TestExpressionNear:
    def test_near_within_distance(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'near("gun","dante",50)', "Dante pulled out a gun"
        )
        assert passed is True

    def test_near_too_far(self, evaluator):
        text = "Dante walked away. " + "x " * 100 + "He found a gun."
        passed, _ = evaluator._eval_expression(
            'near("dante","gun",20)', text
        )
        assert passed is False

    def test_near_default_distance(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'near("dante","gun")', "Dante pulled out a gun"
        )
        assert passed is True


class TestExpressionSeq:
    def test_correct_order(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'seq("dante","gun")', "Dante pulled a gun"
        )
        assert passed is True

    def test_wrong_order(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'seq("gun","dante")', "Dante pulled a gun"
        )
        assert passed is False


class TestExpressionCount:
    def test_count_basic(self, evaluator):
        passed, detail = evaluator._eval_expression(
            'count("blood")', "blood was everywhere, blood on the walls"
        )
        assert passed is True
        assert "2" in detail

    def test_count_with_threshold(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'count("blood", >= 3)', "blood blood"
        )
        assert passed is False

    def test_count_zero(self, evaluator):
        passed, _ = evaluator._eval_expression(
            'count("xyz")', "no match here"
        )
        assert passed is False


# ---------------------------------------------------------------------------
# Signal condition tests
# ---------------------------------------------------------------------------


class TestSignalCondition:
    def test_signal_above_threshold(self, evaluator):
        passed, _ = evaluator._eval_signal("danger", ">=", 0.5, {"danger": 0.7})
        assert passed is True

    def test_signal_below_threshold(self, evaluator):
        passed, _ = evaluator._eval_signal("danger", ">=", 0.5, {"danger": 0.3})
        assert passed is False

    def test_missing_signal(self, evaluator):
        passed, _ = evaluator._eval_signal("combat", ">", 0.0, {"danger": 0.5})
        assert passed is False


# ---------------------------------------------------------------------------
# State condition tests
# ---------------------------------------------------------------------------


class TestStateCondition:
    @pytest.mark.asyncio
    async def test_character_state(self, db, evaluator):
        card_id = "TestRP:lilith"
        # story_cards entry so trigger evaluator can find the card_id
        future = await db.enqueue_write(
            """INSERT OR REPLACE INTO story_cards
                   (id, rp_folder, file_path, card_type, name, frontmatter, indexed_at)
               VALUES (?, ?, ?, 'character', ?, '{}', '2026-01-01T00:00:00')""",
            [card_id, "TestRP", "Story Cards/Characters/Lilith.md", "Lilith"],
        )
        await future
        future = await db.enqueue_write(
            """INSERT OR REPLACE INTO character_state_entries
                   (card_id, rp_folder, branch, exchange_number, emotional_state, created_at)
               VALUES (?, ?, ?, 0, ?, '2026-01-01T00:00:00')""",
            [card_id, "TestRP", "main", "terrified"],
        )
        await future

        passed, _ = await evaluator._eval_state(
            "characters.lilith.emotional_state", "==", "terrified", None, "TestRP", "main"
        )
        assert passed is True

    @pytest.mark.asyncio
    async def test_relationship_trust(self, db, evaluator):
        future = await db.enqueue_write(
            """INSERT OR REPLACE INTO trust_baselines
                   (character_a, character_b, rp_folder, branch, baseline_score, created_at)
               VALUES (?, ?, ?, ?, ?, '2026-01-01T00:00:00')""",
            ["Lilith", "Dante", "TestRP", "main", 16],
        )
        await future
        future = await db.enqueue_write(
            """INSERT INTO trust_modifications
                   (character_a, character_b, rp_folder, branch, exchange_number,
                    change, direction, reason, date, created_at)
               VALUES (?, ?, ?, ?, 0, ?, ?, ?, '', '2026-01-01T00:00:00')""",
            ["Lilith", "Dante", "TestRP", "main", 5, "increase", "trust building"],
        )
        await future

        passed, _ = await evaluator._eval_state(
            "relationships.lilith->dante.trust_score", ">=", 20, None, "TestRP", "main"
        )
        assert passed is True  # 16 + 5 = 21

    @pytest.mark.asyncio
    async def test_scene_state(self, db, evaluator):
        future = await db.enqueue_write(
            """INSERT INTO scene_state_entries
                   (rp_folder, branch, exchange_number, mood, created_at)
               VALUES (?, ?, 0, ?, '2026-01-01T00:00:00')""",
            ["TestRP", "main", "tense"],
        )
        await future

        passed, _ = await evaluator._eval_state(
            "scene.mood", "==", "tense", None, "TestRP", "main"
        )
        assert passed is True

    @pytest.mark.asyncio
    async def test_character_not_found(self, evaluator):
        passed, detail = await evaluator._eval_state(
            "characters.nobody.emotional_state", "==", "happy", None, "TestRP", "main"
        )
        assert passed is False
        assert "not found" in detail

    @pytest.mark.asyncio
    async def test_contains_operator(self, db, evaluator):
        card_id = "TestRP:lilith"
        future = await db.enqueue_write(
            """INSERT OR REPLACE INTO story_cards
                   (id, rp_folder, file_path, card_type, name, frontmatter, indexed_at)
               VALUES (?, ?, ?, 'character', ?, '{}', '2026-01-01T00:00:00')""",
            [card_id, "TestRP", "Story Cards/Characters/Lilith.md", "Lilith"],
        )
        await future
        future = await db.enqueue_write(
            """INSERT OR REPLACE INTO character_state_entries
                   (card_id, rp_folder, branch, exchange_number, conditions, created_at)
               VALUES (?, ?, ?, 0, ?, '2026-01-01T00:00:00')""",
            [card_id, "TestRP", "main", json.dumps(["injured", "bleeding"])],
        )
        await future

        passed, _ = await evaluator._eval_state(
            "characters.lilith.conditions", "contains", "injured", None, "TestRP", "main"
        )
        assert passed is True

    @pytest.mark.asyncio
    async def test_intersects_operator(self, db, evaluator):
        card_id = "TestRP:lilith"
        future = await db.enqueue_write(
            """INSERT OR REPLACE INTO story_cards
                   (id, rp_folder, file_path, card_type, name, frontmatter, indexed_at)
               VALUES (?, ?, ?, 'character', ?, '{}', '2026-01-01T00:00:00')""",
            [card_id, "TestRP", "Story Cards/Characters/Lilith.md", "Lilith"],
        )
        await future
        future = await db.enqueue_write(
            """INSERT OR REPLACE INTO character_state_entries
                   (card_id, rp_folder, branch, exchange_number, conditions, created_at)
               VALUES (?, ?, ?, 0, ?, '2026-01-01T00:00:00')""",
            [card_id, "TestRP", "main", json.dumps(["injured", "armed"])],
        )
        await future

        passed, _ = await evaluator._eval_state(
            "characters.lilith.conditions", "intersects", None,
            ["injured", "captive"],
            "TestRP", "main"
        )
        assert passed is True


# ---------------------------------------------------------------------------
# Full evaluation tests
# ---------------------------------------------------------------------------


class TestEvaluateAll:
    @pytest.mark.asyncio
    async def test_fires_matching_trigger(self, db, evaluator):
        await _insert_trigger(
            db, "t1", "TestRP", "Danger Response",
            [{"type": "expression", "expr": 'any("gun","knife")'}],
            inject_content="Watch out!",
        )

        fired = await evaluator.evaluate_all(
            "TestRP", "main", "He pulled a gun on her", {}, 1
        )
        assert len(fired) == 1
        assert fired[0].trigger_name == "Danger Response"

    @pytest.mark.asyncio
    async def test_cooldown_prevents_firing(self, db, evaluator):
        await _insert_trigger(
            db, "t2", "TestRP", "Test",
            [{"type": "expression", "expr": 'any("hello")'}],
            cooldown=5,
        )

        # Fire once
        fired = await evaluator.evaluate_all("TestRP", "main", "hello", {}, 1)
        assert len(fired) == 1

        # Should be on cooldown
        fired = await evaluator.evaluate_all("TestRP", "main", "hello", {}, 3)
        assert len(fired) == 0

        # After cooldown
        fired = await evaluator.evaluate_all("TestRP", "main", "hello", {}, 7)
        assert len(fired) == 1

    @pytest.mark.asyncio
    async def test_match_mode_all(self, db, evaluator):
        await _insert_trigger(
            db, "t3", "TestRP", "All Match",
            [
                {"type": "expression", "expr": 'any("gun")'},
                {"type": "signal", "signal": "danger", "operator": ">=", "value": 0.5},
            ],
            match_mode="all",
        )

        # Only expression matches, not signal
        fired = await evaluator.evaluate_all("TestRP", "main", "He has a gun", {}, 1)
        assert len(fired) == 0

        # Both match
        fired = await evaluator.evaluate_all(
            "TestRP", "main", "He has a gun", {"danger": 0.7}, 2
        )
        assert len(fired) == 1

    @pytest.mark.asyncio
    async def test_priority_sorting(self, db, evaluator):
        await _insert_trigger(
            db, "t4", "TestRP", "Low Priority",
            [{"type": "expression", "expr": 'any("test")'}],
            priority=1,
        )
        await _insert_trigger(
            db, "t5", "TestRP", "High Priority",
            [{"type": "expression", "expr": 'any("test")'}],
            priority=10,
        )

        fired = await evaluator.evaluate_all("TestRP", "main", "test word", {}, 1)
        assert len(fired) == 2
        assert fired[0].trigger_name == "High Priority"


class TestEvaluateSingle:
    @pytest.mark.asyncio
    async def test_detailed_results(self, db, evaluator):
        await _insert_trigger(
            db, "t6", "TestRP", "Detail Test",
            [
                {"type": "expression", "expr": 'any("gun")'},
                {"type": "expression", "expr": 'any("knife")'},
            ],
        )

        result = await evaluator.evaluate_single(
            "t6", "He drew a gun", {}, "TestRP"
        )
        assert result.would_fire is True
        assert len(result.conditions_evaluated) == 2
        assert result.conditions_evaluated[0].matched is True
        assert result.conditions_evaluated[1].matched is False
