"""Tests for exchanges router endpoints."""

from __future__ import annotations

import httpx
import pytest

from rp_engine.config import TrustConfig
from rp_engine.dependencies import get_db
from rp_engine.services.branch_manager import BranchManager
from rp_engine.services.state_manager import StateManager
from tests.conftest import create_test_app


@pytest.fixture
def app(db):
    test_app = create_test_app()
    test_app.dependency_overrides[get_db] = lambda: db
    # Phase 6: exchange endpoints now depend on state_manager and branch_manager
    sm = StateManager(db=db, config=TrustConfig())
    bm = BranchManager(db=db, state_manager=sm)
    test_app.state.state_manager = sm
    test_app.state.branch_manager = bm
    return test_app


async def _create_session(c: httpx.AsyncClient, rp_folder="TestRP") -> str:
    resp = await c.post("/api/sessions", json={"rp_folder": rp_folder})
    return resp.json()["id"]


class TestSaveExchange:
    async def test_save_basic(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            session_id = await _create_session(c)
            resp = await c.post("/api/exchanges", json={
                "user_message": "Hello",
                "assistant_response": "Hi there!",
                "session_id": session_id,
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["exchange_number"] == 1
        assert data["session_id"] == session_id

    async def test_auto_number(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            session_id = await _create_session(c)
            await c.post("/api/exchanges", json={
                "user_message": "First", "assistant_response": "One", "session_id": session_id,
            })
            resp = await c.post("/api/exchanges", json={
                "user_message": "Second", "assistant_response": "Two", "session_id": session_id,
            })
        assert resp.json()["exchange_number"] == 2

    async def test_active_session_fallback(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            await _create_session(c)
            resp = await c.post("/api/exchanges", json={
                "user_message": "Test", "assistant_response": "Response",
            })
        assert resp.status_code == 201

    async def test_no_session_error(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/exchanges", json={
                "user_message": "Test", "assistant_response": "Response",
            })
        assert resp.status_code == 404

    async def test_idempotency(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            session_id = await _create_session(c)
            body = {
                "user_message": "Test",
                "assistant_response": "Response",
                "session_id": session_id,
                "idempotency_key": "unique-key-123",
            }
            resp1 = await c.post("/api/exchanges", json=body)
            resp2 = await c.post("/api/exchanges", json=body)
        assert resp1.json()["id"] == resp2.json()["id"]
        assert resp2.json()["idempotent_hit"] is True

    async def test_parent_validation_conflict(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            session_id = await _create_session(c)
            await c.post("/api/exchanges", json={
                "user_message": "First", "assistant_response": "One", "session_id": session_id,
            })
            resp = await c.post("/api/exchanges", json={
                "user_message": "Third",
                "assistant_response": "Three",
                "session_id": session_id,
                "parent_exchange_number": 5,
            })
        assert resp.status_code == 409

    async def test_rewind(self, app):
        """Rewind creates a new branch and saves the exchange there (CoW)."""
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            session_id = await _create_session(c)
            for i in range(1, 4):
                await c.post("/api/exchanges", json={
                    "user_message": f"Msg {i}",
                    "assistant_response": f"Resp {i}",
                    "session_id": session_id,
                })
            resp = await c.post("/api/exchanges", json={
                "user_message": "New msg 2",
                "assistant_response": "New resp 2",
                "session_id": session_id,
                "exchange_number": 2,
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["exchange_number"] == 2
        # In CoW system, rewound_count is 0 since we branch instead of deleting
        assert data["rewound_count"] == 0


class TestListExchanges:
    async def test_list_all(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            session_id = await _create_session(c)
            await c.post("/api/exchanges", json={
                "user_message": "Test", "assistant_response": "Resp", "session_id": session_id,
            })
            resp = await c.get("/api/exchanges")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] >= 1

    async def test_filter_by_session(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            sid = await _create_session(c)
            await c.post("/api/exchanges", json={
                "user_message": "Test", "assistant_response": "Resp", "session_id": sid,
            })
            resp = await c.get(f"/api/exchanges?session_id={sid}")
        assert resp.status_code == 200
        assert resp.json()["total_count"] >= 1


class TestRecentExchanges:
    async def test_recent(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            session_id = await _create_session(c)
            await c.post("/api/exchanges", json={
                "user_message": "Test", "assistant_response": "Resp", "session_id": session_id,
            })
            resp = await c.get("/api/exchanges/recent?limit=5")
        assert resp.status_code == 200
        assert len(resp.json()["exchanges"]) >= 1


class TestDeleteExchange:
    async def test_delete(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            session_id = await _create_session(c)
            create_resp = await c.post("/api/exchanges", json={
                "user_message": "To delete", "assistant_response": "Will be gone", "session_id": session_id,
            })
            eid = create_resp.json()["id"]
            resp = await c.delete(f"/api/exchanges/{eid}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_delete_nonexistent(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete("/api/exchanges/99999")
        assert resp.status_code == 404
