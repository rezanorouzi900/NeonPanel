# tests/test_auth.py — login ok/bad, lock after 5 tries, refresh, change-pass.
# Author: OpenCode
from __future__ import annotations


def test_login_ok(client):
    r = client.post("/api/auth/login", json={"username": "RXpanel", "password": "test-pass-123"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["access"] and body["data"]["refresh"]


def test_login_bad(client):
    r = client.post("/api/auth/login", json={"username": "RXpanel", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "BAD_CRED"


def test_login_lock_after_5(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "RXpanel", "password": "wrong"})
    r = client.post("/api/auth/login", json={"username": "RXpanel", "password": "test-pass-123"})
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "LOCKED"


def test_refresh_ok(client):
    r = client.post("/api/auth/login", json={"username": "RXpanel", "password": "test-pass-123"})
    refresh = r.json()["data"]["refresh"]
    r2 = client.post("/api/auth/refresh", json={"refresh": refresh})
    assert r2.status_code == 200
    assert r2.json()["data"]["access"]


def test_refresh_bad_token(client):
    r = client.post("/api/auth/refresh", json={"refresh": "garbage.token.here"})
    assert r.status_code == 401


def test_change_password_cycle(client, auth_header):
    r = client.post("/api/auth/change-pass", json={"old": "test-pass-123", "new": "new-pass-456"},
                    headers=auth_header)
    assert r.status_code == 200
    r2 = client.post("/api/auth/login", json={"username": "RXpanel", "password": "new-pass-456"})
    assert r2.status_code == 200
    # change back for other tests
    client.post("/api/auth/login", json={"username": "RXpanel", "password": "new-pass-456"})
    r3 = client.post("/api/auth/change-pass", json={"old": "new-pass-456", "new": "test-pass-123"},
                     headers={"Authorization": f"Bearer {r2.json()['data']['access']}"})
    assert r3.status_code == 200


def test_change_password_too_short(client, auth_header):
    r = client.post("/api/auth/change-pass", json={"old": "test-pass-123", "new": "short"},
                    headers=auth_header)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BAD_INPUT"
