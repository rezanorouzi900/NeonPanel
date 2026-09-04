# tests/conftest.py — shared fixtures: env, fresh DB, test client.
# Author: OpenCode
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

os.environ.setdefault("ADMIN_USER", "RXpanel")
os.environ.setdefault("ADMIN_PASS", "test-pass-123")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="neon-test-"))
os.environ.setdefault("TESTING", "1")


@pytest.fixture(autouse=True)
def _reset_login_guard():
    from app.auth import guard

    guard.attempts.clear()
    guard.locked.clear()
    yield
    guard.attempts.clear()
    guard.locked.clear()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    from app.config import settings

    settings.data_dir = str(tmp_path / "data")
    from app.db import get_engine, init_db

    engine = get_engine(settings.data_dir)
    init_db(engine)
    from app.routes import init_ws_paths, seed_first_admin

    with Session(engine) as s:
        init_ws_paths(s)
        seed_first_admin(s)
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def auth_header(client):
    r = client.post("/api/auth/login", json={"username": "RXpanel", "password": "test-pass-123"})
    tok = r.json()["data"]["access"]
    return {"Authorization": f"Bearer {tok}"}
