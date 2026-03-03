"""Tests for cards router endpoints."""

from __future__ import annotations

import httpx
import pytest

from rp_engine.dependencies import get_card_indexer, get_db, get_vault_root
from tests.conftest import create_test_app


@pytest.fixture
def app(db, sample_card_dir, card_indexer):
    test_app = create_test_app()
    test_app.dependency_overrides[get_db] = lambda: db
    test_app.dependency_overrides[get_card_indexer] = lambda: card_indexer
    test_app.dependency_overrides[get_vault_root] = lambda: sample_card_dir
    return test_app


class TestListCards:
    async def test_list_all(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/cards")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 6

    async def test_filter_by_type(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/cards?card_type=character")
        assert resp.status_code == 200
        data = resp.json()
        assert all(c["card_type"] == "character" for c in data["cards"])

    async def test_filter_by_rp_folder(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/cards?rp_folder=TestRP")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


class TestGetCard:
    async def test_get_by_name(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/cards/character/dante-moretti")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Dante Moretti"
        assert data["card_type"] == "character"
        assert "frontmatter" in data
        assert "connections" in data

    async def test_get_by_alias(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/cards/character/beasty")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Dante Moretti"

    async def test_not_found(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/cards/character/nonexistent")
        assert resp.status_code == 404


class TestCreateCard:
    async def test_create_card(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/cards/character?rp_folder=TestRP",
                json={"name": "New NPC", "frontmatter": {"importance": "minor"}, "content": "A new character."},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New NPC"

    async def test_create_duplicate(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            await c.post(
                "/api/cards/character?rp_folder=TestRP",
                json={"name": "Unique NPC", "content": "First."},
            )
            resp = await c.post(
                "/api/cards/character?rp_folder=TestRP",
                json={"name": "Unique NPC", "content": "Duplicate."},
            )
        assert resp.status_code == 409

    async def test_invalid_type(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/cards/invalid_type?rp_folder=TestRP",
                json={"name": "Test"},
            )
        assert resp.status_code == 400


class TestReindex:
    async def test_reindex(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/cards/reindex?rp_folder=TestRP")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entities"] >= 1
