"""Tests for RP management router."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from rp_engine.dependencies import get_card_indexer, get_db, get_vault_root
from rp_engine.services.card_indexer import CardIndexer
from tests.conftest import create_test_app


@pytest.fixture
def app(db, tmp_path):
    test_app = create_test_app()
    indexer = CardIndexer(db, tmp_path)
    test_app.dependency_overrides[get_db] = lambda: db
    test_app.dependency_overrides[get_card_indexer] = lambda: indexer
    test_app.dependency_overrides[get_vault_root] = lambda: tmp_path
    return test_app


class TestCreateRP:
    async def test_create(self, app, tmp_path):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/rp", json={"rp_name": "NewRP"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["rp_folder"] == "NewRP"
        assert len(data["created_files"]) > 0
        assert (tmp_path / "NewRP" / "Story Cards" / "Characters").is_dir()
        assert (tmp_path / "NewRP" / "RP State" / "Story_Guidelines.md").exists()

    async def test_create_duplicate(self, app, tmp_path):
        (tmp_path / "ExistingRP").mkdir()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/rp", json={"rp_name": "ExistingRP"})
        assert resp.status_code == 409


class TestListRPs:
    async def test_list_with_story_cards(self, app, tmp_path):
        (tmp_path / "MyRP" / "Story Cards").mkdir(parents=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/rp")
        assert resp.status_code == 200
        folders = [r["rp_folder"] for r in resp.json()]
        assert "MyRP" in folders


class TestGetRP:
    async def test_get_existing(self, app, tmp_path):
        (tmp_path / "TestRP" / "Story Cards").mkdir(parents=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/rp/TestRP")
        assert resp.status_code == 200
        assert resp.json()["rp_folder"] == "TestRP"

    async def test_get_nonexistent(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/rp/NonExistent")
        assert resp.status_code == 404
