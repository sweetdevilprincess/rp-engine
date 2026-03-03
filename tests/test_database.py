"""Tests for database initialization, schema, and write queue."""

import pytest


EXPECTED_TABLES = [
    "sessions",
    "exchanges",
    "characters",
    "relationships",
    "trust_modifications",
    "plot_threads",
    "thread_counters",
    "events",
    "scene_context",
    "story_cards",
    "entity_connections",
    "entity_aliases",
    "entity_keywords",
    "vectors",
    "vectors_fts",
    "indexed_files",
    "branches",
    "card_gaps",
    "config",
    "context_sent",
    "situational_triggers",
]


async def test_schema_creates_all_tables(db):
    """Verify all 21 tables exist in sqlite_master."""
    rows = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE '_migrations%'"
    )
    table_names = {row["name"] for row in rows}
    for expected in EXPECTED_TABLES:
        assert expected in table_names, f"Missing table: {expected}"


async def test_fts5_virtual_table_exists(db):
    """vectors_fts should be in sqlite_master."""
    row = await db.fetch_one(
        "SELECT name FROM sqlite_master WHERE name = 'vectors_fts'"
    )
    assert row is not None, "vectors_fts virtual table not found"


async def test_wal_mode_enabled(db):
    """PRAGMA journal_mode should return 'wal' (or 'memory' for in-memory)."""
    mode = await db.fetch_val("PRAGMA journal_mode")
    # In-memory databases use 'memory' journal mode
    assert mode in ("wal", "memory")


async def test_migration_tracking(db):
    """_migrations table should have at least 1 entry."""
    row = await db.fetch_one(
        "SELECT * FROM _migrations WHERE name = '001_initial.sql'"
    )
    assert row is not None, "Migration 001_initial.sql not tracked"


async def test_write_queue_basic(db):
    """INSERT via enqueue_write, then verify with fetch_one."""
    future = await db.enqueue_write(
        "INSERT INTO config (key, value) VALUES (?, ?)",
        ["test_key", '"test_value"'],
    )
    await future
    row = await db.fetch_one("SELECT * FROM config WHERE key = ?", ["test_key"])
    assert row is not None
    assert row["value"] == '"test_value"'


async def test_write_queue_returns_lastrowid(db):
    """INSERT into events should return a positive lastrowid."""
    # Need a session first for the foreign key
    await db._write_connection.execute(
        "INSERT INTO sessions (id, rp_folder, started_at) VALUES (?, ?, datetime('now'))",
        ["test-session", "TestRP"],
    )
    await db._write_connection.commit()

    future = await db.enqueue_write(
        "INSERT INTO events (rp_folder, branch, event, created_at) VALUES (?, ?, ?, datetime('now'))",
        ["TestRP", "main", "Test event happened"],
    )
    result = await future
    assert isinstance(result, int)
    assert result > 0


async def test_foreign_keys_enabled(db):
    """PRAGMA foreign_keys should return 1."""
    val = await db.fetch_val("PRAGMA foreign_keys")
    assert val == 1
