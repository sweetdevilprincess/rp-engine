"""Tests for sessions router endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from rp_engine.config import TrustConfig
from rp_engine.dependencies import get_card_indexer, get_db, get_vault_root
from rp_engine.services.branch_manager import BranchManager
from rp_engine.services.state_manager import StateManager
from rp_engine.utils.frontmatter import parse_frontmatter
from tests.conftest import SAMPLE_CHARACTER_MD, create_test_app


class _StubIndexer:
    """Minimal stub for CardIndexer used by end_session trust writeback."""
    async def index_file(self, rp_folder, file_path):
        pass


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def app(db, vault):
    test_app = create_test_app()
    test_app.dependency_overrides[get_db] = lambda: db
    test_app.dependency_overrides[get_card_indexer] = lambda: _StubIndexer()
    test_app.dependency_overrides[get_vault_root] = lambda: vault
    # Phase 6: session endpoints now access branch_manager from app state
    sm = StateManager(db=db, config=TrustConfig())
    bm = BranchManager(db=db, state_manager=sm)
    test_app.state.state_manager = sm
    test_app.state.branch_manager = bm
    return test_app


class TestCreateSession:
    async def test_create(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/sessions", json={"rp_folder": "Mafia"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["rp_folder"] == "Mafia"
        assert data["branch"] == "main"
        assert len(data["id"]) == 12

    async def test_custom_branch(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/sessions", json={"rp_folder": "Mafia", "branch": "alt"})
        assert resp.status_code == 201
        assert resp.json()["branch"] == "alt"


class TestActiveSession:
    async def test_no_active(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/sessions/active")
        assert resp.status_code == 404

    async def test_get_active(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/sessions", json={"rp_folder": "Mafia"})
            resp = await c.get("/api/sessions/active")
        assert resp.status_code == 200
        assert resp.json()["rp_folder"] == "Mafia"


class TestEndSession:
    async def test_end_session(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            create_resp = await c.post("/api/sessions", json={"rp_folder": "Mafia"})
            session_id = create_resp.json()["id"]
            resp = await c.post(f"/api/sessions/{session_id}/end")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["ended_at"] is not None
        assert "summary" in data

    async def test_end_nonexistent(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/sessions/nonexistent/end")
        assert resp.status_code == 404

    async def test_end_already_ended(self, app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            create_resp = await c.post("/api/sessions", json={"rp_folder": "Mafia"})
            session_id = create_resp.json()["id"]
            await c.post(f"/api/sessions/{session_id}/end")
            resp = await c.post(f"/api/sessions/{session_id}/end")
        assert resp.status_code == 400


class TestTrustWriteback:
    async def test_end_session_cards_read_only(self, db, vault):
        """Cards are read-only in CoW system — trust lives only in DB, no writeback."""
        rp_folder = "TestRP"

        # Set up card file on disk
        card_dir = vault / rp_folder / "Story Cards" / "Characters"
        card_dir.mkdir(parents=True)
        card_file = card_dir / "Dante Moretti.md"
        card_file.write_text(SAMPLE_CHARACTER_MD, encoding="utf-8")
        original_content = card_file.read_text(encoding="utf-8")

        # Insert story card and relationship
        future = await db.enqueue_write(
            """INSERT INTO story_cards (rp_folder, file_path, card_type, name, importance)
               VALUES (?, ?, ?, ?, ?)""",
            [rp_folder, f"{rp_folder}/Story Cards/Characters/Dante Moretti.md",
             "character", "Dante Moretti", "main"],
        )
        await future

        future = await db.enqueue_write(
            """INSERT INTO relationships
                   (rp_folder, branch, character_a, character_b,
                    initial_trust_score, trust_modification_sum,
                    session_trust_gained, session_trust_lost, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            [rp_folder, "main", "Dante Moretti", "Lilith", 16, 5, 5, 0],
        )
        await future

        test_app = create_test_app()
        test_app.dependency_overrides[get_db] = lambda: db
        _sm = StateManager(db=db, config=TrustConfig())
        _bm = BranchManager(db=db, state_manager=_sm)
        test_app.state.state_manager = _sm
        test_app.state.branch_manager = _bm

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as c:
            create_resp = await c.post("/api/sessions", json={"rp_folder": rp_folder})
            session_id = create_resp.json()["id"]
            resp = await c.post(f"/api/sessions/{session_id}/end")

        assert resp.status_code == 200

        # Card file should NOT be modified (cards are read-only)
        assert card_file.read_text(encoding="utf-8") == original_content

        # DB relationships should remain unchanged (no reset at session end)
        rel_row = await db.fetch_one(
            "SELECT * FROM relationships WHERE rp_folder = ? AND branch = 'main'",
            [rp_folder],
        )
        assert rel_row["trust_modification_sum"] == 5  # NOT reset to 0
