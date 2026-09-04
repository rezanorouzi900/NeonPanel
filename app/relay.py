# app/relay.py
# The heart: ASGI app that speaks VLESS over WebSocket (px-panel method).
# Client -> uvicorn(TLS edge) -> this WS handler -> parse VLESS -> TCP connect -> pipe.
# Author: OpenCode
from __future__ import annotations

import asyncio
import logging
import struct
import time

import httpx
from starlette.types import Scope

from . import store
from .vless import RESP_OK, parse_header

log = logging.getLogger("relay")

WS_PATH = "/vl"
UDP_DNS_PORT = 53  # UDP only for DNS (DoH upstream) — like px-panel
DNS_UPSTREAM = "https://cloudflare-dns.com/dns-query"
CHUNK = 65536
REFILL = 0.2  # token-bucket refill interval (s)


class _Throttle:
    """Token-bucket: rate in bytes/s; zero-copy pass-through when disabled."""

    __slots__ = ("rate", "tokens", "last")

    def __init__(self, mbps: int):
        self.rate = mbps * 125_000 if mbps else 0
        self.tokens = float(self.rate * REFILL) if self.rate else 0.0
        self.last = time.monotonic()

    async def wait(self, n: int) -> None:
        if not self.rate:
            return
        while True:
            now = time.monotonic()
            self.tokens = min(self.rate * REFILL, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= n:
                self.tokens -= n
                return
            await asyncio.sleep(max(0.005, min((n - self.tokens) / self.rate, REFILL)))


def _client_ip(scope) -> str:
    hdrs = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    return (hdrs.get("cf-connecting-ip")
            or hdrs.get("x-forwarded-for", "").split(",")[0].strip()
            or (scope.get("client") or ["?"])[0])


async def handle_vless_ws(scope: Scope, receive, send) -> None:
    """One VLESS-over-WS connection: parse header, connect, pump both ways."""
    ip = _client_ip(scope)
    await send({"type": "websocket.accept", "subprotocol": None})
    try:
        first = await _first_frame(receive)
        if not first:
            await send({"type": "websocket.close", "code": 1000})
            return

        valid = {c["uuid"] for c in store.list_configs() if c.get("enabled")}
        try:
            uid, addr, port, hlen = parse_header(first, valid)
        except ValueError as e:
            log.info("vless reject (%s) ip=%s", e, ip)
            await send({"type": "websocket.close", "code": 1000})
            return

        cfg = store.get_by_uuid(uid)
        ok, reason = store.usable(cfg)
        if not ok or not store.live_start(uid, ip):
            log.info("vless %s blocked: %s", uid[:8], reason)
            store.live_end(uid, ip)
            await send({"type": "websocket.close", "code": 1000})
            return

        payload = first[hlen:]
        used = 0
        try:
            if port == UDP_DNS_PORT and first[18] == 0x02:  # UDP DNS request
                used = await _dns_doh(send, payload)
            else:
                used = await _tcp_pipe(send, receive, payload, addr, port, uid)
        finally:
            if used:
                store.add_usage(str(cfg["id"]), used)
            store.live_end(uid, ip)
            try:
                await send({"type": "websocket.close", "code": 1000})
            except Exception:
                pass
    except Exception:  # noqa: BLE001 — relay must never crash the server
        log.exception("relay error")
        try:
            await send({"type": "websocket.close", "code": 1011})
        except Exception:
            pass


async def _first_frame(receive) -> bytes | None:
    """Read messages until the first data frame (skip pings/close)."""
    while True:
        msg = await receive()
        t = msg["type"]
        if t == "websocket.disconnect":
            return None
        if t == "websocket.receive":
            data = msg.get("bytes")
            if data is None:
                data = (msg.get("text") or "").encode()
            if data:
                return data


async def _tcp_pipe(send, receive, first_payload: bytes, addr: str,
                    port: int, uid: str) -> int:
    """Connect to destination; write first payload; pump bidirectionally."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(addr, port), timeout=10
        )
    except (OSError, asyncio.TimeoutError) as e:
        log.info("connect fail %s:%s (%s)", addr, port, type(e).__name__)
        return 0

    used = 0
    if first_payload:
        writer.write(first_payload)
        used += len(first_payload)
    await send({"type": "websocket.send", "bytes": RESP_OK})

    cfg = store.get_by_uuid(uid) or {}
    th_in = _Throttle(cfg.get("speed_mbps", 0))

    async def client_to_remote() -> None:
        nonlocal used
        while True:
            msg = await receive()
            if msg["type"] == "websocket.disconnect":
                return
            data = msg.get("bytes")
            if data is None:
                data = (msg.get("text") or "").encode()
            if not data:
                continue
            used += len(data)
            writer.write(data)
            await writer.drain()

    async def remote_to_client() -> None:
        nonlocal used
        while True:
            chunk = await reader.read(CHUNK)
            if not chunk:
                return
            used += len(chunk)
            await th_in.wait(len(chunk))
            await send({"type": "websocket.send", "bytes": chunk})

    t_up = asyncio.create_task(client_to_remote())
    t_down = asyncio.create_task(remote_to_client())
    try:
        await asyncio.wait([t_up, t_down], return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in (t_up, t_down):
            if not t.done():
                t.cancel()
        try:
            writer.close()
        except Exception:
            pass
    return used


async def _dns_doh(send, payload: bytes) -> int:
    """UDP DNS(53) → DoH upstream; reply framed [len(2B)][dns] (px-panel style)."""
    try:
        async with httpx.AsyncClient(timeout=6) as cx:
            r = await cx.post(DNS_UPSTREAM, content=payload,
                              headers={"content-type": "application/dns-message"})
        ans = r.content
        await send({"type": "websocket.send",
                    "bytes": struct.pack(">H", len(ans)) + ans})
        return len(payload) + len(ans)
    except Exception:
        return len(payload)
