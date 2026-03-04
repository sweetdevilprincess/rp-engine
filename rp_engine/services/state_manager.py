"""Centralized state management using copy-on-write branching.

Characters, relationships, scenes, and events are resolved through the branch
ancestry graph. State is stored as CoW snapshots (character_state_entries,
scene_state_entries) and trust modifications with direct branch/exchange columns.

Cards are read-only — all runtime state lives in the DB, scoped by branch.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from rp_engine.config import TrustConfig
from rp_engine.database import PRIORITY_ANALYSIS, Database
from rp_engine.models.context import SceneState
from rp_engine.models.state import (
    CharacterDetail,
    CharacterUpdate,
    EventDetail,
    RelationshipDetail,
    SceneUpdate,
    StateSnapshot,
    TrustModification,
)
from rp_engine.services.ancestry_resolver import AncestryResolver
from rp_engine.services.context_engine import trust_stage
from rp_engine.utils.json_helpers import safe_parse_json, safe_parse_json_list

logger = logging.getLogger(__name__)


class StateManager:
    """Manages character state, relationships/trust, scene context, and events.

    Uses AncestryResolver for branch-aware state resolution.
    """

    def __init__(self, db: Database, config: TrustConfig, resolver: AncestryResolver | None = None) -> None:
        self.db = db
        self.config = config
        self.resolver = resolver
        # In-memory session trust caps (session-scoped, reset at session start)
        # key: (char_a, char_b, rp_folder, branch) -> {"gained": int, "lost": int}
        self._session_trust_caps: dict[tuple[str, str, str, str], dict[str, int]] = {}

    # ===================================================================
    # Exchange Number Resolution
    # ===================================================================

    async def _resolve_exchange_number(
        self, exchange_id: int | None, rp_folder: str, branch: str
    ) -> int:
        """Resolve an exchange_id to an exchange_number, or get the latest."""
        if exchange_id is not None:
            row = await self.db.fetch_one(
                "SELECT exchange_number FROM exchanges WHERE id = ?", [exchange_id]
            )
            if row:
                return row["exchange_number"]
        # Fall back to latest exchange_number on this branch
        latest = await self.db.fetch_val(
            "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
        return latest or 0

    # ===================================================================
    # Character State
    # ===================================================================

    async def get_character(
        self, name: str, rp_folder: str, branch: str = "main"
    ) -> CharacterDetail | None:
        """Fetch a single character by name, resolving state through ancestry."""
        # 1. Find the character's card in story_cards
        card = await self.db.fetch_one(
            """SELECT * FROM story_cards
               WHERE rp_folder = ? AND LOWER(name) = LOWER(?)
                 AND card_type IN ('character', 'npc')""",
            [rp_folder, name],
        )
        if not card:
            return None

        # 2. Resolve runtime state through ancestry
        runtime = None
        if self.resolver:
            runtime = await self.resolver.resolve_character_state(
                card["id"], rp_folder, branch
            )

        # 3. Build CharacterDetail from card + runtime state
        fm = safe_parse_json(card.get("frontmatter"))

        return CharacterDetail(
            name=card["name"],
            card_path=card.get("file_path"),
            is_player_character=bool(fm.get("is_player_character", False)),
            importance=card.get("importance") or fm.get("importance"),
            primary_archetype=fm.get("primary_archetype"),
            secondary_archetype=fm.get("secondary_archetype"),
            behavioral_modifiers=safe_parse_json_list(fm.get("behavioral_modifiers")),
            location=runtime.get("location") if runtime else None,
            conditions=safe_parse_json_list(runtime.get("conditions") if runtime else None),
            emotional_state=runtime.get("emotional_state") if runtime else None,
            last_seen=runtime.get("last_seen") if runtime else None,
            updated_at=runtime.get("created_at") if runtime else None,
        )

    async def get_all_characters(
        self, rp_folder: str, branch: str = "main"
    ) -> dict[str, CharacterDetail]:
        """Fetch all characters, resolving state through ancestry."""
        # Get active characters from ledger
        ledger_rows = await self.db.fetch_all(
            "SELECT * FROM character_ledger WHERE rp_folder = ? AND branch = ? AND status = 'active'",
            [rp_folder, branch],
        )

        result = {}
        for lr in ledger_rows:
            card = await self.db.fetch_one(
                "SELECT * FROM story_cards WHERE id = ?", [lr["card_id"]]
            )
            if not card:
                continue

            runtime = None
            if self.resolver:
                runtime = await self.resolver.resolve_character_state(
                    lr["card_id"], rp_folder, branch
                )

            fm = safe_parse_json(card.get("frontmatter"))

            detail = CharacterDetail(
                name=card["name"],
                card_path=card.get("file_path"),
                is_player_character=bool(fm.get("is_player_character", False)),
                importance=card.get("importance") or fm.get("importance"),
                primary_archetype=fm.get("primary_archetype"),
                secondary_archetype=fm.get("secondary_archetype"),
                behavioral_modifiers=safe_parse_json_list(fm.get("behavioral_modifiers")),
                location=runtime.get("location") if runtime else None,
                conditions=safe_parse_json_list(runtime.get("conditions") if runtime else None),
                emotional_state=runtime.get("emotional_state") if runtime else None,
                last_seen=runtime.get("last_seen") if runtime else None,
                updated_at=runtime.get("created_at") if runtime else None,
            )
            result[card["name"]] = detail
        return result

    async def get_characters_at_location(
        self, location: str, rp_folder: str, branch: str = "main"
    ) -> list[CharacterDetail]:
        """Fetch characters at a specific location, resolving through ancestry."""
        all_chars = await self.get_all_characters(rp_folder, branch)
        return [
            c for c in all_chars.values()
            if c.location and c.location.lower() == location.lower()
        ]

    async def update_character(
        self,
        name: str,
        updates: CharacterUpdate,
        rp_folder: str,
        branch: str = "main",
        exchange_id: int | None = None,
    ) -> CharacterDetail:
        """Write a new character state snapshot (CoW entry).

        Creates a full snapshot by merging updates with the current resolved state.
        Also ensures the character exists in the ledger.
        """
        now = datetime.now(UTC).isoformat()
        exchange_number = await self._resolve_exchange_number(exchange_id, rp_folder, branch)

        # 1. Find or create the character's card_id
        card = await self.db.fetch_one(
            """SELECT id, name FROM story_cards
               WHERE rp_folder = ? AND LOWER(name) = LOWER(?)
                 AND card_type IN ('character', 'npc')""",
            [rp_folder, name],
        )

        if card:
            card_id = card["id"]

            # 2. Ensure ledger entry exists
            ledger = await self.db.fetch_one(
                "SELECT * FROM character_ledger WHERE card_id = ? AND rp_folder = ? AND branch = ?",
                [card_id, rp_folder, branch],
            )
            if not ledger:
                future = await self.db.enqueue_write(
                    """INSERT OR IGNORE INTO character_ledger
                           (card_id, rp_folder, branch, status, activated_at_exchange, created_at)
                       VALUES (?, ?, ?, 'active', ?, ?)""",
                    [card_id, rp_folder, branch, exchange_number, now],
                    priority=PRIORITY_ANALYSIS,
                )
                await future
            elif ledger["status"] == "dormant":
                future = await self.db.enqueue_write(
                    """UPDATE character_ledger SET status = 'active', activated_at_exchange = ?
                       WHERE card_id = ? AND rp_folder = ? AND branch = ?""",
                    [exchange_number, card_id, rp_folder, branch],
                    priority=PRIORITY_ANALYSIS,
                )
                await future

            # 3. Resolve current state and merge
            current_runtime = None
            if self.resolver:
                current_runtime = await self.resolver.resolve_character_state(
                    card_id, rp_folder, branch
                )

            new_location = updates.location if updates.location is not None else (
                current_runtime.get("location") if current_runtime else None
            )
            new_conditions = (
                json.dumps(updates.conditions)
                if updates.conditions is not None
                else (current_runtime.get("conditions") if current_runtime else "[]")
            )
            new_emotional = updates.emotional_state if updates.emotional_state is not None else (
                current_runtime.get("emotional_state") if current_runtime else None
            )
            new_last_seen = updates.last_seen if updates.last_seen is not None else (
                current_runtime.get("last_seen") if current_runtime else None
            )

            # 4. Insert CoW entry (INSERT OR REPLACE for same exchange_number)
            future = await self.db.enqueue_write(
                """INSERT OR REPLACE INTO character_state_entries
                       (card_id, rp_folder, branch, exchange_number,
                        location, conditions, emotional_state, last_seen, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [card_id, rp_folder, branch, exchange_number,
                 new_location, new_conditions, new_emotional, new_last_seen, now],
                priority=PRIORITY_ANALYSIS,
            )
            await future
        else:
            # No story card found — cannot update character without a card
            logger.warning("No story card found for character '%s' in rp_folder '%s'", name, rp_folder)
            return CharacterDetail(name=name)

        result = await self.get_character(name, rp_folder, branch)
        return result  # type: ignore[return-value]

    # ===================================================================
    # Relationships & Trust
    # ===================================================================

    async def get_relationship(
        self, char_a: str, char_b: str, rp_folder: str, branch: str = "main"
    ) -> RelationshipDetail | None:
        """Fetch a relationship between two characters using ancestry-resolved trust."""
        if not self.resolver:
            logger.warning("get_relationship called without resolver")
            return None

        trust_data = await self.resolver.resolve_trust(char_a, char_b, rp_folder, branch)
        # Also check reverse direction
        trust_data_rev = await self.resolver.resolve_trust(char_b, char_a, rp_folder, branch)

        # Use whichever has data (or merge both)
        if trust_data["live_score"] == 0 and trust_data_rev["live_score"] != 0:
            trust_data = trust_data_rev
            char_a, char_b = char_b, char_a

        if trust_data["live_score"] == 0 and trust_data["baseline_score"] == 0:
            return None

        # Get modification history
        mods = await self.resolver.resolve_trust_full_history(
            char_a, char_b, rp_folder, branch
        )
        modifications = [
            TrustModification(
                date=m.get("date"),
                change=m.get("change") or 0,
                direction=m.get("direction") or "neutral",
                reason=m.get("reason"),
                exchange_id=m.get("exchange_id"),
                branch=m.get("branch"),
                exchange_number=m.get("exchange_number"),
            )
            for m in mods
        ]

        return RelationshipDetail(
            character_a=char_a,
            character_b=char_b,
            initial_trust_score=trust_data["baseline_score"],
            trust_modification_sum=trust_data["branch_modifications_sum"],
            live_trust_score=trust_data["live_score"],
            trust_stage=trust_data["trust_stage"],
            modifications=modifications,
        )

    async def get_all_relationships(
        self,
        rp_folder: str,
        branch: str = "main",
        character: str | None = None,
    ) -> list[RelationshipDetail]:
        """Fetch all relationships, optionally filtered by character."""
        if not self.resolver:
            logger.warning("get_all_relationships called without resolver")
            return []

        # Get all trust baselines for this branch
        if character:
            baseline_rows = await self.db.fetch_all(
                """SELECT * FROM trust_baselines
                   WHERE rp_folder = ? AND branch = ?
                     AND (LOWER(character_a) = LOWER(?) OR LOWER(character_b) = LOWER(?))""",
                [rp_folder, branch, character, character],
            )
        else:
            baseline_rows = await self.db.fetch_all(
                "SELECT * FROM trust_baselines WHERE rp_folder = ? AND branch = ?",
                [rp_folder, branch],
            )

        results = []
        seen_pairs: set[tuple[str, str]] = set()
        for br in baseline_rows:
            pair = (br["character_a"], br["character_b"])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            rel = await self.get_relationship(
                br["character_a"], br["character_b"], rp_folder, branch
            )
            if rel:
                results.append(rel)

        return results

    async def update_trust(
        self,
        char_a: str,
        char_b: str,
        change: int,
        direction: str,
        reason: str,
        rp_folder: str,
        branch: str = "main",
        exchange_id: int | None = None,
    ) -> RelationshipDetail:
        """Apply a trust change between two characters.

        Uses trust_modifications with direct columns (character_a, character_b, branch,
        exchange_number, rp_folder) for direct querying without JOIN.
        Checks session caps and score bounds.
        """
        if not self.resolver:
            raise RuntimeError("update_trust requires an AncestryResolver")

        now = datetime.now(UTC).isoformat()
        exchange_number = await self._resolve_exchange_number(exchange_id, rp_folder, branch)

        # Resolve current trust through ancestry
        trust_data = await self.resolver.resolve_trust(char_a, char_b, rp_folder, branch)
        current_live = trust_data["live_score"]

        # Check session caps (in-memory)
        cap_key = (char_a.lower(), char_b.lower(), rp_folder, branch)
        caps = self._session_trust_caps.setdefault(cap_key, {"gained": 0, "lost": 0})

        effective_change = change
        if change > 0:
            remaining_gain = self.config.session_max_gain - caps["gained"]
            if remaining_gain <= 0:
                logger.info(
                    "Session gain cap reached for %s<->%s (gained=%d, cap=%d)",
                    char_a, char_b, caps["gained"], self.config.session_max_gain,
                )
                effective_change = 0
            else:
                effective_change = min(change, remaining_gain)
        elif change < 0:
            remaining_loss = self.config.session_max_loss - caps["lost"]
            if remaining_loss >= 0:
                logger.info(
                    "Session loss cap reached for %s<->%s (lost=%d, cap=%d)",
                    char_a, char_b, caps["lost"], self.config.session_max_loss,
                )
                effective_change = 0
            else:
                effective_change = max(change, remaining_loss)

        # Clamp to score bounds
        new_live = current_live + effective_change
        if new_live > self.config.max_score:
            effective_change = self.config.max_score - current_live
        elif new_live < self.config.min_score:
            effective_change = self.config.min_score - current_live

        if effective_change == 0:
            rel = await self.get_relationship(char_a, char_b, rp_folder, branch)
            if rel:
                return rel
            return RelationshipDetail(
                character_a=char_a, character_b=char_b,
                live_trust_score=current_live, trust_stage=trust_stage(current_live),
            )

        # Update session caps
        if effective_change > 0:
            caps["gained"] += effective_change
        elif effective_change < 0:
            caps["lost"] += effective_change

        # Ensure trust baseline exists for this pair/branch
        existing_baseline = await self.db.fetch_one(
            """SELECT * FROM trust_baselines
               WHERE character_a = ? AND character_b = ? AND rp_folder = ? AND branch = ?""",
            [char_a, char_b, rp_folder, branch],
        )
        if not existing_baseline:
            future = await self.db.enqueue_write(
                """INSERT OR IGNORE INTO trust_baselines
                       (character_a, character_b, rp_folder, branch, baseline_score, created_at)
                   VALUES (?, ?, ?, ?, 0, ?)""",
                [char_a, char_b, rp_folder, branch, now],
                priority=PRIORITY_ANALYSIS,
            )
            await future

        # Insert trust modification with direct columns
        future = await self.db.enqueue_write(
            """INSERT INTO trust_modifications
                   (date, change, direction, reason, exchange_id, created_at,
                    character_a, character_b, branch, exchange_number, rp_folder)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [now[:10], effective_change, direction, reason, exchange_id, now,
             char_a, char_b, branch, exchange_number, rp_folder],
            priority=PRIORITY_ANALYSIS,
        )
        await future

        # Return updated relationship
        rel = await self.get_relationship(char_a, char_b, rp_folder, branch)
        if rel:
            return rel
        return RelationshipDetail(
            character_a=char_a, character_b=char_b,
            live_trust_score=current_live + effective_change,
            trust_stage=trust_stage(current_live + effective_change),
        )

    async def reset_session_caps(self, rp_folder: str, branch: str = "main") -> None:
        """Reset in-memory session trust caps. Called at session start."""
        keys_to_clear = [
            k for k in self._session_trust_caps
            if k[2] == rp_folder and k[3] == branch
        ]
        for k in keys_to_clear:
            del self._session_trust_caps[k]

    # ===================================================================
    # Scene Context
    # ===================================================================

    async def get_scene(
        self, rp_folder: str, branch: str = "main"
    ) -> SceneState:
        """Read the current scene context, resolved through ancestry."""
        if self.resolver:
            row = await self.resolver.resolve_scene_state(rp_folder, branch)
            if row:
                return SceneState(
                    location=row.get("location"),
                    time_of_day=row.get("time_of_day"),
                    mood=row.get("mood"),
                    in_story_timestamp=row.get("in_story_timestamp"),
                )
        return SceneState()

    async def update_scene(
        self,
        updates: SceneUpdate,
        rp_folder: str,
        branch: str = "main",
        exchange_id: int | None = None,
    ) -> SceneState:
        """Write a new scene state snapshot (CoW entry).

        Merges updates with current resolved state.
        """
        now = datetime.now(UTC).isoformat()
        exchange_number = await self._resolve_exchange_number(exchange_id, rp_folder, branch)

        # Resolve current state
        current = await self.get_scene(rp_folder, branch)

        new_location = updates.location if updates.location is not None else current.location
        new_time = updates.time_of_day if updates.time_of_day is not None else current.time_of_day
        new_mood = updates.mood if updates.mood is not None else current.mood
        new_ts = updates.in_story_timestamp if updates.in_story_timestamp is not None else current.in_story_timestamp

        # Insert CoW entry
        future = await self.db.enqueue_write(
            """INSERT OR REPLACE INTO scene_state_entries
                   (rp_folder, branch, exchange_number, location, time_of_day,
                    mood, in_story_timestamp, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [rp_folder, branch, exchange_number, new_location, new_time,
             new_mood, new_ts, now],
            priority=PRIORITY_ANALYSIS,
        )
        await future

        return SceneState(
            location=new_location,
            time_of_day=new_time,
            mood=new_mood,
            in_story_timestamp=new_ts,
        )

    # ===================================================================
    # Events
    # ===================================================================

    async def get_events(
        self,
        rp_folder: str,
        branch: str = "main",
        limit: int = 15,
        significance: str | None = None,
        character: str | None = None,
    ) -> list[EventDetail]:
        """Fetch events with optional filters, ordered by created_at DESC."""
        sql = "SELECT * FROM events WHERE rp_folder = ? AND branch = ?"
        params: list = [rp_folder, branch]

        if significance:
            sql += " AND significance = ?"
            params.append(significance)

        if character:
            sql += " AND EXISTS (SELECT 1 FROM json_each(characters) WHERE LOWER(json_each.value) = LOWER(?))"
            params.append(character)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self.db.fetch_all(sql, params)
        return [self._row_to_event(row) for row in rows]

    async def add_event(
        self,
        event: str,
        characters: list[str],
        significance: str,
        rp_folder: str,
        branch: str = "main",
        exchange_id: int | None = None,
        in_story_timestamp: str | None = None,
    ) -> EventDetail:
        """Insert a new event and return it."""
        now = datetime.now(UTC).isoformat()
        chars_json = json.dumps(characters)

        future = await self.db.enqueue_write(
            """INSERT INTO events
                   (rp_folder, branch, in_story_timestamp, event, characters,
                    significance, exchange_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [rp_folder, branch, in_story_timestamp, event, chars_json, significance, exchange_id, now],
            priority=PRIORITY_ANALYSIS,
        )
        row_id = await future

        row = await self.db.fetch_one("SELECT * FROM events WHERE id = ?", [row_id])
        return self._row_to_event(row)

    def _row_to_event(self, row: dict) -> EventDetail:
        """Convert a database row to an EventDetail model."""
        return EventDetail(
            id=row["id"],
            in_story_timestamp=row.get("in_story_timestamp"),
            event=row["event"],
            characters=safe_parse_json_list(row.get("characters")),
            significance=row.get("significance"),
            exchange_id=row.get("exchange_id"),
            created_at=row.get("created_at"),
        )

    # ===================================================================
    # Full State Snapshot
    # ===================================================================

    async def get_full_state(
        self, rp_folder: str, branch: str = "main"
    ) -> StateSnapshot:
        """Assemble the full state snapshot for an RP/branch."""
        characters = await self.get_all_characters(rp_folder, branch)
        relationships = await self.get_all_relationships(rp_folder, branch)
        scene = await self.get_scene(rp_folder, branch)
        events = await self.get_events(rp_folder, branch)

        session_row = await self.db.fetch_one(
            """SELECT * FROM sessions
               WHERE rp_folder = ? AND branch = ? AND ended_at IS NULL
               ORDER BY started_at DESC LIMIT 1""",
            [rp_folder, branch],
        )
        session = dict(session_row) if session_row else None

        return StateSnapshot(
            characters=characters,
            relationships=relationships,
            scene=scene,
            events=events,
            session=session,
            branch=branch,
        )
