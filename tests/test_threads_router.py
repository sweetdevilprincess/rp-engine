"""Integration tests for threads router endpoints."""

from __future__ import annotations

import json

import httpx
import pytest

from rp_engine.dependencies import get_db, get_thread_tracker
from rp_engine.services.thread_tracker import ThreadTracker
from tests.conftest import create_test_app


RP = "TestRP"


@pytest.fixture
def app(db):
    test_app = create_test_app()
    tracker = ThreadTracker(db=db)
    test_app.dependency_overrides[get_db] = lambda: db
    test_app.dependency_overrides[get_thread_tracker] = lambda: tracker
    return test_app


async def _seed_thread(db, thread_id="thread_1", name="Core Tension", status="active",
                       keywords=None, thresholds=None, consequences=None, related_characters=None):
    """Insert a plot_threads row."""
    future = await db.enqueue_write(
        """INSERT INTO plot_threads (id, rp_folder, name, status, keywords, thresholds, consequences, related_characters)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            thread_id, RP, name, status,
            json.dumps(keywords or ["tension", "conflict"]),
            json.dumps(thresholds or {"gentle": 5, "moderate": 10, "strong": 15}),
            json.dumps(consequences or {"gentle": "Reminder needed", "moderate": "Characters drift", "strong": "Plot stalls"}),
            json.dumps(related_characters or ["Dante", "Lilith"]),
        ],
    )
    await future


async def _seed_counter(db, thread_id="thread_1", counter=0, branch="main"):
    """Insert a thread_counters row."""
    future = await db.enqueue_write(
        """INSERT INTO thread_counters (thread_id, rp_folder, branch, current_counter, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        [thread_id, RP, branch, counter],
    )
    await future


class TestListThreads:
    async def test_list_threads(self, app, db):
        await _seed_thread(db, "t1", "Thread A")
        await _seed_thread(db, "t2", "Thread B")
        await _seed_counter(db, "t1", 3)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/threads", params={"rp_folder": RP})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        names = {t["name"] for t in data["threads"]}
        assert "Thread A" in names
        assert "Thread B" in names
        # Verify counter was loaded for t1
        t1 = next(t for t in data["threads"] if t["thread_id"] == "t1")
        assert t1["current_counter"] == 3

    async def test_list_threads_empty(self, app, db):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/threads", params={"rp_folder": "NoRP"})
        assert resp.status_code == 200
        assert resp.json()["threads"] == []
        assert resp.json()["total"] == 0


class TestGetAlerts:
    async def test_get_alerts(self, app, db):
        await _seed_thread(db, "t1", "Stale Thread")
        await _seed_counter(db, "t1", 7)  # Above gentle (5), below moderate (10)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/threads/alerts", params={"rp_folder": RP})
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) == 1
        assert alerts[0]["thread_id"] == "t1"
        assert alerts[0]["level"] == "gentle"
        assert alerts[0]["counter"] == 7

    async def test_no_alerts_when_below_threshold(self, app, db):
        await _seed_thread(db, "t1", "Fresh Thread")
        await _seed_counter(db, "t1", 2)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/threads/alerts", params={"rp_folder": RP})
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetThread:
    async def test_get_thread_detail(self, app, db):
        await _seed_thread(db, "t1", "Core Tension", related_characters=["Dante", "Lilith"])
        await _seed_counter(db, "t1", 4)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/threads/t1", params={"rp_folder": RP})
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "t1"
        assert data["name"] == "Core Tension"
        assert data["current_counter"] == 4
        assert "Dante" in data["related_characters"]

    async def test_get_thread_not_found(self, app, db):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/threads/nope", params={"rp_folder": RP})
        assert resp.status_code == 404
