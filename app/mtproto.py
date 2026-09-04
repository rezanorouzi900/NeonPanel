# app/mtproto.py
# Goal: Telegram MTProto proxy — random secret, dd/ee links with the REAL public host.
# Author: OpenCode
from __future__ import annotations

import asyncio
import os
import secrets

from .config import settings


def ensure_secret(data_dir: str) -> str:
    """Read or create the 32-hex secret in secret.txt with mode 600."""
    path = os.path.join(data_dir, "secret.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            s = f.read().strip()
        if len(s) == 64 and all(c in "0123456789abcdef" for c in s):
            return s
    s = secrets.token_hex(16)  # 32 hex chars
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(s)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return s


def build_links(host: str, port: int, secret: str) -> dict:
    """Simple dd link + cloaked ee link (fakes TLS traffic)."""
    simple = f"https://t.me/proxy?server={host}&port={port}&secret=dd{secret}"
    cloaked = f"https://t.me/proxy?server={host}&port={port}&secret=ee{secret}www.google.com"
    return {"simple": simple, "cloaked": cloaked}


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Read the 64-byte MTProto handshake and log it; close politely."""
    try:
        data = await asyncio.wait_for(reader.readexactly(64), timeout=15)
        peer = writer.get_extra_info("peername")
        if data:
            print(f"[mtproto] handshake {len(data)} bytes from {peer}")
    except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionResetError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def serve(port: int) -> None:
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    print(f"[mtproto] listening on 0.0.0.0:{port}")
    async with server:
        await server.serve_forever()


def suggested_host() -> str:
    """Real public host — never localhost when a public domain is known."""
    from .domain import detect_domain

    d = detect_domain(None)
    host = d.split(":")[0]
    if host in ("localhost", "127.0.0.1"):
        return os.getenv("RAILWAY_TCP_PROXY_DOMAIN", host)
    return host


if __name__ == "__main__":
    secret = ensure_secret(settings.data_dir)
    host = suggested_host()
    links = build_links(host, settings.mt_port, secret)
    print("[mtproto] links:", links)
    asyncio.run(serve(settings.mt_port))
