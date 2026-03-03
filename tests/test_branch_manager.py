"""Tests for branch management with copy-on-write branching."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from rp_engine.database import Database, PRIORITY_EXCHANGE
from rp_engine.models.state import CharacterUpdate, SceneUpdate
from rp_engine.services.branch_manager import BranchManager
from rp_engine.services.state_manager import StateManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_session(db: Database, rp_folder: str = "TestRP", branch: str = "main", session_id: str = "sess-1"):
    """Insert a session row."""
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        "INSERT INTO sessions (id, rp_folder, branch, started_at) VALUES (?, ?, ?, ?)",
        [session_id, rp_folder, branch, now],
    )
    await future
    return session_id


async def _create_exchange(db: Database, rp_folder: str = "TestRP", branch: str = "main",
                           session_id: str = "sess-1", exchange_number: int = 1,
                           user_msg: str = "hello", asst_resp: str = "world"):
    """Insert an exchange row and return its id."""
    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        """INSERT INTO exchanges (session_id, rp_folder, branch, exchange_number,
               user_message, assistant_response, analysis_status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)""",
        [session_id, rp_folder, branch, exchange_number, user_msg, asst_resp, now],
        priority=PRIORITY_EXCHANGE,
    )
    return await future


async def _seed_state(
    db: Database,
    state_manager: StateManager,
    branch_manager: BranchManager,
    rp_folder: str = "TestRP",
    branch: str = "main",
):
    """Create a session, exchange, character, relationship, scene, and events on a branch."""
    await branch_manager.ensure_main_branch(rp_folder)
    sid = await _create_session(db, rp_folder, branch)
    eid = await _create_exchange(db, rp_folder, branch, sid, exchange_number=1)

    # Character
    await state_manager.update_character(
        "Dante", CharacterUpdate(location="Penthouse", emotional_state="calm"),
        rp_folder, branch, exchange_id=eid,
    )

    # Scene
    await state_manager.update_scene(
        SceneUpdate(location="Penthouse", mood="tense"),
        rp_folder, branch, exchange_id=eid,
    )

    # Relationship
    await state_manager.update_trust(
        "Dante", "Lilith", change=2, direction="increase", reason="test trust",
        rp_folder=rp_folder, branch=branch, exchange_id=eid,
    )

    # Event
    await state_manager.add_event(
        event="Dante entered the room",
        characters=["Dante"],
        significance="medium",
        rp_folder=rp_folder, branch=branch, exchange_id=eid,
    )

    return sid, eid


# ===================================================================
# Branch CRUD Tests
# ===================================================================


class TestEnsureMainBranch:
    @pytest.mark.asyncio
    async def test_creates_main(self, db, branch_manager):
        await branch_manager.ensure_main_branch("TestRP")
        row = await db.fetch_one("SELECT * FROM branches WHERE name = 'main' AND rp_folder = 'TestRP'")
        assert row is not None
        assert row["is_active"] == 1

    @pytest.mark.asyncio
    async def test_idempotent(self, db, branch_manager):
        await branch_manager.ensure_main_branch("TestRP")
        await branch_manager.ensure_main_branch("TestRP")
        count = await db.fetch_val("SELECT COUNT(*) FROM branches WHERE name = 'main' AND rp_folder = 'TestRP'")
        assert count == 1


class TestGetActiveBranch:
    @pytest.mark.asyncio
    async def test_defaults_to_main(self, db, branch_manager):
        result = await branch_manager.get_active_branch("TestRP")
        assert result == "main"

    @pytest.mark.asyncio
    async def test_returns_active(self, db, branch_manager):
        await branch_manager.ensure_main_branch("TestRP")
        result = await branch_manager.get_active_branch("TestRP")
        assert result == "main"


class TestCreateBranch:
    @pytest.mark.asyncio
    async def test_branch_created_with_ancestry(self, db, state_manager, branch_manager):
        """Branch creation should record the parent and branch point."""
        await _seed_state(db, state_manager, branch_manager)

        info = await branch_manager.create_branch("alt", "TestRP", description="Test branch")

        assert info.created_from == "main"
        assert info.branch_point_exchange == 1
        assert info.description == "Test branch"

    @pytest.mark.asyncio
    async def test_character_state_visible_through_ancestry(self, db, state_manager, branch_manager):
        """Characters on parent branch should be visible from child via ancestry."""
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        # Character state from main should be visible on alt through ancestry
        char = await state_manager.get_character("Dante", "TestRP", "alt")
        assert char is not None
        assert char.location == "Penthouse"
        assert char.emotional_state == "calm"

    @pytest.mark.asyncio
    async def test_trust_baseline_snapshotted(self, db, state_manager, branch_manager):
        """Trust baselines should be snapshotted on branch creation."""
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        # Check trust_baselines table
        baselines = await db.fetch_all(
            "SELECT * FROM trust_baselines WHERE rp_folder = ? AND branch = ?",
            ["TestRP", "alt"],
        )
        assert len(baselines) >= 1

        # The baseline should equal the accumulated trust from main (0 initial + 2 modification)
        bl = baselines[0]
        assert bl["baseline_score"] == 2

    @pytest.mark.asyncio
    async def test_scene_visible_through_ancestry(self, db, state_manager, branch_manager):
        """Scene from parent should be visible on child through ancestry."""
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        scene = await state_manager.get_scene("TestRP", "alt")
        assert scene.location == "Penthouse"
        assert scene.mood == "tense"

    @pytest.mark.asyncio
    async def test_does_not_copy_exchanges(self, db, state_manager, branch_manager):
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        count = await db.fetch_val(
            "SELECT COUNT(*) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            ["TestRP", "alt"],
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_copies_thread_counters(self, db, state_manager, branch_manager):
        await branch_manager.ensure_main_branch("TestRP")

        now = datetime.now(timezone.utc).isoformat()
        future = await db.enqueue_write(
            "INSERT INTO plot_threads (id, rp_folder, name) VALUES (?, ?, ?)",
            ["thread1", "TestRP", "Test Thread"],
        )
        await future
        future = await db.enqueue_write(
            "INSERT INTO thread_counters (thread_id, rp_folder, branch, current_counter, updated_at) VALUES (?, ?, ?, ?, ?)",
            ["thread1", "TestRP", "main", 5, now],
        )
        await future

        await branch_manager.create_branch("alt", "TestRP")

        row = await db.fetch_one(
            "SELECT current_counter FROM thread_counters WHERE rp_folder = ? AND branch = ?",
            ["TestRP", "alt"],
        )
        assert row is not None
        assert row["current_counter"] == 5

    @pytest.mark.asyncio
    async def test_activates_new_branch(self, db, state_manager, branch_manager):
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        active = await branch_manager.get_active_branch("TestRP")
        assert active == "alt"

    @pytest.mark.asyncio
    async def test_duplicate_branch_fails(self, db, state_manager, branch_manager):
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")
        with pytest.raises(ValueError, match="already exists"):
            await branch_manager.create_branch("alt", "TestRP")


class TestSwitchBranch:
    @pytest.mark.asyncio
    async def test_switch_branch(self, db, state_manager, branch_manager):
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        assert await branch_manager.get_active_branch("TestRP") == "alt"

        previous = await branch_manager.switch_branch("main", "TestRP")
        assert previous == "alt"
        assert await branch_manager.get_active_branch("TestRP") == "main"

    @pytest.mark.asyncio
    async def test_switch_nonexistent_fails(self, db, branch_manager):
        await branch_manager.ensure_main_branch("TestRP")
        with pytest.raises(ValueError, match="not found"):
            await branch_manager.switch_branch("nonexistent", "TestRP")


class TestListBranches:
    @pytest.mark.asyncio
    async def test_list_branches(self, db, state_manager, branch_manager):
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        result = await branch_manager.list_branches("TestRP")
        assert result.active_branch == "alt"
        assert len(result.branches) == 2
        names = {b.name for b in result.branches}
        assert names == {"main", "alt"}


# ===================================================================
# Ancestry Tests
# ===================================================================


class TestAncestry:
    @pytest.mark.asyncio
    async def test_ancestry_walks_parent(self, db, state_manager, branch_manager):
        """Current branch has 2, need 5 — should get remaining from parent."""
        await _seed_state(db, state_manager, branch_manager)

        sid = "sess-1"
        for i in range(2, 6):
            await _create_exchange(db, "TestRP", "main", sid, i, f"msg{i}", f"resp{i}")

        await branch_manager.create_branch("alt", "TestRP")

        await _create_session(db, "TestRP", "alt", "sess-alt")
        await _create_exchange(db, "TestRP", "alt", "sess-alt", 6, "alt msg1", "alt resp1")
        await _create_exchange(db, "TestRP", "alt", "sess-alt", 7, "alt msg2", "alt resp2")

        rows = await branch_manager.get_exchanges_with_ancestry("TestRP", "alt", limit=5)
        assert len(rows) == 5

    @pytest.mark.asyncio
    async def test_ancestry_respects_branch_point(self, db, state_manager, branch_manager):
        """Should not include parent exchanges past the branch_point."""
        await _seed_state(db, state_manager, branch_manager)

        sid = "sess-1"
        await _create_exchange(db, "TestRP", "main", sid, 2, "msg2", "resp2")
        await _create_exchange(db, "TestRP", "main", sid, 3, "msg3", "resp3")

        await branch_manager.create_branch("alt", "TestRP")

        await _create_exchange(db, "TestRP", "main", sid, 4, "msg4", "resp4")

        rows = await branch_manager.get_exchanges_with_ancestry("TestRP", "alt", limit=10)
        exchange_numbers = [r["exchange_number"] for r in rows]
        assert 4 not in exchange_numbers

    @pytest.mark.asyncio
    async def test_ancestry_no_parent(self, db, branch_manager):
        await branch_manager.ensure_main_branch("TestRP")
        await _create_session(db, "TestRP")
        await _create_exchange(db, "TestRP", "main", "sess-1", 1)

        rows = await branch_manager.get_exchanges_with_ancestry("TestRP", "main", limit=5)
        assert len(rows) == 1


# ===================================================================
# Checkpoint Tests
# ===================================================================


class TestCheckpoints:
    @pytest.mark.asyncio
    async def test_checkpoint_create_and_list(self, db, state_manager, branch_manager):
        await _seed_state(db, state_manager, branch_manager)

        cp = await branch_manager.create_checkpoint("save1", "TestRP", "main", "First save")
        assert cp.name == "save1"
        assert cp.exchange_number == 1
        assert cp.description == "First save"

        cps = await branch_manager.list_checkpoints("TestRP", "main")
        assert len(cps) == 1
        assert cps[0].name == "save1"

    @pytest.mark.asyncio
    async def test_checkpoint_duplicate_fails(self, db, state_manager, branch_manager):
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_checkpoint("save1", "TestRP", "main")

        with pytest.raises(ValueError, match="already exists"):
            await branch_manager.create_checkpoint("save1", "TestRP", "main")

    @pytest.mark.asyncio
    async def test_checkpoint_no_exchanges_fails(self, db, branch_manager):
        await branch_manager.ensure_main_branch("TestRP")
        with pytest.raises(ValueError, match="No exchanges"):
            await branch_manager.create_checkpoint("save1", "TestRP", "main")

    @pytest.mark.asyncio
    async def test_checkpoint_restore_creates_branch(self, db, state_manager, branch_manager):
        """Restoring a checkpoint should create a new branch (not delete)."""
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_checkpoint("save1", "TestRP", "main")

        # Add more exchanges
        await _create_exchange(db, "TestRP", "main", "sess-1", 2, "msg2", "resp2")
        await _create_exchange(db, "TestRP", "main", "sess-1", 3, "msg3", "resp3")

        # Restore to checkpoint
        result = await branch_manager.restore_checkpoint("save1", "TestRP", "main")
        assert result.exchange_number == 1
        assert result.new_branch is not None
        assert "rewind" in result.new_branch

        # Original exchanges still exist on main (append-only)
        count = await db.fetch_val(
            "SELECT COUNT(*) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            ["TestRP", "main"],
        )
        assert count == 3  # all 3 exchanges preserved

        # New branch is now active
        active = await branch_manager.get_active_branch("TestRP")
        assert active == result.new_branch

        # State on new branch should be from checkpoint point (exchange 1)
        # Scene should be visible through ancestry (new_branch -> main at exchange 1)
        scene = await state_manager.get_scene("TestRP", result.new_branch)
        assert scene.location == "Penthouse"


# ===================================================================
# State Isolation Tests (CoW)
# ===================================================================


class TestStateIsolation:
    @pytest.mark.asyncio
    async def test_state_isolation_between_branches(self, db, state_manager, branch_manager):
        """Updating state on branch A should not affect branch B."""
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        # Update character on 'alt' branch
        await _create_session(db, "TestRP", "alt", "sess-alt")
        eid_alt = await _create_exchange(db, "TestRP", "alt", "sess-alt", 1)
        await state_manager.update_character(
            "Dante", CharacterUpdate(location="Airport", emotional_state="anxious"),
            "TestRP", "alt", exchange_id=eid_alt,
        )

        # Main branch should be unchanged
        char_main = await state_manager.get_character("Dante", "TestRP", "main")
        assert char_main.location == "Penthouse"
        assert char_main.emotional_state == "calm"

        # Alt branch should have updated values
        char_alt = await state_manager.get_character("Dante", "TestRP", "alt")
        assert char_alt.location == "Airport"
        assert char_alt.emotional_state == "anxious"

    @pytest.mark.asyncio
    async def test_scene_isolation_between_branches(self, db, state_manager, branch_manager):
        """Scene context should be independent per branch."""
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        # Update scene on alt
        await _create_session(db, "TestRP", "alt", "sess-alt")
        eid_alt = await _create_exchange(db, "TestRP", "alt", "sess-alt", 1)
        await state_manager.update_scene(
            SceneUpdate(location="Airport", mood="frantic"),
            "TestRP", "alt", exchange_id=eid_alt,
        )

        # Main unchanged
        scene_main = await state_manager.get_scene("TestRP", "main")
        assert scene_main.location == "Penthouse"

        # Alt updated
        scene_alt = await state_manager.get_scene("TestRP", "alt")
        assert scene_alt.location == "Airport"

    @pytest.mark.asyncio
    async def test_trust_isolation_between_branches(self, db, state_manager, branch_manager):
        """Trust changes on one branch should not affect another."""
        await _seed_state(db, state_manager, branch_manager)
        await branch_manager.create_branch("alt", "TestRP")

        # Add trust on alt branch
        await _create_session(db, "TestRP", "alt", "sess-alt")
        eid_alt = await _create_exchange(db, "TestRP", "alt", "sess-alt", 1)
        await state_manager.update_trust(
            "Dante", "Lilith", change=5, direction="increase", reason="alt trust",
            rp_folder="TestRP", branch="alt", exchange_id=eid_alt,
        )

        # Main should still have trust of 2 (from seed)
        rel_main = await state_manager.get_relationship("Dante", "Lilith", "TestRP", "main")
        assert rel_main is not None
        assert rel_main.live_trust_score == 2

        # Alt should have baseline 2 + mod 5 = 7
        rel_alt = await state_manager.get_relationship("Dante", "Lilith", "TestRP", "alt")
        assert rel_alt is not None
        assert rel_alt.live_trust_score == 7
