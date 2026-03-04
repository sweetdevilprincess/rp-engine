"""Unit tests for the StateManager service."""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio

from rp_engine.config import TrustConfig
from rp_engine.database import PRIORITY_ANALYSIS, Database
from rp_engine.services.ancestry_resolver import AncestryResolver
from rp_engine.services.state_manager import StateManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RP = "TestRP"
BRANCH = "main"


def _make_state_manager(db: Database) -> StateManager:
    resolver = AncestryResolver(db)
    return StateManager(db=db, config=TrustConfig(), resolver=resolver)


async def _insert_character(
    db: Database,
    name: str,
    rp_folder: str = RP,
    branch: str = BRANCH,
    **overrides,
) -> None:
    """Insert a character via story_cards + character_ledger + character_state_entries."""
    card_id = f"{rp_folder}:{name.lower()}"
    now = "2026-01-01T00:00:00"

    # 1. Insert story card
    fm = {
        "is_player_character": overrides.pop("is_player_character", False),
        "importance": overrides.get("importance", "main"),
        "primary_archetype": overrides.pop("primary_archetype", None),
        "secondary_archetype": overrides.pop("secondary_archetype", None),
        "behavioral_modifiers": json.loads(overrides.pop("behavioral_modifiers", "[]"))
            if isinstance(overrides.get("behavioral_modifiers"), str)
            else overrides.pop("behavioral_modifiers", []),
    }
    future = await db.enqueue_write(
        """INSERT OR IGNORE INTO story_cards
               (id, rp_folder, file_path, card_type, name, importance, frontmatter, indexed_at)
           VALUES (?, ?, ?, 'character', ?, ?, ?, ?)""",
        [card_id, rp_folder, f"Story Cards/Characters/{name}.md", name,
         overrides.pop("importance", "main"), json.dumps(fm), now],
        priority=PRIORITY_ANALYSIS,
    )
    await future

    # 2. Insert character_ledger entry
    future = await db.enqueue_write(
        """INSERT OR IGNORE INTO character_ledger
               (card_id, rp_folder, branch, status, activated_at_exchange, created_at)
           VALUES (?, ?, ?, 'active', 0, ?)""",
        [card_id, rp_folder, branch, now],
        priority=PRIORITY_ANALYSIS,
    )
    await future

    # 3. Insert runtime state if any runtime fields provided
    location = overrides.pop("location", None)
    conditions = overrides.pop("conditions", "[]")
    emotional_state = overrides.pop("emotional_state", None)
    last_seen = overrides.pop("last_seen", None)

    if location or emotional_state or last_seen or conditions != "[]":
        future = await db.enqueue_write(
            """INSERT OR REPLACE INTO character_state_entries
                   (card_id, rp_folder, branch, exchange_number,
                    location, conditions, emotional_state, last_seen, created_at)
               VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)""",
            [card_id, rp_folder, branch, location, conditions,
             emotional_state, last_seen, now],
            priority=PRIORITY_ANALYSIS,
        )
        await future


async def _insert_relationship(
    db: Database,
    char_a: str,
    char_b: str,
    rp_folder: str = RP,
    branch: str = BRANCH,
    initial_trust: int = 0,
) -> None:
    """Insert a relationship via trust_baselines."""
    now = "2026-01-01T00:00:00"
    future = await db.enqueue_write(
        """INSERT OR IGNORE INTO trust_baselines
               (character_a, character_b, rp_folder, branch,
                baseline_score, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [char_a, char_b, rp_folder, branch, initial_trust, now],
        priority=PRIORITY_ANALYSIS,
    )
    await future


async def _insert_event(
    db: Database,
    event_text: str,
    rp_folder: str = RP,
    branch: str = BRANCH,
    **overrides,
) -> int:
    defaults = {
        "rp_folder": rp_folder,
        "branch": branch,
        "in_story_timestamp": None,
        "event": event_text,
        "characters": "[]",
        "significance": "medium",
        "exchange_id": None,
        "created_at": "2026-01-01T00:00:00",
    }
    defaults.update(overrides)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join(["?"] * len(defaults))
    future = await db.enqueue_write(
        f"INSERT INTO events ({cols}) VALUES ({placeholders})",
        list(defaults.values()),
        priority=PRIORITY_ANALYSIS,
    )
    return await future


# ---------------------------------------------------------------------------
# Character State Tests
# ---------------------------------------------------------------------------


class TestCharacterState:
    @pytest.mark.asyncio
    async def test_get_character(self, db):
        await _insert_character(db, "Dante", location="warehouse", emotional_state="tense")
        sm = _make_state_manager(db)

        char = await sm.get_character("Dante", RP, BRANCH)
        assert char is not None
        assert char.name == "Dante"
        assert char.location == "warehouse"
        assert char.emotional_state == "tense"

    @pytest.mark.asyncio
    async def test_get_character_not_found(self, db):
        sm = _make_state_manager(db)
        result = await sm.get_character("Nobody", RP, BRANCH)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_characters(self, db):
        await _insert_character(db, "Dante")
        await _insert_character(db, "Lilith")
        sm = _make_state_manager(db)

        chars = await sm.get_all_characters(RP, BRANCH)
        assert len(chars) == 2
        assert "Dante" in chars
        assert "Lilith" in chars

    @pytest.mark.asyncio
    async def test_get_characters_at_location(self, db):
        await _insert_character(db, "Dante", location="warehouse")
        await _insert_character(db, "Lilith", location="penthouse")
        sm = _make_state_manager(db)

        at_warehouse = await sm.get_characters_at_location("warehouse", RP, BRANCH)
        assert len(at_warehouse) == 1
        assert at_warehouse[0].name == "Dante"

    @pytest.mark.asyncio
    async def test_update_character_creates_ledger_entry(self, db):
        """Updating a character with a story card but no ledger entry creates one."""
        # Insert story card only (no ledger/state entry)
        future = await db.enqueue_write(
            """INSERT INTO story_cards
                   (id, rp_folder, file_path, card_type, name, importance, frontmatter, indexed_at)
               VALUES (?, ?, ?, 'character', ?, 'main', '{}', '2026-01-01T00:00:00')""",
            [f"{RP}:newguy", RP, "Story Cards/Characters/NewGuy.md", "NewGuy"],
            priority=PRIORITY_ANALYSIS,
        )
        await future

        sm = _make_state_manager(db)
        from rp_engine.models.state import CharacterUpdate

        result = await sm.update_character(
            "NewGuy",
            CharacterUpdate(location="docks", emotional_state="calm"),
            RP,
            BRANCH,
        )
        assert result.name == "NewGuy"
        assert result.location == "docks"
        assert result.emotional_state == "calm"

        # Verify persisted
        fetched = await sm.get_character("NewGuy", RP, BRANCH)
        assert fetched is not None
        assert fetched.location == "docks"

    @pytest.mark.asyncio
    async def test_update_character_no_card_returns_empty(self, db):
        """Updating a character without a story card returns an empty detail."""
        sm = _make_state_manager(db)
        from rp_engine.models.state import CharacterUpdate

        result = await sm.update_character(
            "NoCard",
            CharacterUpdate(location="nowhere"),
            RP,
            BRANCH,
        )
        assert result.name == "NoCard"
        assert result.location is None  # no card = no state stored

    @pytest.mark.asyncio
    async def test_update_character_partial(self, db):
        await _insert_character(db, "Dante", location="warehouse", emotional_state="tense")
        sm = _make_state_manager(db)
        from rp_engine.models.state import CharacterUpdate

        # Only update emotional_state, location should stay
        result = await sm.update_character(
            "Dante",
            CharacterUpdate(emotional_state="calm"),
            RP,
            BRANCH,
        )
        assert result.emotional_state == "calm"
        assert result.location == "warehouse"  # preserved


# ---------------------------------------------------------------------------
# Trust Management Tests
# ---------------------------------------------------------------------------


class TestTrustManagement:
    @pytest.mark.asyncio
    async def test_update_trust_creates_relationship(self, db):
        sm = _make_state_manager(db)

        rel = await sm.update_trust(
            "Dante", "Lilith", 3, "positive", "Saved her life", RP, BRANCH
        )
        assert rel.character_a == "Dante"
        assert rel.character_b == "Lilith"
        assert rel.live_trust_score == 3
        assert rel.trust_stage == "neutral"

    @pytest.mark.asyncio
    async def test_trust_modification_recorded(self, db):
        sm = _make_state_manager(db)

        rel = await sm.update_trust(
            "Dante", "Lilith", 5, "positive", "Helped escape", RP, BRANCH
        )
        assert len(rel.modifications) == 1
        assert rel.modifications[0].change == 5
        assert rel.modifications[0].direction == "positive"
        assert rel.modifications[0].reason == "Helped escape"

    @pytest.mark.asyncio
    async def test_live_trust_score_computed(self, db):
        await _insert_relationship(db, "Dante", "Lilith", initial_trust=10)
        sm = _make_state_manager(db)

        rel = await sm.update_trust(
            "Dante", "Lilith", 5, "positive", "Trust earned", RP, BRANCH
        )
        # initial 10 + modification 5 = 15
        assert rel.live_trust_score == 15

    @pytest.mark.asyncio
    async def test_trust_stage_calculation(self, db):
        """Verify trust stages at key boundaries."""
        from rp_engine.services.context_engine import trust_stage

        assert trust_stage(-50) == "hostile"
        assert trust_stage(-36) == "hostile"
        assert trust_stage(-35) == "antagonistic"
        assert trust_stage(-21) == "antagonistic"
        assert trust_stage(-20) == "suspicious"
        assert trust_stage(-11) == "suspicious"
        assert trust_stage(-10) == "wary"
        assert trust_stage(-1) == "wary"
        assert trust_stage(0) == "neutral"
        assert trust_stage(9) == "neutral"
        assert trust_stage(10) == "familiar"
        assert trust_stage(19) == "familiar"
        assert trust_stage(20) == "trusted"
        assert trust_stage(34) == "trusted"
        assert trust_stage(35) == "devoted"
        assert trust_stage(50) == "devoted"

    @pytest.mark.asyncio
    async def test_session_cap_gain(self, db):
        """Hitting session_max_gain should prevent further increases."""
        config = TrustConfig(session_max_gain=5)
        resolver = AncestryResolver(db)
        sm = StateManager(db=db, config=config, resolver=resolver)

        # First change: +5 (hits cap exactly)
        rel = await sm.update_trust("Dante", "Lilith", 5, "positive", "Big help", RP, BRANCH)
        assert rel.live_trust_score == 5

        # Second change: should be capped to 0
        rel = await sm.update_trust("Dante", "Lilith", 3, "positive", "More help", RP, BRANCH)
        assert rel.live_trust_score == 5  # unchanged

    @pytest.mark.asyncio
    async def test_session_cap_loss(self, db):
        """Hitting session_max_loss should prevent further decreases."""
        config = TrustConfig(session_max_loss=-5)
        resolver = AncestryResolver(db)
        sm = StateManager(db=db, config=config, resolver=resolver)

        # Give initial trust to have room to lose
        await _insert_relationship(db, "Dante", "Lilith", initial_trust=20)

        # First change: -5 (hits cap exactly)
        rel = await sm.update_trust("Dante", "Lilith", -5, "negative", "Betrayal", RP, BRANCH)
        assert rel.live_trust_score == 15

        # Second change: should be capped to 0
        rel = await sm.update_trust("Dante", "Lilith", -3, "negative", "More betrayal", RP, BRANCH)
        assert rel.live_trust_score == 15  # unchanged

    @pytest.mark.asyncio
    async def test_score_clamped_to_bounds(self, db):
        """Trust score should not exceed min_score/max_score."""
        config = TrustConfig(min_score=-50, max_score=50)
        resolver = AncestryResolver(db)
        sm = StateManager(db=db, config=config, resolver=resolver)

        # Start at 45, try to add 10 -> clamped to 50
        await _insert_relationship(db, "Dante", "Lilith", initial_trust=45)
        rel = await sm.update_trust("Dante", "Lilith", 10, "positive", "Extreme", RP, BRANCH)
        assert rel.live_trust_score == 50

    @pytest.mark.asyncio
    async def test_reset_session_caps(self, db):
        sm = _make_state_manager(db)

        # Build some session trust
        await sm.update_trust("Dante", "Lilith", 5, "positive", "Help", RP, BRANCH)

        # Verify in-memory session caps are set
        cap_key = ("dante", "lilith", RP, BRANCH)
        assert sm._session_trust_caps[cap_key]["gained"] == 5

        # Reset
        await sm.reset_session_caps(RP, BRANCH)

        # In-memory caps should be cleared
        assert cap_key not in sm._session_trust_caps

    @pytest.mark.asyncio
    async def test_get_relationship_with_history(self, db):
        sm = _make_state_manager(db)

        await sm.update_trust("Dante", "Lilith", 3, "positive", "First", RP, BRANCH)
        await sm.update_trust("Dante", "Lilith", -1, "negative", "Second", RP, BRANCH)

        rel = await sm.get_relationship("Dante", "Lilith", RP, BRANCH)
        assert rel is not None
        assert len(rel.modifications) == 2
        # Most recent first
        assert rel.modifications[0].reason == "Second"
        assert rel.modifications[1].reason == "First"


# ---------------------------------------------------------------------------
# Scene Context Tests
# ---------------------------------------------------------------------------


class TestSceneContext:
    @pytest.mark.asyncio
    async def test_get_scene_empty(self, db):
        sm = _make_state_manager(db)
        scene = await sm.get_scene(RP, BRANCH)
        assert scene.location is None
        assert scene.time_of_day is None
        assert scene.mood is None

    @pytest.mark.asyncio
    async def test_update_and_get_scene(self, db):
        sm = _make_state_manager(db)
        from rp_engine.models.state import SceneUpdate

        await sm.update_scene(
            SceneUpdate(location="warehouse", time_of_day="night", mood="tense"),
            RP,
            BRANCH,
        )
        scene = await sm.get_scene(RP, BRANCH)
        assert scene.location == "warehouse"
        assert scene.time_of_day == "night"
        assert scene.mood == "tense"

    @pytest.mark.asyncio
    async def test_partial_scene_update(self, db):
        sm = _make_state_manager(db)
        from rp_engine.models.state import SceneUpdate

        # Set initial scene
        await sm.update_scene(
            SceneUpdate(location="warehouse", mood="tense"),
            RP,
            BRANCH,
        )

        # Partial update — only mood
        result = await sm.update_scene(
            SceneUpdate(mood="calm"),
            RP,
            BRANCH,
        )
        assert result.location == "warehouse"  # preserved
        assert result.mood == "calm"  # updated


# ---------------------------------------------------------------------------
# Event Tests
# ---------------------------------------------------------------------------


class TestEvents:
    @pytest.mark.asyncio
    async def test_add_and_get_event(self, db):
        sm = _make_state_manager(db)

        event = await sm.add_event(
            "Dante punched Marco",
            ["Dante", "Marco"],
            "high",
            RP,
            BRANCH,
        )
        assert event.event == "Dante punched Marco"
        assert event.characters == ["Dante", "Marco"]
        assert event.significance == "high"
        assert event.id is not None

    @pytest.mark.asyncio
    async def test_events_ordered_desc(self, db):
        sm = _make_state_manager(db)

        # Insert with different timestamps
        await _insert_event(db, "First event", created_at="2026-01-01T00:00:00")
        await _insert_event(db, "Second event", created_at="2026-01-02T00:00:00")
        await _insert_event(db, "Third event", created_at="2026-01-03T00:00:00")

        events = await sm.get_events(RP, BRANCH)
        assert len(events) == 3
        assert events[0].event == "Third event"
        assert events[2].event == "First event"

    @pytest.mark.asyncio
    async def test_events_filter_by_significance(self, db):
        sm = _make_state_manager(db)

        await _insert_event(db, "Minor thing", significance="low", created_at="2026-01-01T00:00:00")
        await _insert_event(db, "Major thing", significance="high", created_at="2026-01-02T00:00:00")

        events = await sm.get_events(RP, BRANCH, significance="high")
        assert len(events) == 1
        assert events[0].event == "Major thing"

    @pytest.mark.asyncio
    async def test_events_filter_by_character(self, db):
        sm = _make_state_manager(db)

        await _insert_event(
            db, "Dante's event",
            characters=json.dumps(["Dante"]),
            created_at="2026-01-01T00:00:00",
        )
        await _insert_event(
            db, "Lilith's event",
            characters=json.dumps(["Lilith"]),
            created_at="2026-01-02T00:00:00",
        )

        events = await sm.get_events(RP, BRANCH, character="Dante")
        assert len(events) == 1
        assert events[0].event == "Dante's event"

    @pytest.mark.asyncio
    async def test_events_limit(self, db):
        sm = _make_state_manager(db)

        for i in range(20):
            await _insert_event(
                db, f"Event {i}",
                created_at=f"2026-01-{i+1:02d}T00:00:00",
            )

        events = await sm.get_events(RP, BRANCH)
        assert len(events) == 15  # default limit


# ---------------------------------------------------------------------------
# Full State Snapshot
# ---------------------------------------------------------------------------


class TestFullState:
    @pytest.mark.asyncio
    async def test_full_state_snapshot(self, db):
        sm = _make_state_manager(db)
        from rp_engine.models.state import CharacterUpdate, SceneUpdate

        # Insert a story card for Dante so update_character works
        await _insert_character(db, "Dante")

        # Populate data
        await sm.update_character("Dante", CharacterUpdate(location="warehouse"), RP, BRANCH)
        await sm.update_trust("Dante", "Lilith", 5, "positive", "Help", RP, BRANCH)
        await sm.update_scene(SceneUpdate(location="warehouse", mood="tense"), RP, BRANCH)
        await sm.add_event("Something happened", ["Dante"], "medium", RP, BRANCH)

        snapshot = await sm.get_full_state(RP, BRANCH)

        assert "Dante" in snapshot.characters
        assert len(snapshot.relationships) == 1
        assert snapshot.scene.location == "warehouse"
        assert len(snapshot.events) == 1
        assert snapshot.branch == "main"
