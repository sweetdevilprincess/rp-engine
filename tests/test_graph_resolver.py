"""Tests for GraphResolver service."""

from __future__ import annotations

import json

import pytest

from rp_engine.services.graph_resolver import GraphResolver


@pytest.fixture
def resolver(card_indexer, db):
    """GraphResolver backed by indexed test data."""
    return GraphResolver(db)


class TestResolveEntity:
    @pytest.mark.asyncio
    async def test_direct_id_match(self, resolver):
        eid = await resolver.resolve_entity("Dante Moretti", "TestRP")
        assert eid == "TestRP:dante moretti"

    @pytest.mark.asyncio
    async def test_alias_match(self, resolver):
        eid = await resolver.resolve_entity("Beasty", "TestRP")
        assert eid == "TestRP:dante moretti"

    @pytest.mark.asyncio
    async def test_parenthetical_stripping(self, resolver):
        # "Dante Moretti (boss)" should strip to "Dante Moretti"
        eid = await resolver.resolve_entity("Dante Moretti (boss)", "TestRP")
        assert eid == "TestRP:dante moretti"

    @pytest.mark.asyncio
    async def test_underscore_to_space(self, resolver):
        eid = await resolver.resolve_entity(
            "memory_lilith_wakes_with_dante", "TestRP"
        )
        assert eid is not None

    @pytest.mark.asyncio
    async def test_md_extension_stripping(self, resolver):
        eid = await resolver.resolve_entity("Dante Moretti.md", "TestRP")
        assert eid == "TestRP:dante moretti"

    @pytest.mark.asyncio
    async def test_nonexistent_returns_none(self, resolver):
        eid = await resolver.resolve_entity("Nobody Here", "TestRP")
        assert eid is None


class TestGetConnections:
    @pytest.mark.asyncio
    async def test_hop_1_returns_direct(self, resolver):
        connections = await resolver.get_connections(
            ["TestRP:dante moretti"], max_hops=1
        )
        # Dante should have connections to memories, relationships, etc.
        assert len(connections) > 0
        for conn in connections:
            assert conn.hop == 1

    @pytest.mark.asyncio
    async def test_hop_2_returns_deeper(self, resolver):
        connections = await resolver.get_connections(
            ["TestRP:dante moretti"], max_hops=2
        )
        hops = {c.hop for c in connections}
        # Should have at least hop 1
        assert 1 in hops

    @pytest.mark.asyncio
    async def test_seeds_not_in_results(self, resolver):
        connections = await resolver.get_connections(
            ["TestRP:dante moretti"], max_hops=2
        )
        for conn in connections:
            assert conn.entity_id != "TestRP:dante moretti"

    @pytest.mark.asyncio
    async def test_max_results_limit(self, resolver):
        connections = await resolver.get_connections(
            ["TestRP:dante moretti"], max_hops=3, max_results=2
        )
        assert len(connections) <= 2

    @pytest.mark.asyncio
    async def test_empty_seeds(self, resolver):
        connections = await resolver.get_connections([], max_hops=2)
        assert connections == []

    @pytest.mark.asyncio
    async def test_hop1_has_content(self, resolver):
        connections = await resolver.get_connections(
            ["TestRP:dante moretti"], max_hops=2
        )
        for conn in connections:
            if conn.hop == 1:
                assert conn.content is not None

    @pytest.mark.asyncio
    async def test_bidirectional_traversal(self, resolver):
        """Connections loaded from entity_connections go both ways."""
        # Memory → Dante via memories connection
        # So from Dante we should reach memory via _reverse edge
        connections = await resolver.get_connections(
            ["TestRP:dante moretti"], max_hops=1
        )
        entity_ids = [c.entity_id for c in connections]
        # Check we can reach the memory (card_indexer creates connection from Dante → memory)
        memory_found = any("memory" in eid or "lilith wakes" in eid for eid in entity_ids)
        assert memory_found, f"Expected memory in connections, got: {entity_ids}"


class TestNPCEnrichment:
    @pytest.mark.asyncio
    async def test_returns_categorized(self, resolver):
        enrichment = await resolver.get_npc_enrichment(
            "TestRP:dante moretti", [], "TestRP"
        )
        assert "memories" in enrichment
        assert "secrets" in enrichment
        assert "knowledge" in enrichment
        assert isinstance(enrichment["memories"], list)


class TestFilterSecrets:
    @pytest.mark.asyncio
    async def test_known_by_filter(self, db, resolver):
        """Secrets with known_by that doesn't include character are filtered out."""
        # Insert a secret with known_by only listing "Dante"
        future = await db.enqueue_write(
            """INSERT INTO story_cards (id, rp_folder, file_path, card_type, name, frontmatter, content)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                "TestRP:test_secret",
                "TestRP",
                "test.md",
                "secret",
                "Test Secret",
                json.dumps({"known_by": ["Dante"]}),
                "Secret content",
            ],
        )
        await future

        # Lilith should NOT see this secret
        kept = await resolver.filter_secrets_for_character(
            ["TestRP:test_secret"], "TestRP:lilith"
        )
        assert "TestRP:test_secret" not in kept

        # Dante should see it
        kept = await resolver.filter_secrets_for_character(
            ["TestRP:test_secret"], "TestRP:dante"
        )
        assert "TestRP:test_secret" in kept

    @pytest.mark.asyncio
    async def test_empty_input(self, resolver):
        kept = await resolver.filter_secrets_for_character([], "TestRP:lilith")
        assert kept == []
