# tests/test_sub.py — v2: formats + beautiful HTML page + userinfo + 404s.
# Author: OpenCode
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
CLIENT_UA = "okhttp/4.12.0"


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


def _get_sub(client, token, ua, host="panel.example.com"):
    return client.get(f"/sub/{token}",
                      headers={"user-agent": ua, "host": host})


def test_sub_base64_decodes_to_links(client):
    d = _make_user(client)
    r = _get_sub(client, d["sub_token"], CLIENT_UA)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    decoded = base64.b64decode(r.text).decode()
    assert "vless://" in decoded and f"vless://{d['uuid']}" in decoded
    assert "panel.example.com" in decoded


def test_sub_browser_gets_beautiful_html(client):
    d = _make_user(client)
    r = _get_sub(client, d["sub_token"], BROWSER_UA)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # page shows the real links, not random chars
    assert "vless://" in r.text
    assert d["name"] in r.text
    assert "/api/qr/" in r.text  # QR images
    assert "مصرف" in r.text  # Persian stats labels
    assert f"/sub/{d['sub_token']}" in r.text  # sub URL visible


def test_sub_html_explicit_fmt(client):
    d = _make_user(client)
    r = client.get(f"/sub/{d['sub_token']}?fmt=html")
    assert "text/html" in r.headers["content-type"]


def test_sub_userinfo_header(client):
    d = _make_user(client)
    r = _get_sub(client, d["sub_token"], CLIENT_UA)
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


def test_sub_qr_endpoint(client):
    d = _make_user(client)
    r = client.get(f"/api/qr/{d['sub_token']}?p=vless", headers={"host": "panel.example.com"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:4] == b"\x89PNG"
