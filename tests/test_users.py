# tests/test_users.py — CRUD + name validation + duplicates (PART 2 §7.3).
# Author: OpenCode
from __future__ import annotations

AUTH = None


def _auth(client):
    r = client.post("/api/auth/login", json={"username": "RXpanel", "password": "test-pass-123"})
    return {"Authorization": f"Bearer {r.json()['data']['access']}"}


def test_create_user_ok(client):
    h = _auth(client)
    r = client.post("/api/users", json={"name": "reza-01", "quota_gb": 30, "expires_days": 30},
                    headers=h)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["uuid"] and d["sub_token"]
    assert "vless://" in d["links"]["vless"]
    assert "vmess://" in d["links"]["vmess"]
    assert "trojan://" in d["links"]["trojan"]
    assert d["sub_url"].endswith(f"/sub/{d['sub_token']}")


def test_create_user_bad_names(client):
    h = _auth(client)
    for bad in ["a", "x" * 33, "bad!name", "با!نام"]:
        r = client.post("/api/users", json={"name": bad}, headers=h)
        assert r.status_code == 400, bad
        assert r.json()["detail"]["code"] == "BAD_INPUT"
        assert "name" in r.json()["detail"].get("fields", [])


def test_create_user_duplicate(client):
    h = _auth(client)
    client.post("/api/users", json={"name": "reza-01"}, headers=h)
    r = client.post("/api/users", json={"name": "reza-01"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "DUPLICATE"


def test_patch_forbidden_field(client):
    h = _auth(client)
    r = client.post("/api/users", json={"name": "reza-02"}, headers=h)
    uid = r.json()["data"]["id"]
    r2 = client.patch(f"/api/users/{uid}", json={"uuid": "123"}, headers=h)
    assert r2.status_code == 400
    assert r2.json()["detail"]["code"] == "BAD_INPUT"


def test_disable_and_enable(client):
    h = _auth(client)
    r = client.post("/api/users", json={"name": "reza-03"}, headers=h)
    uid = r.json()["data"]["id"]
    r2 = client.patch(f"/api/users/{uid}", json={"enabled": False}, headers=h)
    assert r2.json()["data"]["enabled"] is False
    r3 = client.patch(f"/api/users/{uid}", json={"enabled": True}, headers=h)
    assert r3.json()["data"]["enabled"] is True


def test_reset_usage(client):
    h = _auth(client)
    r = client.post("/api/users", json={"name": "reza-04"}, headers=h)
    uid = r.json()["data"]["id"]
    r2 = client.post(f"/api/users/{uid}/reset", headers=h)
    assert r2.status_code == 200
    assert r2.json()["data"]["used_bytes"] == 0


def test_delete_user(client):
    h = _auth(client)
    r = client.post("/api/users", json={"name": "reza-05"}, headers=h)
    uid = r.json()["data"]["id"]
    r2 = client.delete(f"/api/users/{uid}?wipe=true", headers=h)
    assert r2.status_code == 200
    r3 = client.get(f"/api/users/{uid}", headers=h)
    assert r3.status_code == 404


def test_list_search_pagination(client):
    h = _auth(client)
    for i in range(3):
        client.post("/api/users", json={"name": f"reza-1{i}"}, headers=h)
    r = client.get("/api/users?page=1&per=2&q=reza-1", headers=h)
    d = r.json()["data"]
    assert d["total"] == 3
    assert len(d["items"]) == 2


def test_no_auth_401(client):
    r = client.get("/api/users")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "NO_AUTH"
