"""Integration tests for state router endpoints."""

from __future__ import annotations

import httpx
import pytest

from rp_engine.config import TrustConfig
from rp_engine.dependencies import get_db, get_state_manager
from rp_engine.services.state_manager import StateManager
from tests.conftest import create_test_app


@pytest.fixture
def app(db):
    test_app = create_test_app()
    sm = StateManager(db=db, config=TrustConfig())
    test_app.dependency_overrides[get_db] = lambda: db
    test_app.dependency_overrides[get_state_manager] = lambda: sm
    return test_app


RP = "Mafia"


# ---------------------------------------------------------------------------
# Character Endpoints
# ---------------------------------------------------------------------------


class TestCharacterEndpoints:
    async def test_get_characters_empty(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/state/characters", params={"rp_folder": RP})
        assert resp.status_code == 200
        assert resp.json()["characters"] == {}

    async def test_get_character_not_found(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/state/characters/Nobody", params={"rp_folder": RP})
        assert resp.status_code == 404

    async def test_update_and_get_character(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            # PUT to create
            resp = await c.put(
                "/api/state/characters/Dante",
                params={"rp_folder": RP},
                json={"location": "warehouse", "emotional_state": "tense"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "Dante"
            assert data["location"] == "warehouse"
            assert data["emotional_state"] == "tense"

            # GET to verify
            resp = await c.get("/api/state/characters/Dante", params={"rp_folder": RP})
            assert resp.status_code == 200
            assert resp.json()["location"] == "warehouse"

    async def test_get_characters_location_filter(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            await c.put(
                "/api/state/characters/Dante",
                params={"rp_folder": RP},
                json={"location": "warehouse"},
            )
            await c.put(
                "/api/state/characters/Lilith",
                params={"rp_folder": RP},
                json={"location": "penthouse"},
            )

            resp = await c.get(
                "/api/state/characters",
                params={"rp_folder": RP, "location": "warehouse"},
            )
            assert resp.status_code == 200
            chars = resp.json()["characters"]
            assert len(chars) == 1
            assert "Dante" in chars


# ---------------------------------------------------------------------------
# Relationship Endpoints
# ---------------------------------------------------------------------------


class TestRelationshipEndpoints:
    async def test_get_relationships_empty(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/state/relationships", params={"rp_folder": RP})
        assert resp.status_code == 200
        assert resp.json()["relationships"] == []

    async def test_update_trust_and_get(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            # PUT trust change
            resp = await c.put(
                "/api/state/relationships/Dante/Lilith",
                params={"rp_folder": RP},
                json={"trust_change": 5, "reason": "Saved her", "direction": "positive"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["live_trust_score"] == 5
            assert data["character_a"] == "Dante"

            # GET relationships
            resp = await c.get("/api/state/relationships", params={"rp_folder": RP})
            rels = resp.json()["relationships"]
            assert len(rels) == 1
            assert rels[0]["live_trust_score"] == 5

    async def test_trust_stage_in_response(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put(
                "/api/state/relationships/Dante/Lilith",
                params={"rp_folder": RP},
                json={"trust_change": 5, "reason": "Trust built", "direction": "positive"},
            )
            data = resp.json()
            assert data["trust_stage"] == "neutral"  # 5 is in 0-9 range


# ---------------------------------------------------------------------------
# Scene Endpoints
# ---------------------------------------------------------------------------


class TestSceneEndpoints:
    async def test_get_scene_default(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/state/scene", params={"rp_folder": RP})
        assert resp.status_code == 200
        data = resp.json()
        assert data["location"] is None

    async def test_update_and_get_scene(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put(
                "/api/state/scene",
                params={"rp_folder": RP},
                json={"location": "warehouse", "mood": "tense"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["location"] == "warehouse"
            assert data["mood"] == "tense"

            # GET
            resp = await c.get("/api/state/scene", params={"rp_folder": RP})
            assert resp.json()["location"] == "warehouse"


# ---------------------------------------------------------------------------
# Event Endpoints
# ---------------------------------------------------------------------------


class TestEventEndpoints:
    async def test_create_event(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/state/events",
                params={"rp_folder": RP},
                json={
                    "event": "Dante punched Marco",
                    "characters": ["Dante", "Marco"],
                    "significance": "high",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["event"] == "Dante punched Marco"
        assert data["characters"] == ["Dante", "Marco"]
        assert data["id"] is not None

    async def test_get_events_with_filters(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            await c.post(
                "/api/state/events",
                params={"rp_folder": RP},
                json={"event": "Low event", "significance": "low"},
            )
            await c.post(
                "/api/state/events",
                params={"rp_folder": RP},
                json={"event": "High event", "significance": "high"},
            )

            resp = await c.get(
                "/api/state/events",
                params={"rp_folder": RP, "significance": "high"},
            )
            events = resp.json()["events"]
            assert len(events) == 1
            assert events[0]["event"] == "High event"


# ---------------------------------------------------------------------------
# Full State Snapshot
# ---------------------------------------------------------------------------


class TestStateSnapshot:
    async def test_full_state(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            # Populate some data
            await c.put(
                "/api/state/characters/Dante",
                params={"rp_folder": RP},
                json={"location": "warehouse"},
            )
            await c.put(
                "/api/state/scene",
                params={"rp_folder": RP},
                json={"location": "warehouse"},
            )
            await c.post(
                "/api/state/events",
                params={"rp_folder": RP},
                json={"event": "Something", "significance": "medium"},
            )

            # GET full state
            resp = await c.get("/api/state", params={"rp_folder": RP})
            assert resp.status_code == 200
            data = resp.json()
            assert "Dante" in data["characters"]
            assert data["scene"]["location"] == "warehouse"
            assert len(data["events"]) == 1
            assert data["branch"] == "main"
