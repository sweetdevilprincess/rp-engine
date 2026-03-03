"""Tests for the TimestampTracker service."""

from __future__ import annotations

import pytest
import pytest_asyncio

from rp_engine.database import Database
from rp_engine.services.timestamp_tracker import TimestampTracker


@pytest_asyncio.fixture
async def ts_tracker(db: Database):
    """TimestampTracker with a scene context containing a timestamp."""
    await db.enqueue_write(
        """INSERT INTO scene_context (rp_folder, branch, location, time_of_day, mood, in_story_timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            "TestRP", "main", "The Warehouse", "evening", "tense",
            "[Wednesday, March 5, 2025 - 9:30 PM, The Warehouse]",
        ],
    )
    import asyncio
    await asyncio.sleep(0.1)
    return TimestampTracker(db)


class TestActivityDetection:
    """Test that activities are extracted correctly."""

    def test_walking_detected(self):
        acts = TimestampTracker.detect_activities("She walked down the hallway quietly.")
        names = [a["name"] for a in acts]
        assert "walk" in names

    def test_conversation_from_dialogue(self):
        acts = TimestampTracker.detect_activities(
            '"Hello," she said. "How are you?" he replied.'
        )
        names = [a["name"] for a in acts]
        assert any(n in ("talk", "chat") for n in names)

    def test_eating_detected(self):
        acts = TimestampTracker.detect_activities("She ate the dinner slowly.")
        names = [a["name"] for a in acts]
        assert "eat" in names

    def test_fighting_detected(self):
        acts = TimestampTracker.detect_activities("He attacked the guard swiftly.")
        names = [a["name"] for a in acts]
        assert "fight" in names

    def test_negation_filtered(self):
        acts = TimestampTracker.detect_activities("She did not walk anywhere.")
        names = [a["name"] for a in acts]
        assert "walk" not in names

    def test_in_dialogue_filtered(self):
        acts = TimestampTracker.detect_activities(
            'He said "She walked to the store" while sitting down.'
        )
        names = [a["name"] for a in acts]
        assert "walk" not in names

    def test_no_activities(self):
        acts = TimestampTracker.detect_activities("The room was silent.")
        # Only dialogue detection, which requires quotes
        pattern_acts = [a for a in acts if a["category"] != "conversation"]
        assert len(pattern_acts) == 0

    def test_sleeping_detected(self):
        acts = TimestampTracker.detect_activities("She slept through the night.")
        names = [a["name"] for a in acts]
        assert "sleep" in names


class TestDurationCalculation:
    """Test the parallel/sequential duration logic."""

    def test_single_activity(self):
        acts = [{"name": "walk", "category": "movement"}]
        dur = TimestampTracker.calculate_duration(acts)
        assert dur == 15  # walk = 15 min

    def test_parallel_categories(self):
        acts = [
            {"name": "walk", "category": "movement"},
            {"name": "talk", "category": "conversation"},
        ]
        dur = TimestampTracker.calculate_duration(acts)
        # Parallel: max(15, 10) = 15
        assert dur == 15

    def test_combat_always_sequential(self):
        acts = [
            {"name": "walk", "category": "movement"},
            {"name": "fight", "category": "combat"},
        ]
        dur = TimestampTracker.calculate_duration(acts)
        # max(walk=15) + combat(5) = 20
        assert dur == 20

    def test_daily_always_sequential(self):
        acts = [
            {"name": "walk", "category": "movement"},
            {"name": "eat", "category": "daily"},
        ]
        dur = TimestampTracker.calculate_duration(acts)
        # max(walk=15) + daily(30) = 45
        assert dur == 45

    def test_same_category_sums(self):
        acts = [
            {"name": "walk", "category": "movement"},
            {"name": "run", "category": "movement"},
        ]
        dur = TimestampTracker.calculate_duration(acts)
        # walk(15) + run(8) = 23
        assert dur == 23

    def test_empty_activities_default(self):
        dur = TimestampTracker.calculate_duration([])
        assert dur == 5

    def test_modifier_applied(self):
        acts = [{"name": "walk", "category": "movement"}]
        dur = TimestampTracker.calculate_duration(acts, modifier=2.0)
        assert dur == 30  # 15 * 2.0

    def test_modifier_rushed(self):
        acts = [{"name": "walk", "category": "movement"}]
        dur = TimestampTracker.calculate_duration(acts, modifier=0.6)
        assert dur == 9  # round(15 * 0.6)


class TestModifierDetection:
    """Test pace modifier detection."""

    def test_slow_modifier(self):
        name, mult = TimestampTracker._detect_modifier("She walked slowly down the hall.")
        assert name == "slow"
        assert mult == 1.5

    def test_rushed_modifier(self):
        name, mult = TimestampTracker._detect_modifier("He desperately ran for the door.")
        assert name == "rushed"
        assert mult == 0.6

    def test_no_modifier(self):
        name, mult = TimestampTracker._detect_modifier("She opened the door.")
        assert name is None
        assert mult == 1.0

    def test_most_extreme_wins(self):
        name, mult = TimestampTracker._detect_modifier(
            "She carefully and meticulously searched the room."
        )
        assert name == "thorough"
        assert mult == 2.0


class TestTimestampParsing:
    """Test timestamp parsing and formatting."""

    def test_parse_with_location(self):
        ts = TimestampTracker.parse_timestamp(
            "[Wednesday, March 5, 2025 - 9:30 PM, The Warehouse]"
        )
        assert ts is not None
        assert ts["weekday"] == "Wednesday"
        assert ts["month"] == "March"
        assert ts["day"] == 5
        assert ts["year"] == 2025
        assert ts["hour"] == 9
        assert ts["minute"] == 30
        assert ts["period"] == "PM"
        assert ts["location"] == "The Warehouse"

    def test_parse_without_location(self):
        ts = TimestampTracker.parse_timestamp(
            "[Monday, January 1, 2025 - 12:00 AM]"
        )
        assert ts is not None
        assert ts["hour"] == 12
        assert ts["period"] == "AM"
        assert ts["location"] is None

    def test_parse_no_match(self):
        ts = TimestampTracker.parse_timestamp("No timestamp here.")
        assert ts is None


class TestTimestampAdvancement:
    """Test the _advance and _format methods."""

    def test_advance_simple(self):
        ts = {
            "weekday": "Wednesday", "month": "March", "day": 5,
            "year": 2025, "hour": 9, "minute": 30, "period": "PM",
            "location": "The Warehouse",
        }
        result = TimestampTracker._advance(ts, 30)
        assert result["hour"] == 10
        assert result["minute"] == 0
        assert result["period"] == "PM"

    def test_advance_past_midnight(self):
        ts = {
            "weekday": "Wednesday", "month": "March", "day": 5,
            "year": 2025, "hour": 11, "minute": 30, "period": "PM",
            "location": None,
        }
        result = TimestampTracker._advance(ts, 60)
        assert result["hour"] == 12
        assert result["minute"] == 30
        assert result["period"] == "AM"
        assert result["weekday"] == "Thursday"
        assert result["day"] == 6

    def test_advance_am_pm_boundary(self):
        ts = {
            "weekday": "Monday", "month": "March", "day": 10,
            "year": 2025, "hour": 11, "minute": 45, "period": "AM",
            "location": None,
        }
        result = TimestampTracker._advance(ts, 30)
        assert result["hour"] == 12
        assert result["minute"] == 15
        assert result["period"] == "PM"
        assert result["weekday"] == "Monday"

    def test_format_timestamp(self):
        ts = {
            "weekday": "Wednesday", "month": "March", "day": 5,
            "year": 2025, "hour": 10, "minute": 0, "period": "PM",
            "location": "The Warehouse",
        }
        result = TimestampTracker._format(ts)
        assert result == "[Wednesday, March 5, 2025 - 10:00 PM, The Warehouse]"


class TestAdvanceTimeEndToEnd:
    """Test the full advance_time method."""

    @pytest.mark.asyncio
    async def test_advance_with_activities(self, ts_tracker: TimestampTracker):
        result = await ts_tracker.advance_time(
            "She walked down the hallway and ate the dinner.",
            "TestRP",
        )
        assert result.previous_timestamp is not None
        assert result.new_timestamp is not None
        assert result.elapsed_minutes > 0
        assert len(result.activities_detected) > 0

    @pytest.mark.asyncio
    async def test_advance_with_override(self, ts_tracker: TimestampTracker):
        result = await ts_tracker.advance_time(
            "Any text here.",
            "TestRP",
            override_minutes=60,
        )
        assert result.elapsed_minutes == 60
        assert result.new_timestamp is not None
        assert "[Wednesday, March 5, 2025 - 10:30 PM" in result.new_timestamp

    @pytest.mark.asyncio
    async def test_no_previous_timestamp(self, db: Database):
        tracker = TimestampTracker(db)
        result = await tracker.advance_time("Some text.", "NoRP")
        assert result.previous_timestamp is None
        assert result.new_timestamp is None
