# tests/test_domain.py — all 6 detection branches + sanitize (PART 1 §3).
# Author: OpenCode
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("PUBLIC_DOMAIN", "RAILWAY_PUBLIC_DOMAIN"):
        monkeypatch.delenv(var, raising=False)
    from app import domain

    domain._cache["value"] = None
    domain._cache["at"] = 0.0
    yield


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


def test_branch1_public_domain_env(monkeypatch):
    monkeypatch.setenv("PUBLIC_DOMAIN", "My.Panel.IR")
    from app.domain import detect_domain

    assert detect_domain(None) == "My.Panel.IR"


def test_branch2_forwarded_host():
    from app.domain import detect_domain

    req = FakeRequest({"x-forwarded-host": "panel.example.com, other.com"})
    assert detect_domain(req) == "panel.example.com"


def test_branch3_host_header():
    from app.domain import detect_domain

    req = FakeRequest({"host": "panel.example.com"})
    assert detect_domain(req) == "panel.example.com"


def test_branch4_railway(monkeypatch):
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "neon.up.railway.app")
    from app.domain import detect_domain

    assert detect_domain(None) == "neon.up.railway.app"


def test_branch5_tunnel_cache(monkeypatch):

    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    from app import domain

    domain.remember_tunnel_url("https://abc-def.trycloudflare.com")
    # headers absent, envs absent → cache branch wins
    assert domain.detect_domain(FakeRequest()) == "https://abc-def.trycloudflare.com"


def test_branch6_fallback(monkeypatch):
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    monkeypatch.setenv("PORT", "9090")
    from app.domain import detect_domain

    assert detect_domain(FakeRequest()) == "localhost:9090"


def test_sanitize_valid():
    from app.domain import sanitize_host

    assert sanitize_host("Panel.Example.COM") == "panel.example.com"
    assert sanitize_host("a.b:8080") == "a.b:8080"


def test_sanitize_xss_rejected():
    from app.domain import sanitize_host

    assert sanitize_host("<script>alert(1)</script>") is None
    assert sanitize_host("evil.com/path") is None


def test_sanitize_length_and_empty():
    from app.domain import sanitize_host

    assert sanitize_host("") is None
    assert sanitize_host("a" * 254) is None
    assert sanitize_host("a" * 253) == "a" * 253
