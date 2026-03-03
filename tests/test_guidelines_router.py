"""Tests for guidelines endpoint."""

from __future__ import annotations

import httpx
import pytest

from rp_engine.dependencies import get_vault_root
from tests.conftest import create_test_app


@pytest.fixture
def app(sample_card_dir):
    test_app = create_test_app()
    test_app.dependency_overrides[get_vault_root] = lambda: sample_card_dir
    return test_app


class TestGetGuidelines:
    async def test_parse_guidelines(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/context/guidelines?rp_folder=TestRP")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pov_mode"] == "dual"
        assert data["dual_characters"] == ["Lilith", "Dante"]
        assert data["narrative_voice"] == "first"
        assert data["tense"] == "present"
        assert data["scene_pacing"] == "moderate"

    async def test_missing_guidelines(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/context/guidelines?rp_folder=NonExistent")
        assert resp.status_code == 404

    async def test_cache_hit(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            await c.get("/api/context/guidelines?rp_folder=TestRP")
            resp = await c.get("/api/context/guidelines?rp_folder=TestRP")
        assert resp.status_code == 200

    async def test_required_rp_folder(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/context/guidelines")
        assert resp.status_code == 422
