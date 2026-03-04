"""Tests for the card indexer service."""

from __future__ import annotations

from pathlib import Path

import pytest

from rp_engine.services.card_indexer import CardIndexer


class TestFullIndex:
    async def test_indexes_all_entities(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        result = await indexer.full_index("TestRP")
        assert result["entities"] == 7  # character, memory, secret, location, plot_thread, knowledge, plot_arc

    async def test_indexes_connections(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        result = await indexer.full_index("TestRP")
        assert result["connections"] > 0

    async def test_indexes_aliases(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        result = await indexer.full_index("TestRP")
        assert result["aliases"] > 0

    async def test_indexes_keywords(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        result = await indexer.full_index("TestRP")
        assert result["keywords"] > 0

    async def test_entity_ids_have_rp_prefix(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        row = await db.fetch_one("SELECT id FROM story_cards WHERE name = 'Dante Moretti'")
        assert row is not None
        assert row["id"].startswith("TestRP:")

    async def test_forward_slash_paths(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        rows = await db.fetch_all("SELECT file_path FROM story_cards")
        for row in rows:
            assert "\\" not in row["file_path"]

    async def test_character_type_detection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        row = await db.fetch_one("SELECT card_type FROM story_cards WHERE name = 'Dante Moretti'")
        assert row["card_type"] == "character"

    async def test_memory_type_detection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        row = await db.fetch_one(
            "SELECT card_type FROM story_cards WHERE name = 'Lilith Wakes to Find Dante Still Holding Her'"
        )
        assert row["card_type"] == "memory"

    async def test_secret_type_detection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        row = await db.fetch_one(
            "SELECT card_type FROM story_cards WHERE name = 'Lilith is Terrified Dante Will Abandon Her'"
        )
        assert row["card_type"] == "secret"

    async def test_location_type_detection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        row = await db.fetch_one(
            "SELECT card_type FROM story_cards WHERE name = ?", ["Dante's Penthouse"]
        )
        assert row["card_type"] == "location"

    async def test_plot_thread_type_detection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        row = await db.fetch_one(
            "SELECT card_type FROM story_cards WHERE name = 'Dante-Lilith Core Tension'"
        )
        assert row["card_type"] == "plot_thread"

    async def test_reindex_clears_old_data(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        first_count = await db.fetch_val("SELECT COUNT(*) FROM story_cards WHERE rp_folder = 'TestRP'")

        # Reindex should produce same count (idempotent)
        await indexer.full_index("TestRP")
        second_count = await db.fetch_val("SELECT COUNT(*) FROM story_cards WHERE rp_folder = 'TestRP'")
        assert first_count == second_count

    async def test_no_story_cards_dir(self, db, tmp_path):
        indexer = CardIndexer(db, tmp_path)
        result = await indexer.full_index("NonExistent")
        assert result["entities"] == 0


class TestConnections:
    async def test_character_has_memory_connection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conn = await db.fetch_one(
            "SELECT * FROM entity_connections WHERE from_entity = ? AND connection_type = 'has_memory'",
            ["TestRP:dante moretti"],
        )
        assert conn is not None

    async def test_character_has_relationship_connection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conn = await db.fetch_one(
            "SELECT * FROM entity_connections WHERE from_entity = ? AND connection_type = 'has_relationship'",
            ["TestRP:dante moretti"],
        )
        assert conn is not None
        assert conn["role"] == "love_interest"

    async def test_memory_belongs_to_connection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conn = await db.fetch_one(
            """SELECT * FROM entity_connections
               WHERE from_entity LIKE 'TestRP:lilith wakes%'
               AND connection_type = 'belongs_to'""",
        )
        assert conn is not None

    async def test_location_occupant_connection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conns = await db.fetch_all(
            "SELECT * FROM entity_connections WHERE from_entity = ? AND connection_type = 'occupied_by'",
            ["TestRP:dante's penthouse"],
        )
        assert len(conns) >= 2  # Dante and Lilith

    async def test_location_connected_location(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conn = await db.fetch_one(
            "SELECT * FROM entity_connections WHERE from_entity = ? AND connection_type = 'connects_to'",
            ["TestRP:dante's penthouse"],
        )
        assert conn is not None

    async def test_plot_thread_related_characters(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conns = await db.fetch_all(
            "SELECT * FROM entity_connections WHERE from_entity = ? AND connection_type = 'involves_character'",
            ["TestRP:dante-lilith core tension"],
        )
        assert len(conns) >= 2


class TestAliases:
    async def test_character_aliases_indexed(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        alias = await db.fetch_one(
            "SELECT * FROM entity_aliases WHERE alias = 'beasty'"
        )
        assert alias is not None
        assert alias["entity_id"] == "TestRP:dante moretti"

    async def test_file_stem_alias(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        alias = await db.fetch_one(
            "SELECT * FROM entity_aliases WHERE alias = 'dante moretti'"
        )
        assert alias is not None


class TestIncrementalIndex:
    async def test_index_new_file(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")

        # Add a new file
        new_file = sample_card_dir / "TestRP" / "Story Cards" / "Characters" / "New Character.md"
        new_file.write_text("---\ntype: character\nname: New Character\n---\nBody.", encoding="utf-8")

        result = await indexer.index_file("TestRP", new_file)
        assert result is True

        row = await db.fetch_one("SELECT * FROM story_cards WHERE name = 'New Character'")
        assert row is not None

    async def test_unchanged_file_skipped(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")

        # Re-index same file — should return False (unchanged)
        file_path = sample_card_dir / "TestRP" / "Story Cards" / "Characters" / "Dante Moretti.md"
        result = await indexer.index_file("TestRP", file_path)
        assert result is False


class TestRemoveFile:
    async def test_removes_entity(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")

        file_path = sample_card_dir / "TestRP" / "Story Cards" / "Characters" / "Dante Moretti.md"
        result = await indexer.remove_file("TestRP", file_path)
        assert result is True

        row = await db.fetch_one("SELECT * FROM story_cards WHERE name = 'Dante Moretti'")
        assert row is None


class TestPlotArcIndexing:
    async def test_plot_arc_type_detection(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        row = await db.fetch_one(
            "SELECT card_type FROM story_cards WHERE name = ?",
            ["Lilith's Infiltration"],
        )
        assert row is not None
        assert row["card_type"] == "plot_arc"

    async def test_plot_type_normalized_to_plot_arc(self, db, tmp_path):
        """Cards with type: plot (old format) should normalize to plot_arc."""
        rp = tmp_path / "TestRP" / "Story Cards" / "Plot Arcs"
        rp.mkdir(parents=True)
        (rp / "Test Arc.md").write_text(
            '---\ntype: plot\nname: Test Arc\nrp: Mafia\n---\nTest.',
            encoding="utf-8",
        )
        indexer = CardIndexer(db, tmp_path)
        await indexer.full_index("TestRP")
        row = await db.fetch_one(
            "SELECT card_type FROM story_cards WHERE name = 'Test Arc'"
        )
        assert row is not None
        assert row["card_type"] == "plot_arc"

    async def test_plot_arc_key_characters_connections(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conns = await db.fetch_all(
            "SELECT * FROM entity_connections "
            "WHERE from_entity = ? AND connection_type = 'involves_character'",
            ["TestRP:lilith's infiltration"],
        )
        assert len(conns) >= 2
        # Verify roles are preserved
        roles = {c["role"] for c in conns if c["role"]}
        assert "protagonist" in roles
        assert "catalyst" in roles

    async def test_plot_arc_related_memories_connections(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conns = await db.fetch_all(
            "SELECT * FROM entity_connections "
            "WHERE from_entity = ? AND connection_type = 'involves_memory'",
            ["TestRP:lilith's infiltration"],
        )
        assert len(conns) >= 1

    async def test_plot_arc_related_threads_connections(self, db, sample_card_dir):
        indexer = CardIndexer(db, sample_card_dir)
        await indexer.full_index("TestRP")
        conns = await db.fetch_all(
            "SELECT * FROM entity_connections "
            "WHERE from_entity = ? AND connection_type = 'related_thread'",
            ["TestRP:lilith's infiltration"],
        )
        assert len(conns) >= 1


class TestGetAllRpFolders:
    def test_discovers_rp_folders(self, sample_card_dir):
        indexer = CardIndexer(None, sample_card_dir)
        folders = indexer.get_all_rp_folders()
        assert "TestRP" in folders

    def test_ignores_non_rp_dirs(self, tmp_path):
        (tmp_path / "NotAnRP").mkdir()
        indexer = CardIndexer(None, tmp_path)
        folders = indexer.get_all_rp_folders()
        assert "NotAnRP" not in folders
