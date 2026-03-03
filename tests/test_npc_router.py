"""Tests for NPC router endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from rp_engine.config import SearchConfig, get_config
from rp_engine.dependencies import (
    get_card_indexer,
    get_db,
    get_npc_engine,
    get_vault_root,
)
from rp_engine.services.graph_resolver import GraphResolver
from rp_engine.services.npc_engine import NPCEngine
from rp_engine.services.vector_search import VectorSearch
from tests.conftest import MockLLMClient, create_test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_character(db, name: str, rp_folder: str = "TestRP", branch: str = "main"):
    char_id = f"{rp_folder}:{branch}:{name.lower()}"
    future = await db.enqueue_write(
        """INSERT OR REPLACE INTO characters
           (id, rp_folder, branch, name, importance, primary_archetype, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [char_id, rp_folder, branch, name, "main", "POWER_HOLDER",
         datetime.now(timezone.utc).isoformat()],
    )
    await future


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def app(db, sample_card_dir, card_indexer, mock_llm):
    """Test app with NPC engine wired up."""
    test_app = create_test_app()

    graph_resolver = GraphResolver(db)
    search_config = SearchConfig()
    vector_search = VectorSearch(db, search_config, embed_fn=mock_llm.embed)
    config = get_config()
    engine = NPCEngine(
        db=db,
        llm_client=mock_llm,
        graph_resolver=graph_resolver,
        vector_search=vector_search,
        config=config,
        vault_root=sample_card_dir,
    )

    test_app.dependency_overrides[get_db] = lambda: db
    test_app.dependency_overrides[get_card_indexer] = lambda: card_indexer
    test_app.dependency_overrides[get_vault_root] = lambda: sample_card_dir
    test_app.dependency_overrides[get_npc_engine] = lambda: engine

    return test_app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReact:
    @pytest.mark.asyncio
    async def test_returns_reaction(self, app, db):
        await _insert_character(db, "Dante Moretti")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                "/api/npc/react?rp_folder=TestRP",
                json={"npc_name": "Dante Moretti", "scene_prompt": "Lilith enters"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["character"] == "Dante Moretti"
        assert "internalMonologue" in data
        assert "trustShift" in data

    @pytest.mark.asyncio
    async def test_unknown_npc_404(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                "/api/npc/react?rp_folder=TestRP",
                json={"npc_name": "Nobody", "scene_prompt": "test"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_rp_folder(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                "/api/npc/react",
                json={"npc_name": "Dante", "scene_prompt": "test"},
            )

        assert resp.status_code == 422  # Missing required query param


class TestReactBatch:
    @pytest.mark.asyncio
    async def test_batch_returns_list(self, app, db):
        await _insert_character(db, "Dante Moretti")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                "/api/npc/react-batch?rp_folder=TestRP",
                json={
                    "npc_names": ["Dante Moretti"],
                    "scene_prompt": "Lilith walks in",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["character"] == "Dante Moretti"

    @pytest.mark.asyncio
    async def test_batch_empty_names(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                "/api/npc/react-batch?rp_folder=TestRP",
                json={"npc_names": [], "scene_prompt": "test"},
            )

        assert resp.status_code == 200
        assert resp.json() == []


class TestGetTrust:
    @pytest.mark.asyncio
    async def test_returns_trust_info(self, app, db):
        # Insert relationship
        future = await db.enqueue_write(
            """INSERT INTO relationships
               (rp_folder, branch, character_a, character_b, initial_trust_score,
                trust_modification_sum, trust_stage, dynamic, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ["TestRP", "main", "Dante Moretti", "Lilith", 16, 0, "familiar",
             "cautious respect", datetime.now(timezone.utc).isoformat()],
        )
        await future

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get("/api/npc/Dante Moretti/trust?rp_folder=TestRP")

        assert resp.status_code == 200
        data = resp.json()
        assert data["npc_name"] == "Dante Moretti"
        assert data["trust_score"] == 16
        assert data["trust_stage"] == "familiar"

    @pytest.mark.asyncio
    async def test_no_relationship_returns_zero(self, app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get("/api/npc/Unknown/trust?rp_folder=TestRP")

        assert resp.status_code == 200
        data = resp.json()
        assert data["trust_score"] == 0
        assert data["trust_stage"] == "neutral"


class TestListNPCs:
    @pytest.mark.asyncio
    async def test_returns_list(self, app, db):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get("/api/npcs?rp_folder=TestRP")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have at least Dante from indexed cards
        names = [n["name"] for n in data]
        assert "Dante Moretti" in names

    @pytest.mark.asyncio
    async def test_returns_archetype_info(self, app, db):
        await _insert_character(db, "Dante Moretti")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get("/api/npcs?rp_folder=TestRP")

        data = resp.json()
        dante = next(n for n in data if n["name"] == "Dante Moretti")
        assert dante["primary_archetype"] == "POWER_HOLDER"
