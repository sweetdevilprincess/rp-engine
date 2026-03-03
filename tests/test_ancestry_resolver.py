"""Tests for the AncestryResolver service."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from rp_engine.database import Database
from rp_engine.services.ancestry_resolver import AncestryResolver


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def resolver(db):
    return AncestryResolver(db)


async def _create_branch(db, name, rp_folder, created_from=None, branch_point_exchange=None):
    """Helper to insert a branch record."""
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        """INSERT INTO branches (name, rp_folder, created_from, branch_point_exchange,
               is_active, created_at)
           VALUES (?, ?, ?, ?, FALSE, ?)""",
        [name, rp_folder, created_from, branch_point_exchange, now],
    )
    await future


async def _insert_char_state(db, card_id, rp_folder, branch, exchange_number, **kwargs):
    """Helper to insert a character_state_entries row."""
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        """INSERT INTO character_state_entries
               (card_id, rp_folder, branch, exchange_number, location, conditions,
                emotional_state, last_seen, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            card_id, rp_folder, branch, exchange_number,
            kwargs.get("location"), kwargs.get("conditions"),
            kwargs.get("emotional_state"), kwargs.get("last_seen"), now,
        ],
    )
    await future


async def _insert_scene_state(db, rp_folder, branch, exchange_number, **kwargs):
    """Helper to insert a scene_state_entries row."""
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        """INSERT INTO scene_state_entries
               (rp_folder, branch, exchange_number, location, time_of_day, mood,
                in_story_timestamp, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            rp_folder, branch, exchange_number,
            kwargs.get("location"), kwargs.get("time_of_day"),
            kwargs.get("mood"), kwargs.get("in_story_timestamp"), now,
        ],
    )
    await future


async def _insert_trust_baseline(db, char_a, char_b, rp_folder, branch,
                                  baseline_score, source_branch=None, source_exchange=None):
    """Helper to insert a trust baseline."""
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        """INSERT INTO trust_baselines
               (character_a, character_b, rp_folder, branch, baseline_score,
                source_branch, source_exchange, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [char_a, char_b, rp_folder, branch, baseline_score,
         source_branch, source_exchange, now],
    )
    await future


async def _insert_trust_mod(db, char_a, char_b, rp_folder, branch, exchange_number,
                             change, direction="positive", reason="test"):
    """Helper to insert a trust modification with new columns."""
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        """INSERT INTO trust_modifications
               (relationship_id, date, change, direction, reason, created_at,
                character_a, character_b, branch, exchange_number, rp_folder)
           VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [now[:10], change, direction, reason, now,
         char_a, char_b, branch, exchange_number, rp_folder],
    )
    await future


async def _insert_memory(db, memory_id, rp_folder, branch, exchange_number, belongs_to, title):
    """Helper to insert a memory entry."""
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        """INSERT INTO memory_entries
               (memory_id, rp_folder, branch, exchange_number, belongs_to, title, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [memory_id, rp_folder, branch, exchange_number, belongs_to, title, now],
    )
    await future


# ---------------------------------------------------------------------------
# Tests: Ancestry Chain
# ---------------------------------------------------------------------------

class TestAncestryChain:
    async def test_single_branch(self, db, resolver):
        await _create_branch(db, "main", "TestRP")

        chain = await resolver.get_ancestry_chain("TestRP", "main")
        assert len(chain) == 1
        assert chain[0][0] == "main"

    async def test_two_level_ancestry(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "branch_a", "TestRP", created_from="main", branch_point_exchange=50)

        chain = await resolver.get_ancestry_chain("TestRP", "branch_a")
        assert len(chain) == 2
        assert chain[0] == ("branch_a", 2**31)
        assert chain[1] == ("main", 50)

    async def test_three_level_ancestry(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "b1", "TestRP", created_from="main", branch_point_exchange=50)
        await _create_branch(db, "b2", "TestRP", created_from="b1", branch_point_exchange=80)

        chain = await resolver.get_ancestry_chain("TestRP", "b2")
        assert len(chain) == 3
        assert chain[0] == ("b2", 2**31)
        assert chain[1] == ("b1", 80)
        assert chain[2] == ("main", 50)

    async def test_caching(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "b1", "TestRP", created_from="main", branch_point_exchange=50)

        chain1 = await resolver.get_ancestry_chain("TestRP", "b1")
        chain2 = await resolver.get_ancestry_chain("TestRP", "b1")
        assert chain1 is chain2  # same object from cache

    async def test_cache_invalidation(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        chain1 = await resolver.get_ancestry_chain("TestRP", "main")

        resolver.invalidate_cache()
        chain2 = await resolver.get_ancestry_chain("TestRP", "main")
        assert chain1 is not chain2  # different object after invalidation


# ---------------------------------------------------------------------------
# Tests: Character State Resolution
# ---------------------------------------------------------------------------

class TestCharacterStateResolution:
    async def test_resolve_on_current_branch(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _insert_char_state(
            db, "card_dante", "TestRP", "main", 5,
            location="Penthouse", emotional_state="calm",
        )

        result = await resolver.resolve_character_state("card_dante", "TestRP", "main")
        assert result is not None
        assert result["location"] == "Penthouse"
        assert result["emotional_state"] == "calm"

    async def test_resolve_walks_to_parent(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "child", "TestRP", created_from="main", branch_point_exchange=50)
        await _insert_char_state(
            db, "card_dante", "TestRP", "main", 30,
            location="Bar", emotional_state="tense",
        )

        # child branch has no state — should resolve from parent
        result = await resolver.resolve_character_state("card_dante", "TestRP", "child")
        assert result is not None
        assert result["location"] == "Bar"
        assert result["branch"] == "main"

    async def test_child_overrides_parent(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "child", "TestRP", created_from="main", branch_point_exchange=50)
        await _insert_char_state(
            db, "card_dante", "TestRP", "main", 30,
            location="Bar",
        )
        await _insert_char_state(
            db, "card_dante", "TestRP", "child", 55,
            location="Penthouse",
        )

        result = await resolver.resolve_character_state("card_dante", "TestRP", "child")
        assert result is not None
        assert result["location"] == "Penthouse"
        assert result["branch"] == "child"

    async def test_respects_branch_point_exchange(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "child", "TestRP", created_from="main", branch_point_exchange=30)

        # State written AFTER branch point on parent should NOT be visible
        await _insert_char_state(
            db, "card_dante", "TestRP", "main", 10, location="Bar",
        )
        await _insert_char_state(
            db, "card_dante", "TestRP", "main", 40, location="Club",
        )

        result = await resolver.resolve_character_state("card_dante", "TestRP", "child")
        assert result is not None
        assert result["location"] == "Bar"  # exchange 10 <= 30 (branch point)
        # NOT "Club" which is exchange 40 > 30

    async def test_resolve_at_specific_exchange(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _insert_char_state(
            db, "card_dante", "TestRP", "main", 5, location="Bar",
        )
        await _insert_char_state(
            db, "card_dante", "TestRP", "main", 10, location="Penthouse",
        )

        result = await resolver.resolve_character_state(
            "card_dante", "TestRP", "main", exchange_number=7,
        )
        assert result is not None
        assert result["location"] == "Bar"  # exchange 5 <= 7

    async def test_resolve_returns_none(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        result = await resolver.resolve_character_state("card_nobody", "TestRP", "main")
        assert result is None

    async def test_deep_ancestry(self, db, resolver):
        """Test resolution across 3+ levels of ancestry."""
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "b1", "TestRP", created_from="main", branch_point_exchange=50)
        await _create_branch(db, "b2", "TestRP", created_from="b1", branch_point_exchange=80)
        await _create_branch(db, "b3", "TestRP", created_from="b2", branch_point_exchange=100)

        # State only exists on main
        await _insert_char_state(
            db, "card_dante", "TestRP", "main", 20, location="Bar",
        )

        # Should resolve through b3 -> b2 -> b1 -> main
        result = await resolver.resolve_character_state("card_dante", "TestRP", "b3")
        assert result is not None
        assert result["location"] == "Bar"
        assert result["branch"] == "main"


# ---------------------------------------------------------------------------
# Tests: Scene State Resolution
# ---------------------------------------------------------------------------

class TestSceneStateResolution:
    async def test_resolve_scene_on_branch(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _insert_scene_state(
            db, "TestRP", "main", 5,
            location="Bar", time_of_day="evening", mood="tense",
        )

        result = await resolver.resolve_scene_state("TestRP", "main")
        assert result is not None
        assert result["location"] == "Bar"
        assert result["time_of_day"] == "evening"

    async def test_resolve_scene_from_parent(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "child", "TestRP", created_from="main", branch_point_exchange=50)
        await _insert_scene_state(
            db, "TestRP", "main", 30, location="Bar", mood="dark",
        )

        result = await resolver.resolve_scene_state("TestRP", "child")
        assert result is not None
        assert result["location"] == "Bar"


# ---------------------------------------------------------------------------
# Tests: Trust Resolution
# ---------------------------------------------------------------------------

class TestTrustResolution:
    async def test_trust_with_baseline_and_mods(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _insert_trust_baseline(
            db, "dante", "lilith", "TestRP", "main",
            baseline_score=10,
        )
        await _insert_trust_mod(
            db, "dante", "lilith", "TestRP", "main", 5,
            change=3, direction="positive",
        )
        await _insert_trust_mod(
            db, "dante", "lilith", "TestRP", "main", 8,
            change=-1, direction="negative",
        )

        result = await resolver.resolve_trust("dante", "lilith", "TestRP", "main")
        assert result["baseline_score"] == 10
        assert result["branch_modifications_sum"] == 2  # 3 + (-1)
        assert result["live_score"] == 12

    async def test_trust_no_baseline_no_card(self, db, resolver):
        await _create_branch(db, "main", "TestRP")

        result = await resolver.resolve_trust("dante", "lilith", "TestRP", "main")
        assert result["baseline_score"] == 0
        assert result["branch_modifications_sum"] == 0
        assert result["live_score"] == 0

    async def test_trust_from_card_initial(self, db, resolver):
        await _create_branch(db, "main", "TestRP")

        # Insert a story card with initial trust
        now = datetime.now(timezone.utc).isoformat()
        fm = json.dumps({"npc_trust_levels": {"Lilith": 16}, "initial_trust_score": 16})
        future = await db.enqueue_write(
            """INSERT INTO story_cards (id, rp_folder, file_path, card_type, name, frontmatter, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ["card_dante", "TestRP", "TestRP/Story Cards/Dante.md", "character", "Dante", fm, now],
        )
        await future

        result = await resolver.resolve_trust("Dante", "Lilith", "TestRP", "main")
        assert result["baseline_score"] == 16
        assert result["live_score"] == 16

    async def test_trust_branch_isolation(self, db, resolver):
        """Modifications on one branch don't affect another."""
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "b1", "TestRP", created_from="main", branch_point_exchange=50)
        await _create_branch(db, "b2", "TestRP", created_from="main", branch_point_exchange=50)

        await _insert_trust_baseline(db, "d", "l", "TestRP", "b1", baseline_score=10,
                                      source_branch="main", source_exchange=50)
        await _insert_trust_baseline(db, "d", "l", "TestRP", "b2", baseline_score=10,
                                      source_branch="main", source_exchange=50)

        # Different mods on different branches
        await _insert_trust_mod(db, "d", "l", "TestRP", "b1", 55, change=5)
        await _insert_trust_mod(db, "d", "l", "TestRP", "b2", 55, change=-3)

        r1 = await resolver.resolve_trust("d", "l", "TestRP", "b1")
        r2 = await resolver.resolve_trust("d", "l", "TestRP", "b2")

        assert r1["live_score"] == 15  # 10 + 5
        assert r2["live_score"] == 7   # 10 + (-3)


# ---------------------------------------------------------------------------
# Tests: Collect from Ancestry
# ---------------------------------------------------------------------------

class TestCollectFromAncestry:
    async def test_collect_memories_across_branches(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "child", "TestRP", created_from="main", branch_point_exchange=50)

        await _insert_memory(db, "mem1", "TestRP", "main", 10, "lilith", "Memory on main")
        await _insert_memory(db, "mem2", "TestRP", "child", 55, "lilith", "Memory on child")

        results = await resolver.collect_from_ancestry(
            "memory_entries", "TestRP", "child",
            filters={"belongs_to": "lilith"},
        )
        assert len(results) == 2
        titles = {r["title"] for r in results}
        assert "Memory on main" in titles
        assert "Memory on child" in titles

    async def test_collect_respects_branch_point(self, db, resolver):
        await _create_branch(db, "main", "TestRP")
        await _create_branch(db, "child", "TestRP", created_from="main", branch_point_exchange=30)

        await _insert_memory(db, "mem1", "TestRP", "main", 10, "lilith", "Visible")
        await _insert_memory(db, "mem2", "TestRP", "main", 40, "lilith", "After branch point")

        results = await resolver.collect_from_ancestry(
            "memory_entries", "TestRP", "child",
            filters={"belongs_to": "lilith"},
        )
        assert len(results) == 1
        assert results[0]["title"] == "Visible"

    async def test_collect_with_limit(self, db, resolver):
        await _create_branch(db, "main", "TestRP")

        for i in range(5):
            await _insert_memory(
                db, f"mem{i}", "TestRP", "main", i + 1, "lilith", f"Memory {i}",
            )

        results = await resolver.collect_from_ancestry(
            "memory_entries", "TestRP", "main",
            filters={"belongs_to": "lilith"},
            limit=3,
        )
        assert len(results) == 3
