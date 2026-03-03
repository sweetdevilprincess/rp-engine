"""Data migration: populate new CoW tables from old tables.

Run as a standalone script:
    python -m rp_engine.migrations.004_data_migration [--db-path path/to/rp-engine.db]

Migrates:
1. characters -> character_ledger + character_state_entries
2. relationships -> trust_baselines
3. trust_modifications -> backfill new columns (character_a, character_b, branch, exchange_number, rp_folder)
4. scene_context -> scene_state_entries

This is idempotent — running it multiple times won't create duplicates (uses INSERT OR IGNORE).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


async def migrate(db_path: str = "data/rp-engine.db") -> dict:
    """Run the full data migration. Returns counts of migrated records."""
    # Import here to avoid circular imports at module level
    from rp_engine.database import Database

    db = Database(db_path)
    await db.initialize()

    counts = {
        "character_ledger": 0,
        "character_state_entries": 0,
        "trust_baselines": 0,
        "trust_modifications_backfilled": 0,
        "scene_state_entries": 0,
    }

    try:
        now = datetime.now(timezone.utc).isoformat()

        # 1. characters -> character_ledger + character_state_entries
        logger.info("Migrating characters...")
        char_rows = await db.fetch_all("SELECT * FROM characters")
        for char in char_rows:
            rp_folder = char["rp_folder"]
            branch = char["branch"]
            name = char["name"]

            # Find matching story card
            card = await db.fetch_one(
                """SELECT id FROM story_cards
                   WHERE rp_folder = ? AND LOWER(name) = LOWER(?)
                     AND card_type IN ('character', 'npc')""",
                [rp_folder, name],
            )
            card_id = card["id"] if card else f"legacy:{rp_folder}:{name.lower()}"

            # Insert into character_ledger
            future = await db.enqueue_write(
                """INSERT OR IGNORE INTO character_ledger
                       (card_id, rp_folder, branch, status, activated_at_exchange, created_at)
                   VALUES (?, ?, ?, 'active', 1, ?)""",
                [card_id, rp_folder, branch, now],
            )
            await future
            counts["character_ledger"] += 1

            # Insert into character_state_entries (exchange 0 = initial state)
            future = await db.enqueue_write(
                """INSERT OR IGNORE INTO character_state_entries
                       (card_id, rp_folder, branch, exchange_number,
                        location, conditions, emotional_state, last_seen, created_at)
                   VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)""",
                [
                    card_id, rp_folder, branch,
                    char.get("location"),
                    char.get("conditions"),
                    char.get("emotional_state"),
                    char.get("last_seen"),
                    now,
                ],
            )
            await future
            counts["character_state_entries"] += 1

        # 2. relationships -> trust_baselines
        logger.info("Migrating relationships to trust_baselines...")
        rel_rows = await db.fetch_all("SELECT * FROM relationships")
        for rel in rel_rows:
            initial = rel.get("initial_trust_score") or 0
            future = await db.enqueue_write(
                """INSERT OR IGNORE INTO trust_baselines
                       (character_a, character_b, rp_folder, branch,
                        baseline_score, baseline_stage, source_branch, source_exchange, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, NULL, 0, ?)""",
                [
                    rel["character_a"], rel["character_b"],
                    rel["rp_folder"], rel["branch"],
                    initial,
                    rel.get("trust_stage"),
                    now,
                ],
            )
            await future
            counts["trust_baselines"] += 1

        # 3. trust_modifications -> backfill new columns
        logger.info("Backfilling trust_modifications with new columns...")
        mod_rows = await db.fetch_all(
            """SELECT tm.id, tm.relationship_id, tm.exchange_id,
                      r.character_a, r.character_b, r.rp_folder, r.branch
               FROM trust_modifications tm
               LEFT JOIN relationships r ON tm.relationship_id = r.id
               WHERE tm.character_a IS NULL AND r.id IS NOT NULL"""
        )
        for mod in mod_rows:
            # Resolve exchange_number from exchange_id
            exchange_number = None
            if mod.get("exchange_id"):
                ex_row = await db.fetch_one(
                    "SELECT exchange_number FROM exchanges WHERE id = ?",
                    [mod["exchange_id"]],
                )
                if ex_row:
                    exchange_number = ex_row["exchange_number"]

            future = await db.enqueue_write(
                """UPDATE trust_modifications
                   SET character_a = ?, character_b = ?, branch = ?,
                       exchange_number = ?, rp_folder = ?
                   WHERE id = ?""",
                [
                    mod["character_a"], mod["character_b"],
                    mod["branch"], exchange_number, mod["rp_folder"],
                    mod["id"],
                ],
            )
            await future
            counts["trust_modifications_backfilled"] += 1

        # 4. scene_context -> scene_state_entries
        logger.info("Migrating scene_context to scene_state_entries...")
        scene_rows = await db.fetch_all("SELECT * FROM scene_context")
        for scene in scene_rows:
            future = await db.enqueue_write(
                """INSERT OR IGNORE INTO scene_state_entries
                       (rp_folder, branch, exchange_number,
                        location, time_of_day, mood, in_story_timestamp, created_at)
                   VALUES (?, ?, 0, ?, ?, ?, ?, ?)""",
                [
                    scene["rp_folder"], scene["branch"],
                    scene.get("location"), scene.get("time_of_day"),
                    scene.get("mood"), scene.get("in_story_timestamp"),
                    now,
                ],
            )
            await future
            counts["scene_state_entries"] += 1

        logger.info("Migration complete: %s", counts)
    finally:
        await db.close()

    return counts


def main():
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    db_path = "data/rp-engine.db"
    if len(sys.argv) > 2 and sys.argv[1] == "--db-path":
        db_path = sys.argv[2]

    logger.info("Starting data migration from: %s", db_path)
    counts = asyncio.run(migrate(db_path))
    print(f"\nMigration complete:")
    for table, count in counts.items():
        print(f"  {table}: {count} records")


if __name__ == "__main__":
    main()
