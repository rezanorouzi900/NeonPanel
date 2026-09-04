# app/domain.py
# Goal: auto-detect the public domain the panel is served on (6-branch priority).
# Author: OpenCode
from __future__ import annotations

import os
import re
import time

from fastapi import Request

HOST_RE = re.compile(r"^[a-zA-Z0-9.-]+(:[0-9]+)?$")
QUICK_TUNNEL_RE = re.compile(r"https://[a-z-]+\.trycloudflare\.com")

_cache: dict[str, object] = {"value": None, "at": 0.0, "source": ""}


def sanitize_host(h: str) -> str | None:
    """Return a safe lowercase host or None if invalid/too long."""
    if not h or len(h) > 253:
        return None
    h = h.strip().lower()
    return h if HOST_RE.match(h) else None


def detect_domain(request: Request | None = None) -> str:
    """Detect current public domain using the 6-branch priority order."""
    # 1) manual override via env
    if os.getenv("PUBLIC_DOMAIN"):
        return os.environ["PUBLIC_DOMAIN"].strip()
    # 2) & 3) request headers
    if request is not None:
        fwd = request.headers.get("x-forwarded-host")
        if fwd:
            clean = sanitize_host(fwd.split(",")[0])
            if clean:
                return clean
        host = sanitize_host(request.headers.get("host", ""))
        if host:
            return host
    # 4) Railway
    if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        return os.environ["RAILWAY_PUBLIC_DOMAIN"].strip()
    # 5) cloudflared quick-tunnel cache
    if time.time() - _cache["at"] < 300 and _cache["value"]:
        return _cache["value"]
    # 6) fallback
    port = os.getenv("PORT", "8080")
    return f"localhost:{port}"


def remember_tunnel_url(url: str) -> None:
    """Cache a cloudflared quick-tunnel URL for domain detection."""
    _cache["value"] = url
    _cache["at"] = time.time()


def domain_source() -> str:
    """Return which branch produced the last detection (for the UI badge)."""
    if os.getenv("PUBLIC_DOMAIN"):
        return "env:PUBLIC_DOMAIN"
    if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        return "env:RAILWAY_PUBLIC_DOMAIN"
    if _cache["at"] > 0:
        return "tunnel:quick"
    return "header:Host"


def split_domain_port(domain: str) -> tuple[str, str | None]:
    """Split 'host:port' into parts; port None when absent."""
    if ":" in domain:
        host, _, port = domain.partition(":")
        return host, port
    return domain, None


def is_local(domain: str) -> bool:
    """True when the domain is a localhost fallback (links must be disabled)."""
    return domain.startswith("localhost") or domain.startswith("127.")
