"""Tests for the ThreadTracker service."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio

from rp_engine.database import Database
from rp_engine.services.thread_tracker import ThreadTracker


@pytest_asyncio.fixture
async def tracker(db: Database):
    """ThreadTracker with a pre-populated thread."""
    # Insert a plot thread
    await db.enqueue_write(
        """INSERT INTO plot_threads (id, rp_folder, name, thread_type, priority, status, keywords, thresholds, consequences, related_characters)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "dante_tension",
            "TestRP",
            "Dante-Lilith Tension",
            "Romance",
            "plot_critical",
            "active",
            json.dumps(["dante", "lilith", "attraction"]),
            json.dumps({"gentle": 3, "moderate": 6, "strong": 9}),
            json.dumps({"gentle": "Drop a hint", "moderate": "Force encounter", "strong": "Crisis point"}),
            json.dumps(["Dante Moretti", "Lilith Graves"]),
        ],
    )
    await db.enqueue_write(
        """INSERT INTO plot_threads (id, rp_folder, name, thread_type, priority, status, keywords, thresholds, consequences, related_characters)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "warehouse_secret",
            "TestRP",
            "Warehouse Secret",
            "Mystery",
            "important",
            "active",
            json.dumps(["warehouse", "shipment", "drugs"]),
            json.dumps({"gentle": 5, "moderate": 10, "strong": 15}),
            json.dumps({}),
            json.dumps(["Marco"]),
        ],
    )
    # Add a resolved thread (should be skipped)
    await db.enqueue_write(
        """INSERT INTO plot_threads (id, rp_folder, name, thread_type, priority, status, keywords, thresholds, consequences, related_characters)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "resolved_thread",
            "TestRP",
            "Old Plot",
            "Resolved",
            "low",
            "resolved",
            json.dumps(["old"]),
            json.dumps({"gentle": 5, "moderate": 10, "strong": 15}),
            json.dumps({}),
            json.dumps([]),
        ],
    )
    import asyncio
    await asyncio.sleep(0.1)  # let writes flush
    return ThreadTracker(db)


class TestKeywordMatching:
    """Test that thread mention detection works correctly."""

    @pytest.mark.asyncio
    async def test_keyword_resets_counter(self, tracker: ThreadTracker):
        alerts = await tracker.update_counters(
            "Dante looked at Lilith with a mix of attraction and anger.",
            "TestRP",
        )
        threads = await tracker.get_all_threads("TestRP")
        dante_thread = next(t for t in threads if t.thread_id == "dante_tension")
        assert dante_thread.current_counter == 0

    @pytest.mark.asyncio
    async def test_no_mention_increments(self, tracker: ThreadTracker):
        alerts = await tracker.update_counters(
            "The rain fell steadily on the roof of the old building.",
            "TestRP",
        )
        threads = await tracker.get_all_threads("TestRP")
        dante_thread = next(t for t in threads if t.thread_id == "dante_tension")
        assert dante_thread.current_counter == 1

    @pytest.mark.asyncio
    async def test_case_insensitive(self, tracker: ThreadTracker):
        alerts = await tracker.update_counters(
            "DANTE walked through the door.",
            "TestRP",
        )
        threads = await tracker.get_all_threads("TestRP")
        dante_thread = next(t for t in threads if t.thread_id == "dante_tension")
        assert dante_thread.current_counter == 0

    @pytest.mark.asyncio
    async def test_character_name_mention(self, tracker: ThreadTracker):
        """Related character names also count as mentions."""
        alerts = await tracker.update_counters(
            "Dante Moretti entered the room without a word.",
            "TestRP",
        )
        threads = await tracker.get_all_threads("TestRP")
        dante_thread = next(t for t in threads if t.thread_id == "dante_tension")
        assert dante_thread.current_counter == 0

    @pytest.mark.asyncio
    async def test_multiple_updates_accumulate(self, tracker: ThreadTracker):
        """Counter increments on each call without mention."""
        for _ in range(3):
            await tracker.update_counters("Nothing relevant here.", "TestRP")

        threads = await tracker.get_all_threads("TestRP")
        dante_thread = next(t for t in threads if t.thread_id == "dante_tension")
        assert dante_thread.current_counter == 3


class TestThresholds:
    """Test threshold-based alert generation."""

    @pytest.mark.asyncio
    async def test_gentle_alert(self, tracker: ThreadTracker):
        # Increment past gentle threshold (3)
        for _ in range(3):
            alerts = await tracker.update_counters("Boring text.", "TestRP")

        assert len(alerts) > 0
        dante_alert = next(
            (a for a in alerts if a.thread_id == "dante_tension"), None
        )
        assert dante_alert is not None
        assert dante_alert.level == "gentle"
        assert dante_alert.counter == 3
        assert dante_alert.consequence == "Drop a hint"

    @pytest.mark.asyncio
    async def test_moderate_alert(self, tracker: ThreadTracker):
        for _ in range(6):
            alerts = await tracker.update_counters("Boring text.", "TestRP")

        dante_alert = next(
            (a for a in alerts if a.thread_id == "dante_tension"), None
        )
        assert dante_alert is not None
        assert dante_alert.level == "moderate"

    @pytest.mark.asyncio
    async def test_strong_alert(self, tracker: ThreadTracker):
        for _ in range(9):
            alerts = await tracker.update_counters("Boring text.", "TestRP")

        dante_alert = next(
            (a for a in alerts if a.thread_id == "dante_tension"), None
        )
        assert dante_alert is not None
        assert dante_alert.level == "strong"
        assert dante_alert.consequence == "Crisis point"

    @pytest.mark.asyncio
    async def test_reset_clears_alert(self, tracker: ThreadTracker):
        # Build up to gentle alert
        for _ in range(4):
            await tracker.update_counters("Boring text.", "TestRP")

        # Mention resets
        alerts = await tracker.update_counters("Dante said hello.", "TestRP")
        dante_alert = next(
            (a for a in alerts if a.thread_id == "dante_tension"), None
        )
        assert dante_alert is None

    @pytest.mark.asyncio
    async def test_no_alert_below_threshold(self, tracker: ThreadTracker):
        alerts = await tracker.update_counters("Boring text.", "TestRP")
        dante_alert = next(
            (a for a in alerts if a.thread_id == "dante_tension"), None
        )
        assert dante_alert is None


class TestResolvedThreads:
    """Resolved threads should be excluded from counter updates."""

    @pytest.mark.asyncio
    async def test_resolved_thread_skipped(self, tracker: ThreadTracker):
        await tracker.update_counters("Something about old topics.", "TestRP")
        threads = await tracker.get_all_threads("TestRP")
        resolved = [t for t in threads if t.thread_id == "resolved_thread"]
        # It should exist in all threads but not have counter updated
        assert len(resolved) == 1
        assert resolved[0].status == "resolved"


class TestGetAlerts:
    """Test the get_alerts method for current state."""

    @pytest.mark.asyncio
    async def test_alerts_reflect_current_state(self, tracker: ThreadTracker):
        for _ in range(4):
            await tracker.update_counters("Nothing here.", "TestRP")

        alerts = await tracker.get_alerts("TestRP")
        assert len(alerts) > 0
        assert any(a.thread_id == "dante_tension" for a in alerts)


class TestGetThread:
    """Test single-thread retrieval."""

    @pytest.mark.asyncio
    async def test_get_existing_thread(self, tracker: ThreadTracker):
        thread = await tracker.get_thread("dante_tension", "TestRP")
        assert thread is not None
        assert thread.name == "Dante-Lilith Tension"
        assert "dante" in thread.keywords

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, tracker: ThreadTracker):
        thread = await tracker.get_thread("nope", "TestRP")
        assert thread is None


class TestIndependentThreads:
    """Test that threads are tracked independently."""

    @pytest.mark.asyncio
    async def test_one_mentioned_other_not(self, tracker: ThreadTracker):
        await tracker.update_counters(
            "The warehouse shipment arrived tonight.",
            "TestRP",
        )
        threads = await tracker.get_all_threads("TestRP")
        dante_thread = next(t for t in threads if t.thread_id == "dante_tension")
        warehouse_thread = next(t for t in threads if t.thread_id == "warehouse_secret")
        assert dante_thread.current_counter == 1  # not mentioned
        assert warehouse_thread.current_counter == 0  # mentioned via keyword
