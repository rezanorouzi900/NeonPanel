# app/tunnel.py
# Goal: run cloudflared (token/quick), parse quick URL, report status (APPENDIX A.11).
# Author: OpenCode
from __future__ import annotations

import os
import re
import subprocess
import threading

from .config import settings
from .domain import remember_tunnel_url

QUICK_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
TOKEN_SCRUB = "***"


def scrub(line: str) -> str:
    """Replace any token-looking value before logging."""
    if settings.cf_token:
        line = line.replace(settings.cf_token, TOKEN_SCRUB)
    return line


def parse_quick_url(log_line: str) -> str | None:
    m = QUICK_RE.search(log_line)
    return m.group(0) if m else None


def start_quick(port: int) -> subprocess.Popen:
    """Start a quick tunnel and capture its URL from stdout."""
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    threading.Thread(target=_read_quick_output, args=(proc,), daemon=True).start()
    return proc


def _read_quick_output(proc: subprocess.Popen) -> None:
    for line in proc.stdout:  # type: ignore[union-attr]
        clean = scrub(line)
        url = parse_quick_url(clean)
        if url:
            remember_tunnel_url(url)


def start_token(token: str) -> subprocess.Popen:
    return subprocess.Popen(
        ["cloudflared", "tunnel", "--no-autoupdate", "run", "--token", token],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def status() -> dict:
    mode = settings.cf_mode if settings.cf_mode in ("off", "token", "quick") else "off"
    cached = os.environ.get("_QUICK_URL", "")
    return {
        "mode": mode,
        "url": cached or None,
        "up": mode != "off",
    }
