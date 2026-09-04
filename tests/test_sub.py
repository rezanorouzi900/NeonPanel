# tests/test_sub.py — base64/clash/singbox/json formats + userinfo + 404s.
# Author: OpenCode
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta


def _login(client):
    r = client.post("/api/auth/login", json={"username": "RXpanel", "password": "test-pass-123"})
    return {"Authorization": f"Bearer {r.json()['data']['access']}"}


def _make_user(client):
    h = _login(client)
    name = f"sub-user-{uuid.uuid4().hex[:8]}"
    r = client.post("/api/users", json={"name": name, "quota_gb": 10, "expires_days": 30},
                    headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    data["name"] = name
    return data


def test_sub_base64_decodes_to_links(client):
    d = _make_user(client)
    r = client.get(f"/sub/{d['sub_token']}", headers={"host": "panel.example.com"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    decoded = base64.b64decode(r.text).decode()
    assert "vless://" in decoded and "vmess://" in decoded
    assert "trojan://" in decoded
    assert f"vless://{d['uuid']}" in decoded
    assert "panel.example.com" in decoded


def test_sub_userinfo_header(client):
    d = _make_user(client)
    r = client.get(f"/sub/{d['sub_token']}", headers={"host": "panel.example.com"})
    ui = r.headers.get("subscription-userinfo", "")
    assert "download=" in ui and "total=" in ui and "expire=" in ui


def test_sub_clash_yaml(client):
    d = _make_user(client)
    r = client.get(f"/sub/{d['sub_token']}?fmt=clash", headers={"host": "panel.example.com"})
    assert r.status_code == 200
    assert r.text.lstrip().startswith("proxies:")
    assert "type: vless" in r.text and "url-test" in r.text


def test_sub_singbox_json(client):
    d = _make_user(client)
    r = client.get(f"/sub/{d['sub_token']}?fmt=singbox", headers={"host": "panel.example.com"})
    doc = r.json()
    tags = [o["tag"] for o in doc["outbounds"]]
    assert any("VLESS" in t for t in tags)
    assert any(o["type"] == "urltest" for o in doc["outbounds"])


def test_sub_json_format(client):
    d = _make_user(client)
    r = client.get(f"/sub/{d['sub_token']}?fmt=json", headers={"host": "panel.example.com"})
    doc = r.json()
    assert doc["name"].startswith("sub-user-")
    assert doc["quota_gb"] == 10
    assert "vless" in doc["links"]


def test_sub_bad_token_404(client):
    r = client.get("/sub/not-a-real-token")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "SUB_GONE"


def test_sub_disabled_user_404(client):
    d = _make_user(client)
    h = _login(client)
    client.patch(f"/api/users/{d['id']}", json={"enabled": False}, headers=h)
    r = client.get(f"/sub/{d['sub_token']}")
    assert r.status_code == 404
    assert "فعال" in r.text


def test_sub_expired_user_404(client):
    d = _make_user(client)
    # force expiry directly in DB
    from sqlmodel import Session

    from app.config import settings
    from app.db import get_engine
    from app.models import User

    with Session(get_engine(settings.data_dir)) as s:
        u = s.get(User, d["id"])
        u.expires_at = datetime.utcnow() - timedelta(days=2)
        s.add(u)
        s.commit()
    r = client.get(f"/sub/{d['sub_token']}")
    assert r.status_code == 404
