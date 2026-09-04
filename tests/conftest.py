# tests/conftest.py — v3: env + fresh store per test + API client fixture.
# Author: OpenCode
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ADMIN_PASS", "test-pass-123")


@pytest.fixture(autouse=True)
def fresh_store(tmp_path, monkeypatch):
    """Every test gets an empty store on a temp dir + clean login attempts."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    from app import auth, store

    store._state = {"configs": {}, "groups": {}, "admin_hash": "", "seq": 1}
    auth._attempts.clear()  # unlock any IP locked by a previous test
    os.makedirs(tmp_path / "data", exist_ok=True)
    # keep save() a no-op in tests (no disk I/O)
    store.save = lambda: None
    yield store


@pytest.fixture()
def client(fresh_store, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    from passlib.context import CryptContext

    fresh_store._state["admin_hash"] = CryptContext(
        schemes=["bcrypt"], deprecated="auto").hash("test-pass-123")
    from app.bridge import Bridge
    from app.main import create_app

    app = create_app()
    with TestClient(Bridge(app)) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    client.post("/api/login", json={"password": "test-pass-123"})
    return client
