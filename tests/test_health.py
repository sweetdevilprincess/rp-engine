"""Integration tests for the /health endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rp_engine.config import get_config


@pytest.fixture(autouse=True)
def _use_temp_paths(tmp_path):
    """Override config to use temp database and vault root for integration tests."""
    get_config.cache_clear()
    config = get_config()
    config.paths.db_path = str(tmp_path / "test.db")
    config.paths.vault_root = str(tmp_path)
    yield
    get_config.cache_clear()


@pytest.fixture
def client():
    """Synchronous test client that triggers full lifespan."""
    from rp_engine.main import app

    with TestClient(app) as c:
        yield c


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data


def test_health_includes_table_count(client):
    response = client.get("/health")
    data = response.json()
    assert data["database"]["tables"] >= 20


def test_health_wal_mode(client):
    response = client.get("/health")
    data = response.json()
    assert data["database"]["journal_mode"] == "wal"
