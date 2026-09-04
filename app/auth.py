# app/auth.py
# Session-cookie auth (px-panel style: single admin password) + login rate limit.
# Author: OpenCode
from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request

SECRET = os.getenv("SECRET_KEY", "neon-dev-secret")
TTL = 8 * 3600
_attempts: dict[str, list[float]] = {}


def _sign( payload: str) -> str:
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    exp = int(time.time() + TTL)
    payload = f"admin:{exp}"
    return f"{exp}:{_sign(payload)}"


def verify_token(token: str | None) -> bool:
    if not token or ":" not in token:
        return False
    exp_str, sig = token.split(":", 1)
    if not exp_str.isdigit() or int(exp_str) < time.time():
        return False
    return hmac.compare_digest(sig, _sign(f"admin:{exp_str}"))


def is_admin(request: Request) -> bool:
    return verify_token(request.cookies.get("neon_sess"))


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=401, detail={
            "ok": False, "code": "NO_AUTH", "msg_fa": "ابتدا وارد شوید"})


def client_ip(request: Request) -> str:
    return (request.headers.get("cf-connecting-ip")
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "?"))


def locked(ip: str) -> bool:
    now = time.time()
    return any(now < a + 900 for a in _attempts.get(ip, []) if a > now - 300)


def record_fail(ip: str) -> None:
    now = time.time()
    lst = [a for a in _attempts.get(ip, []) if now - a < 300]
    lst.append(now)
    _attempts[ip] = lst


def reset_fails(ip: str) -> None:
    _attempts.pop(ip, None)
