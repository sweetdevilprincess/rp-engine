"""Integration tests for card suggest and audit endpoints."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from rp_engine.dependencies import get_db, get_llm_client, get_vault_root
from tests.conftest import MockLLMClient, create_test_app


RP = "TestRP"


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Temp vault with a template file."""
    templates = tmp_path / "z_templates" / "Story Cards"
    templates.mkdir(parents=True)
    (templates / "NPC Template.md").write_text(
        "---\ntype: npc\nname: \"\"\n---\n\nDescription here.\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def app(db, mock_llm, vault):
    test_app = create_test_app()
    test_app.dependency_overrides[get_db] = lambda: db
    test_app.dependency_overrides[get_llm_client] = lambda: mock_llm
    test_app.dependency_overrides[get_vault_root] = lambda: vault
    return test_app


async def _seed_session_and_exchanges(db, count=3, rp_folder=RP):
    """Create a session and exchanges with proper nouns in the response text."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    future = await db.enqueue_write(
        "INSERT INTO sessions (id, rp_folder, branch, started_at) VALUES (?, ?, ?, ?)",
        ["sess-1", rp_folder, "main", now],
    )
    await future

    for i in range(1, count + 1):
        future = await db.enqueue_write(
            """INSERT INTO exchanges (session_id, rp_folder, branch, exchange_number,
                   user_message, assistant_response, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                "sess-1", rp_folder, "main", i,
                f"User message {i}",
                f"Marco Bellini walked into the warehouse. Giovanni watched from the shadows. Marco smirked.",
                now,
            ],
        )
        await future


class TestSuggestCard:
    async def test_suggest_card(self, app, db, mock_llm):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/cards/suggest", json={
                "entity_name": "Marco",
                "card_type": "npc",
                "rp_folder": RP,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_name"] == "Marco"
        assert data["card_type"] == "npc"
        assert "markdown" in data
        # Verify LLM was called
        assert len(mock_llm.calls) == 1

    async def test_suggest_card_missing_fields(self, app, db):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/cards/suggest", json={
                "card_type": "npc",
                "rp_folder": RP,
            })
        assert resp.status_code == 400


class TestAuditCards:
    async def test_audit_quick_mode(self, app, db):
        await _seed_session_and_exchanges(db, count=3)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/cards/audit", json={"rp_folder": RP})
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "quick"
        assert data["total_exchanges_scanned"] == 3
        # Marco Bellini and Giovanni should be detected as proper nouns
        gap_names = {g["entity_name"] for g in data["gaps"]}
        assert "Marco Bellini" in gap_names or "Marco" in gap_names

    async def test_audit_empty(self, app, db):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/cards/audit", json={"rp_folder": "EmptyRP"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["gaps"] == []
        assert data["total_gaps"] == 0

    async def test_audit_filters_known_entities(self, app, db):
        await _seed_session_and_exchanges(db, count=3)

        # Insert Marco as a known story card
        future = await db.enqueue_write(
            """INSERT INTO story_cards (rp_folder, file_path, card_type, name, importance)
               VALUES (?, ?, ?, ?, ?)""",
            [RP, "TestRP/Story Cards/Characters/Marco.md", "character", "Marco", "main"],
        )
        await future

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/cards/audit", json={"rp_folder": RP})
        data = resp.json()
        gap_names = {g["entity_name"].lower() for g in data["gaps"]}
        # "Marco" by itself should be filtered since the card name is "Marco"
        assert "marco" not in gap_names
