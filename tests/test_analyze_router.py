"""Integration tests for analyze router endpoints."""

from __future__ import annotations

import httpx
import pytest

from rp_engine.dependencies import get_db
from tests.conftest import create_test_app


RP = "TestRP"


@pytest.fixture
def app(db):
    test_app = create_test_app()
    test_app.dependency_overrides[get_db] = lambda: db
    return test_app


async def _seed_gap(db, entity_name, seen_count=1, suggested_type=None):
    """Insert a card_gaps row."""
    future = await db.enqueue_write(
        """INSERT INTO card_gaps (entity_name, rp_folder, suggested_type, seen_count, first_seen, last_seen)
           VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
        [entity_name, RP, suggested_type, seen_count],
    )
    await future


class TestGetGaps:
    async def test_get_gaps(self, app, db):
        await _seed_gap(db, "Marco", 5, "npc")
        await _seed_gap(db, "The Docks", 3, "location")

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/analyze/gaps", params={"rp_folder": RP})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        names = {g["entity_name"] for g in data["gaps"]}
        assert "Marco" in names
        assert "The Docks" in names

    async def test_get_gaps_min_count_filter(self, app, db):
        await _seed_gap(db, "Marco", 5)
        await _seed_gap(db, "Random NPC", 1)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/analyze/gaps", params={"rp_folder": RP, "min_seen_count": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["gaps"][0]["entity_name"] == "Marco"

    async def test_get_gaps_empty(self, app, db):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/analyze/gaps", params={"rp_folder": "NoRP"})
        assert resp.status_code == 200
        assert resp.json()["gaps"] == []
        assert resp.json()["total"] == 0

    async def test_gaps_ordered_by_count(self, app, db):
        await _seed_gap(db, "Low", 2)
        await _seed_gap(db, "High", 10)
        await _seed_gap(db, "Mid", 5)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/analyze/gaps", params={"rp_folder": RP})
        gaps = resp.json()["gaps"]
        counts = [g["seen_count"] for g in gaps]
        assert counts == sorted(counts, reverse=True)
        assert counts == [10, 5, 2]
