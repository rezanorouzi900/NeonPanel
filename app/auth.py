# app/auth.py
# Goal: JWT + bcrypt + login rate-limit + current_admin dependency (APPENDIX A.5).
# Author: OpenCode
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import settings

ALGO = "HS256"
ACCESS_MIN = 60
REFRESH_DAYS = 7
LOGIN_WINDOW = 300  # seconds
LOGIN_MAX = 5
LOCK_SECONDS = 900  # 15 minutes

_bearer = HTTPBearer(auto_error=False)


def _secret() -> str:
    return settings.jwt_secret or "dev-only-secret"


def create_access(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_MIN)
    return jwt.encode({"sub": username, "exp": exp, "type": "access"}, _secret(), ALGO)


def create_refresh(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_DAYS)
    return jwt.encode({"sub": username, "exp": exp, "type": "refresh"}, _secret(), ALGO)


def decode(token: str, expected: str = "access") -> str | None:
    """Return username if the token is valid, else None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGO])
        if payload.get("type") != expected:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def hash_password(p: str) -> str:
    from .db import pwd

    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    from .db import pwd

    try:
        return pwd.verify(p, h)
    except Exception:
        return False


class LoginGuard:
    """In-memory per-IP login rate limiter: max 5 tries / 5 min then 15-min lock."""

    def __init__(self) -> None:
        self.attempts: dict[str, list[float]] = {}
        self.locked: dict[str, float] = {}

    def _prune(self, ip: str, now: float) -> None:
        self.attempts[ip] = [t for t in self.attempts.get(ip, []) if now - t < LOGIN_WINDOW]

    def is_locked(self, ip: str) -> bool:
        now = time.time()
        until = self.locked.get(ip, 0)
        if now < until:
            return True
        self.locked.pop(ip, None)
        return False

    def record(self, ip: str) -> None:
        now = time.time()
        self._prune(ip, now)
        self.attempts.setdefault(ip, []).append(now)
        if len(self.attempts[ip]) >= LOGIN_MAX:
            self.locked[ip] = now + LOCK_SECONDS
            self.attempts[ip] = []

    def reset(self, ip: str) -> None:
        self.attempts.pop(ip, None)
        self.locked.pop(ip, None)


guard = LoginGuard()


def client_ip(request: Request) -> str:
    """Real client IP, preferring CF-Connecting-IP when behind a tunnel."""
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None:
        raise HTTPException(status_code=401, detail={"ok": False, "code": "NO_AUTH", "msg_fa": "ابتدا وارد شوید"})
    username = decode(creds.credentials)
    if not username:
        raise HTTPException(status_code=401, detail={"ok": False, "code": "NO_AUTH", "msg_fa": "توکن نامعتبر است"})
    return username
