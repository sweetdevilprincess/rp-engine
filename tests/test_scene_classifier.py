"""Tests for SceneClassifier service."""

from __future__ import annotations

import json

import pytest

from rp_engine.services.scene_classifier import SceneClassifier


@pytest.fixture
def classifier(db):
    return SceneClassifier(db)


class TestTextScoring:
    @pytest.mark.asyncio
    async def test_danger_signal(self, classifier):
        signals = await classifier.classify(
            "He pulled a gun and pointed it at her head",
            None,
            "TestRP",
        )
        assert "danger" in signals
        assert signals["danger"] > 0.3

    @pytest.mark.asyncio
    async def test_emotional_signal(self, classifier):
        signals = await classifier.classify(
            "She couldn't stop the tears from falling. The grief was overwhelming.",
            None,
            "TestRP",
        )
        assert "emotional" in signals
        assert signals["emotional"] > 0.3

    @pytest.mark.asyncio
    async def test_intimate_signal(self, classifier):
        signals = await classifier.classify(
            "He pulled her close and kissed her gently, his lips warm against hers",
            None,
            "TestRP",
        )
        assert "intimate" in signals
        assert signals["intimate"] > 0.3

    @pytest.mark.asyncio
    async def test_no_signals_for_neutral(self, classifier):
        signals = await classifier.classify(
            "She sat at the desk and read a book.",
            None,
            "TestRP",
        )
        # Should have no signals above 0.3
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_multiple_signals(self, classifier):
        signals = await classifier.classify(
            "She screamed as the knife slashed through the air. Tears streamed down her face.",
            None,
            "TestRP",
        )
        assert "danger" in signals
        assert "emotional" in signals

    @pytest.mark.asyncio
    async def test_includes_last_response(self, classifier):
        signals = await classifier.classify(
            "What do we do now?",
            "He aimed the gun at the door. Blood pooled on the floor.",
            "TestRP",
        )
        assert "danger" in signals

    @pytest.mark.asyncio
    async def test_normalization_bounded(self, classifier):
        signals = await classifier.classify(
            "gun knife weapon shoot stab kill attack blood wound dead die murder bomb explosion "
            "threat danger hurt hit punch fight scream run escape chase",
            None,
            "TestRP",
        )
        for score in signals.values():
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_threshold_filtering(self, classifier):
        # With high threshold, fewer signals pass
        signals = await classifier.classify(
            "He pulled a gun. She was afraid.",
            None,
            "TestRP",
            threshold=0.6,
        )
        # Only strong signals should pass
        for score in signals.values():
            assert score >= 0.6


class TestStateBoosts:
    @pytest.mark.asyncio
    async def test_condition_boost(self, db, classifier):
        # Insert a character with "injured" condition
        future = await db.enqueue_write(
            "INSERT INTO characters (id, rp_folder, branch, name, conditions) VALUES (?, ?, ?, ?, ?)",
            ["test:lilith", "TestRP", "main", "Lilith", json.dumps(["injured"])],
        )
        await future

        signals = await classifier.classify(
            "She walked through the dark alley alone.",
            None,
            "TestRP",
        )
        # "dark", "alley", "alone" are low-danger keywords
        # "injured" condition should boost danger signal
        assert "danger" in signals

    @pytest.mark.asyncio
    async def test_mood_boost(self, db, classifier):
        # Insert scene with romantic mood
        future = await db.enqueue_write(
            "INSERT INTO scene_context (rp_folder, branch, mood) VALUES (?, ?, ?)",
            ["TestRP", "main", "romantic"],
        )
        await future

        signals = await classifier.classify(
            "They sat close together, his gaze lingering on her eyes, a shy smile on her lips.",
            None,
            "TestRP",
        )
        assert "intimate" in signals

    @pytest.mark.asyncio
    async def test_emotional_state_boost(self, db, classifier):
        future = await db.enqueue_write(
            "INSERT INTO characters (id, rp_folder, branch, name, emotional_state) VALUES (?, ?, ?, ?, ?)",
            ["test:lilith", "TestRP", "main", "Lilith", "grief"],
        )
        await future

        signals = await classifier.classify(
            "She sat alone quietly in the room, pensive and withdrawn.",
            None,
            "TestRP",
        )
        assert "emotional" in signals
