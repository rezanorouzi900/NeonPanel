# tests/test_security.py — admin routes need JWT, headers present, scrub, rate limit.
# Author: OpenCode
from __future__ import annotations

PROTECTED = [
    ("/api/users", "GET"),
    ("/api/stats/summary", "GET"),
    ("/api/domain", "GET"),
    ("/api/tunnel", "GET"),
    ("/api/mtproto", "GET"),
    ("/api/xray/reload", "POST"),
    ("/api/backup", "GET"),
    ("/api/users/1", "PATCH"),
    ("/api/users/1", "DELETE"),
]


def test_admin_routes_require_auth(client):
    for path, method in PROTECTED:
        r = getattr(client, method.lower())(path)
        assert r.status_code == 401, f"{method} {path} leaked"


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "strict-origin" in r.headers.get("referrer-policy", "")


def test_health_public_no_auth(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_scrub_masks_tokens():
    from app.security import scrub

    line = "token=ghp_abcdefghijklmnopqrst1234567890 called"
    assert "ghp_" not in scrub(line)
    assert "***" in scrub(line)


def test_sub_rate_limit_direct():
    # middleware is disabled under TESTING=1 — exercise the limiter class directly
    from app.security import RateLimitMiddleware

    lim = RateLimitMiddleware(None, "/sub/", 3, 60, "RATE")

    class FakeClient:
        host = "1.2.3.4"

    class FakeUrl:
        path = "/sub/abc"

    class FakeReq:
        url = FakeUrl()
        headers = {}
        client = FakeClient()

    class FakeResp:
        status_code = 200

    async def call_next(req):
        return FakeResp()

    import asyncio

    codes = []
    for _ in range(5):
        resp = asyncio.run(lim.dispatch(FakeReq(), call_next))
        codes.append(resp.status_code if hasattr(resp, "status_code") else resp.body_status)
    assert 429 in codes


def test_login_lock_via_guard():
    from app.auth import LoginGuard

    g = LoginGuard()
    ip = "9.9.9.9"
    for _ in range(5):
        g.record(ip)
    assert g.is_locked(ip) is True


def test_login_rate_limit(client):
    codes = [client.post("/api/auth/login",
                         json={"username": "x", "password": "y"}).status_code
             for _ in range(7)]
    assert 429 in codes


def test_error_shape_is_stable(client):
    r = client.get("/api/users")
    d = r.json()["detail"]
    assert set(d) >= {"ok", "code", "msg_fa"}
    assert d["ok"] is False
