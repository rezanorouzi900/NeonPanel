# app/security.py
# Goal: security headers, CORS, rate limiting, secret scrubbing (PART 1 §4.7, A.14).
# Author: OpenCode
from __future__ import annotations

import re
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings

SEC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "script-src 'self' https://cdn.jsdelivr.net; font-src 'self' data: "
        "https://cdn.jsdelivr.net https://fonts.gstatic.com"
    ),
}

SECRET_PATTERNS = [re.compile(r"ghp_[A-Za-z0-9]{20,}"), re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ")]


def scrub(value: str) -> str:
    """Mask token/secret-looking values before logging."""
    for pat in SECRET_PATTERNS:
        value = pat.sub("***", value)
    if settings.cf_token:
        value = value.replace(settings.cf_token, "***")
    return value


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        for k, v in SEC_HEADERS.items():
            resp.headers.setdefault(k, v)
        return resp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Generic limiter: limit requests per window per IP for matching paths."""

    def __init__(self, app, prefix: str, limit: int, window: int, code: str):
        super().__init__(app)
        self.prefix = prefix
        self.limit = limit
        self.window = window
        self.code = code
        self.hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(self.prefix):
            ip = request.headers.get("cf-connecting-ip") or (
                request.client.host if request.client else "?"
            )
            now = time.time()
            q = self.hits[ip]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return JSONResponse(
                    status_code=429,
                    content={"ok": False, "code": self.code, "msg_fa": "درخواست‌های زیاد — کمی صبر کن"},
                )
            q.append(now)
        return await call_next(request)


def build_rate_limiters() -> list:
    """Sub: 30/1min → RATE. Login lock is handled by auth.LoginGuard (success not counted)."""
    return [
        RateLimitMiddleware(None, "/sub/", 30, 60, "RATE"),
    ]
