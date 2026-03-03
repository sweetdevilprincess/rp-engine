"""Centralized state management using copy-on-write branching.

Characters, relationships, scenes, and events are resolved through the branch
ancestry graph. State is stored as CoW snapshots (character_state_entries,
scene_state_entries) and trust modifications with direct branch/exchange columns.

Cards are read-only — all runtime state lives in the DB, scoped by branch.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from rp_engine.config import TrustConfig
from rp_engine.database import PRIORITY_ANALYSIS, PRIORITY_EXCHANGE, Database
from rp_engine.models.context import SceneState
from rp_engine.models.state import (
    CharacterDetail,
    CharacterUpdate,
    EventCreate,
    EventDetail,
    RelationshipDetail,
    SceneUpdate,
    StateSnapshot,
    TrustModification,
)
from rp_engine.services.ancestry_resolver import AncestryResolver
from rp_engine.services.context_engine import trust_stage

logger = logging.getLogger(__name__)


def _parse_json_list(raw: str | list | None) -> list[str]:
    """Safely parse a JSON string into a list, or return as-is if already a list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


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
            # Fall back to old characters table during migration period
            # Try current branch first
            row = await self.db.fetch_one(
                """SELECT * FROM characters
                   WHERE rp_folder = ? AND branch = ? AND LOWER(name) = LOWER(?)""",
                [rp_folder, branch, name],
            )
            if row:
                return self._row_to_character(row)

            # Walk ancestry to find character on parent branches
            if self.resolver:
                chain = await self.resolver.get_ancestry_chain(rp_folder, branch)
                for chain_branch, _ in chain[1:]:  # skip current branch (already checked)
                    row = await self.db.fetch_one(
                        """SELECT * FROM characters
                           WHERE rp_folder = ? AND branch = ? AND LOWER(name) = LOWER(?)""",
                        [rp_folder, chain_branch, name],
                    )
                    if row:
                        return self._row_to_character(row)
            return None

        # 2. Resolve runtime state through ancestry
        runtime = None
        if self.resolver:
            runtime = await self.resolver.resolve_character_state(
                card["id"], rp_folder, branch
            )

        # 3. Build CharacterDetail from card + runtime state
        fm = {}
        if card.get("frontmatter"):
            try:
                fm = json.loads(card["frontmatter"])
            except (json.JSONDecodeError, TypeError):
                pass

        return CharacterDetail(
            name=card["name"],
            card_path=card.get("file_path"),
            is_player_character=bool(fm.get("is_player_character", False)),
            importance=card.get("importance") or fm.get("importance"),
            primary_archetype=fm.get("primary_archetype"),
            secondary_archetype=fm.get("secondary_archetype"),
            behavioral_modifiers=_parse_json_list(fm.get("behavioral_modifiers")),
            location=runtime.get("location") if runtime else None,
            conditions=_parse_json_list(runtime.get("conditions") if runtime else None),
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

        if ledger_rows:
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

                fm = {}
                if card.get("frontmatter"):
                    try:
                        fm = json.loads(card["frontmatter"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                detail = CharacterDetail(
                    name=card["name"],
                    card_path=card.get("file_path"),
                    is_player_character=bool(fm.get("is_player_character", False)),
                    importance=card.get("importance") or fm.get("importance"),
                    primary_archetype=fm.get("primary_archetype"),
                    secondary_archetype=fm.get("secondary_archetype"),
                    behavioral_modifiers=_parse_json_list(fm.get("behavioral_modifiers")),
                    location=runtime.get("location") if runtime else None,
                    conditions=_parse_json_list(runtime.get("conditions") if runtime else None),
                    emotional_state=runtime.get("emotional_state") if runtime else None,
                    last_seen=runtime.get("last_seen") if runtime else None,
                    updated_at=runtime.get("created_at") if runtime else None,
                )
                result[card["name"]] = detail
            return result

        # Fall back to old characters table during migration period
        rows = await self.db.fetch_all(
            "SELECT * FROM characters WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
        return {row["name"]: self._row_to_character(row) for row in rows}

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
        now = datetime.now(timezone.utc).isoformat()
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
            # No story card — fall back to old characters table for compatibility
            char_id = f"{rp_folder}:{branch}:{name.lower()}"
            existing = await self.db.fetch_one(
                "SELECT * FROM characters WHERE id = ?", [char_id]
            )

            if existing:
                new_location = updates.location if updates.location is not None else existing.get("location")
                new_conditions = (
                    json.dumps(updates.conditions)
                    if updates.conditions is not None
                    else existing.get("conditions")
                )
                new_emotional = (
                    updates.emotional_state
                    if updates.emotional_state is not None
                    else existing.get("emotional_state")
                )
                new_last_seen = (
                    updates.last_seen if updates.last_seen is not None else existing.get("last_seen")
                )

                future = await self.db.enqueue_write(
                    """UPDATE characters
                       SET location = ?, conditions = ?, emotional_state = ?,
                           last_seen = ?, updated_at = ?
                       WHERE id = ?""",
                    [new_location, new_conditions, new_emotional, new_last_seen, now, char_id],
                    priority=PRIORITY_ANALYSIS,
                )
                await future
            else:
                conditions_json = json.dumps(updates.conditions) if updates.conditions else "[]"
                future = await self.db.enqueue_write(
                    """INSERT INTO characters (id, rp_folder, branch, name, location,
                           conditions, emotional_state, last_seen, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [char_id, rp_folder, branch, name, updates.location,
                     conditions_json, updates.emotional_state, updates.last_seen, now],
                    priority=PRIORITY_ANALYSIS,
                )
                await future

        result = await self.get_character(name, rp_folder, branch)
        return result  # type: ignore[return-value]

    def _row_to_character(self, row: dict) -> CharacterDetail:
        """Convert a legacy characters table row to a CharacterDetail model."""
        return CharacterDetail(
            name=row["name"],
            card_path=row.get("card_path"),
            is_player_character=bool(row.get("is_player_character")),
            importance=row.get("importance"),
            primary_archetype=row.get("primary_archetype"),
            secondary_archetype=row.get("secondary_archetype"),
            behavioral_modifiers=_parse_json_list(row.get("behavioral_modifiers")),
            location=row.get("location"),
            conditions=_parse_json_list(row.get("conditions")),
            emotional_state=row.get("emotional_state"),
            last_seen=row.get("last_seen"),
            updated_at=row.get("updated_at"),
        )

    # ===================================================================
    # Relationships & Trust
    # ===================================================================

    async def get_relationship(
        self, char_a: str, char_b: str, rp_folder: str, branch: str = "main"
    ) -> RelationshipDetail | None:
        """Fetch a relationship between two characters using ancestry-resolved trust."""
        if self.resolver:
            trust_data = await self.resolver.resolve_trust(char_a, char_b, rp_folder, branch)
            # Also check reverse direction
            trust_data_rev = await self.resolver.resolve_trust(char_b, char_a, rp_folder, branch)

            # Use whichever has data (or merge both)
            if trust_data["live_score"] == 0 and trust_data_rev["live_score"] != 0:
                trust_data = trust_data_rev
                char_a, char_b = char_b, char_a

            if trust_data["live_score"] == 0 and trust_data["baseline_score"] == 0:
                # Check old relationships table as fallback
                row = await self.db.fetch_one(
                    """SELECT * FROM relationships
                       WHERE rp_folder = ? AND branch = ?
                         AND ((LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?))
                           OR (LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?)))""",
                    [rp_folder, branch, char_a, char_b, char_b, char_a],
                )
                if row:
                    return await self._row_to_relationship(row)
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

        # Fallback: old relationships table
        row = await self.db.fetch_one(
            """SELECT * FROM relationships
               WHERE rp_folder = ? AND branch = ?
                 AND ((LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?))
                   OR (LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?)))""",
            [rp_folder, branch, char_a, char_b, char_b, char_a],
        )
        if not row:
            return None
        return await self._row_to_relationship(row)

    async def get_all_relationships(
        self,
        rp_folder: str,
        branch: str = "main",
        character: str | None = None,
    ) -> list[RelationshipDetail]:
        """Fetch all relationships, optionally filtered by character."""
        if self.resolver:
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

            # Also check old relationships table for any not yet migrated
            if not results:
                return await self._get_all_relationships_legacy(rp_folder, branch, character)
            return results

        return await self._get_all_relationships_legacy(rp_folder, branch, character)

    async def _get_all_relationships_legacy(
        self, rp_folder: str, branch: str, character: str | None
    ) -> list[RelationshipDetail]:
        """Legacy: fetch from old relationships table."""
        if character:
            rows = await self.db.fetch_all(
                """SELECT * FROM relationships
                   WHERE rp_folder = ? AND branch = ?
                     AND (LOWER(character_a) = LOWER(?) OR LOWER(character_b) = LOWER(?))""",
                [rp_folder, branch, character, character],
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT * FROM relationships WHERE rp_folder = ? AND branch = ?",
                [rp_folder, branch],
            )
        return [await self._row_to_relationship(row) for row in rows]

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

        Uses the new trust_modifications columns (character_a, character_b, branch,
        exchange_number, rp_folder) for direct querying without JOIN.
        Checks session caps and score bounds.
        """
        now = datetime.now(timezone.utc).isoformat()
        exchange_number = await self._resolve_exchange_number(exchange_id, rp_folder, branch)

        # Resolve current trust
        if self.resolver:
            trust_data = await self.resolver.resolve_trust(char_a, char_b, rp_folder, branch)
            current_live = trust_data["live_score"]
        else:
            # Legacy fallback
            rel_row = await self.db.fetch_one(
                """SELECT * FROM relationships
                   WHERE rp_folder = ? AND branch = ?
                     AND ((LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?))
                       OR (LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?)))""",
                [rp_folder, branch, char_a, char_b, char_b, char_a],
            )
            if rel_row:
                current_live = (rel_row.get("initial_trust_score") or 0) + (rel_row.get("trust_modification_sum") or 0)
            else:
                current_live = 0

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

        # Update legacy relationships table for backward compat during migration
        # (also returns the relationship_id for the trust_modification)
        rel_id = await self._update_legacy_relationship(
            char_a, char_b, effective_change, rp_folder, branch, now, exchange_id
        )

        # Insert trust modification with BOTH old relationship_id AND new direct columns
        future = await self.db.enqueue_write(
            """INSERT INTO trust_modifications
                   (relationship_id, date, change, direction, reason, exchange_id, created_at,
                    character_a, character_b, branch, exchange_number, rp_folder)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [rel_id, now[:10], effective_change, direction, reason, exchange_id, now,
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

    async def _update_legacy_relationship(
        self, char_a: str, char_b: str, change: int,
        rp_folder: str, branch: str, now: str, exchange_id: int | None,
    ) -> int | None:
        """Update old relationships table for backward compat. Returns relationship_id."""
        rel_row = await self.db.fetch_one(
            """SELECT * FROM relationships
               WHERE rp_folder = ? AND branch = ?
                 AND ((LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?))
                   OR (LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?)))""",
            [rp_folder, branch, char_a, char_b, char_b, char_a],
        )

        if not rel_row:
            # Create legacy relationship
            future = await self.db.enqueue_write(
                """INSERT INTO relationships
                       (rp_folder, branch, character_a, character_b,
                        initial_trust_score, trust_modification_sum,
                        session_trust_gained, session_trust_lost, updated_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                [rp_folder, branch, char_a, char_b,
                 change, max(change, 0), min(change, 0), now],
                priority=PRIORITY_ANALYSIS,
            )
            rel_id = await future

            # Re-fetch to get the auto-generated ID
            new_rel = await self.db.fetch_one(
                """SELECT id FROM relationships
                   WHERE rp_folder = ? AND branch = ?
                     AND LOWER(character_a) = LOWER(?) AND LOWER(character_b) = LOWER(?)""",
                [rp_folder, branch, char_a, char_b],
            )
            return new_rel["id"] if new_rel else None
        else:
            new_mod_sum = (rel_row.get("trust_modification_sum") or 0) + change
            initial = rel_row.get("initial_trust_score") or 0
            new_stage = trust_stage(initial + new_mod_sum)
            new_gained = (rel_row.get("session_trust_gained") or 0) + (change if change > 0 else 0)
            new_lost = (rel_row.get("session_trust_lost") or 0) + (change if change < 0 else 0)

            future = await self.db.enqueue_write(
                """UPDATE relationships
                   SET trust_modification_sum = ?, trust_stage = ?,
                       session_trust_gained = ?, session_trust_lost = ?, updated_at = ?
                   WHERE id = ?""",
                [new_mod_sum, new_stage, new_gained, new_lost, now, rel_row["id"]],
                priority=PRIORITY_ANALYSIS,
            )
            await future
            return rel_row["id"]

    async def reset_session_caps(self, rp_folder: str, branch: str = "main") -> None:
        """Reset in-memory session trust caps. Called at session start."""
        keys_to_clear = [
            k for k in self._session_trust_caps
            if k[2] == rp_folder and k[3] == branch
        ]
        for k in keys_to_clear:
            del self._session_trust_caps[k]

        # Also reset legacy table caps
        future = await self.db.enqueue_write(
            """UPDATE relationships
               SET session_trust_gained = 0, session_trust_lost = 0
               WHERE rp_folder = ? AND branch = ?""",
            [rp_folder, branch],
            priority=PRIORITY_ANALYSIS,
        )
        await future

    async def _row_to_relationship(self, row: dict) -> RelationshipDetail:
        """Convert a legacy relationship row to a RelationshipDetail."""
        initial = row.get("initial_trust_score") or 0
        mod_sum = row.get("trust_modification_sum") or 0
        live = initial + mod_sum

        mod_rows = await self.db.fetch_all(
            """SELECT date, change, direction, reason, exchange_id
               FROM trust_modifications
               WHERE relationship_id = ?
               ORDER BY created_at DESC""",
            [row["id"]],
        )
        modifications = [
            TrustModification(
                date=m.get("date"),
                change=m.get("change") or 0,
                direction=m.get("direction") or "neutral",
                reason=m.get("reason"),
                exchange_id=m.get("exchange_id"),
            )
            for m in mod_rows
        ]

        return RelationshipDetail(
            character_a=row["character_a"],
            character_b=row["character_b"],
            initial_trust_score=initial,
            trust_modification_sum=mod_sum,
            live_trust_score=live,
            trust_stage=trust_stage(live),
            dynamic=row.get("dynamic"),
            modifications=modifications,
        )

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

        # Fallback: old scene_context table
        row = await self.db.fetch_one(
            "SELECT location, time_of_day, mood, in_story_timestamp FROM scene_context WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
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
        now = datetime.now(timezone.utc).isoformat()
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

        # Also update legacy scene_context for backward compat
        existing = await self.db.fetch_one(
            "SELECT * FROM scene_context WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
        if existing:
            future = await self.db.enqueue_write(
                """UPDATE scene_context
                   SET location = ?, time_of_day = ?, mood = ?,
                       in_story_timestamp = ?, updated_at = ?
                   WHERE rp_folder = ? AND branch = ?""",
                [new_location, new_time, new_mood, new_ts, now, rp_folder, branch],
                priority=PRIORITY_ANALYSIS,
            )
            await future
        else:
            future = await self.db.enqueue_write(
                """INSERT INTO scene_context
                       (rp_folder, branch, location, time_of_day, mood, in_story_timestamp, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [rp_folder, branch, new_location, new_time, new_mood, new_ts, now],
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
    # Rewind Support (deprecated — kept as no-ops for backward compat)
    # ===================================================================

    VALID_CHAR_FIELDS = {"location", "conditions", "emotional_state", "last_seen"}
    VALID_SCENE_FIELDS = {"location", "time_of_day", "mood", "in_story_timestamp"}

    async def revert_exchange_state(
        self, exchange_id: int, rp_folder: str, branch: str
    ) -> None:
        """Deprecated: Rewind now creates a branch instead of reverting.

        Kept as a no-op for backward compatibility during migration.
        Legacy callers (exchanges router) will be updated in Phase 4.
        """
        logger.debug(
            "revert_exchange_state called (no-op in CoW system): exchange_id=%d", exchange_id
        )

    async def recalculate_trust_aggregates(
        self, rp_folder: str, branch: str
    ) -> None:
        """Deprecated: Trust is always computed from baseline + sum in CoW system.

        Kept as a no-op for backward compatibility during migration.
        """
        logger.debug(
            "recalculate_trust_aggregates called (no-op in CoW system): %s/%s", rp_folder, branch
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
        now = datetime.now(timezone.utc).isoformat()
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
            characters=_parse_json_list(row.get("characters")),
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
