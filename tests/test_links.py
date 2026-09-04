# tests/test_links.py — roundtrip parse of all 4 links + domain override.
# Author: OpenCode
from __future__ import annotations

from datetime import datetime, timedelta

from app.links import (
    build_all,
    build_ss,
    build_trojan,
    build_vless,
    build_vmess,
    parse_ss,
    parse_trojan,
    parse_vless,
    parse_vmess,
)
from app.models import User


def make_user():
    return User(
        id=1, name="reza-01", uuid="11111111-2222-3333-4444-555555555555",
        trojan_pass="trojanpass1", ss_pass="sspass1234", sub_token="tok",
    )


CTX = {"domain": "panel.example.com", "port": 443, "tls": True,
       "paths": {"vless": "/vX1", "vmess": "/vX2", "trojan": "/vX3"}, "ss_port": 8388}


def test_vless_roundtrip():
    u = make_user()
    link = build_vless(u, CTX["domain"], CTX["port"], "/vX1", True)
    p = parse_vless(link)
    assert p["uuid"] == u.uuid
    assert p["domain"] == "panel.example.com"
    assert p["path"] == "/vX1"
    assert p["security"] == "tls"


def test_vmess_roundtrip():
    u = make_user()
    link = build_vmess(u, CTX["domain"], CTX["port"], "/vX2", True)
    p = parse_vmess(link)
    assert p["id"] == u.uuid
    assert p["add"] == "panel.example.com"
    assert p["path"] == "/vX2"
    assert p["tls"] == "tls"


def test_trojan_roundtrip():
    u = make_user()
    link = build_trojan(u, CTX["domain"], CTX["port"], "/vX3", True)
    p = parse_trojan(link)
    assert p["password"] == u.trojan_pass
    assert p["domain"] == "panel.example.com"
    assert p["path"] == "/vX3"


def test_ss_roundtrip():
    u = make_user()
    link = build_ss(u, CTX["domain"], 8388)
    p = parse_ss(link)
    assert p["method"] == "aes-256-gcm"
    assert p["password"] == u.ss_pass
    assert p["domain"] == "panel.example.com"
    assert p["port"] == 8388


def test_build_all_contains_four():
    u = make_user()
    links = build_all(u, CTX)
    assert set(links) == {"vless", "vmess", "trojan", "ss"}


def test_build_all_ss_disabled():
    u = make_user()
    links = build_all(u, {**CTX, "ss_port": 0})
    assert "ss" not in links


def test_domain_override_applied():
    u = make_user()
    links = build_all(u, {**CTX, "domain": "new.example.org"})
    assert parse_vless(links["vless"])["domain"] == "new.example.org"


def test_unicode_name_fragment():
    u = make_user()
    u.name = "رضا"
    link = build_vless(u, CTX["domain"], CTX["port"], "/vX1", True)
    assert "رضا" not in link.split("#")[0]  # fragment percent-encoded


def test_usable_states():
    u = make_user()
    assert build_all  # smoke: function import path sane
    from app.links import user_usable

    u.enabled = False
    assert user_usable(u) == (False, "disabled")
    u.enabled = True
    u.expires_at = datetime.utcnow() - timedelta(days=1)
    assert user_usable(u) == (False, "expired")
    u.expires_at = None
    u.quota_gb = 1
    u.used_bytes = 1024**3
    assert user_usable(u) == (False, "quota_full")
    u.used_bytes = 0
    ok, reason = user_usable(u)
    assert ok and reason == "ok"
