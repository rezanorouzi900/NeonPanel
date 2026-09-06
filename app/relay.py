# app/relay.py
# The heart: ASGI app that speaks VLESS over WebSocket (native in-process relay).
# Client -> uvicorn(TLS edge) -> this WS handler -> parse VLESS -> TCP connect -> pipe.
# Author: OpenCode
from __future__ import annotations

import asyncio
import base64
import logging
import struct
import time

import httpx
from starlette.types import Scope

from . import store
from .vless import RESP_OK, parse_header

log = logging.getLogger("relay")

WS_PATH = "/vl"
UDP_DNS_PORT = 53  # UDP only for DNS, answered via DoH upstream
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


def _subprotocol(scope) -> str:
    """First offered client subprotocol (used for ed=2560 early data)."""
    for k, v in scope.get("headers", []):
        if k.decode().lower() == "sec-websocket-protocol":
            return v.decode().split(",")[0].strip()
    return ""


def _uses_early_data(scope) -> bool:
    return b"ed=" in (scope.get("query_string") or b"")


async def handle_vless_ws(scope: Scope, receive, send) -> None:
    """One VLESS-over-WS connection: parse header, connect, pump both ways."""
    ip = _client_ip(scope)
    sub = _subprotocol(scope)
    await send({"type": "websocket.accept", "subprotocol": sub or None})

# ed=2560: client embedded the VLESS header (base64) in the subprotocol.
    # It then sends NO frame until it sees the 101 — so decode BEFORE reading.
    initial = b""
    has_ed = bool(sub) and _uses_early_data(scope)
    if has_ed:
        # clients use base64url without padding (xray `ed=2560` style); accept
        # plain base64 too — try urlsafe first, fall back to standard.
        try:
            ed = base64.urlsafe_b64decode(sub + "=" * (-len(sub) % 4))
        except Exception:
            try:
                ed = base64.b64decode(sub)
            except Exception:
                ed = b""
        if len(ed) >= 24:
            initial = ed
    try:
        if not initial:
            first = await asyncio.wait_for(_first_frame(receive), timeout=15)
            initial = first or b""
        else:
            # a frame may still carry the rest (header split across both)
            try:
                extra = await asyncio.wait_for(_first_frame(receive), timeout=0.05)
                if extra:
                    initial = initial + extra
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        if not initial:
            await send({"type": "websocket.close", "code": 1000})
            return

        valid = {c["uuid"] for c in store.list_configs() if c.get("enabled")}
        try:
            uid, addr, port, hlen = parse_header(initial, valid)
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

        payload = initial[hlen:]
        used = 0
        try:
            if port == UDP_DNS_PORT and initial[18] == 0x02:  # UDP DNS request
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


async def handle_tcp_stream(reader, writer) -> None:
    """VLESS over plain TCP — for a raw port when exposed (works like WS but
    without the WebSocket framing). Reads the header from the stream directly."""
    ip = (writer.get_extra_info("peername") or ("?", 0))[0]
    try:
        head = await asyncio.wait_for(reader.read(4096), timeout=15)
        if not head:
            return
        valid = {c["uuid"] for c in store.list_configs() if c.get("enabled")}
        try:
            uid, addr, port, hlen = parse_header(head, valid)
        except ValueError as e:
            log.info("tcp reject (%s) ip=%s", e, ip)
            return
        cfg = store.get_by_uuid(uid)
        ok, reason = store.usable(cfg)
        if not ok or not store.live_start(uid, ip):
            log.info("tcp %s blocked: %s", uid[:8], reason)
            store.live_end(uid, ip)
            return
        payload = head[hlen:]
        used = 0
        try:
            if port == UDP_DNS_PORT and head[18] == 0x02:
                used = await _dns_tcp(writer, payload)
            else:
                used = await _tcp_pipe_raw(writer, reader, payload, addr, port, uid)
        finally:
            if used:
                store.add_usage(str(cfg["id"]), used)
            store.live_end(uid, ip)
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _dns_tcp(writer, payload: bytes) -> int:
    """UDP-DNS(53) over raw TCP → DoH; framed [len(2B)][dns]."""
    try:
        async with httpx.AsyncClient(timeout=6) as cx:
            r = await cx.post(DNS_UPSTREAM, content=payload,
                              headers={"content-type": "application/dns-message"})
        ans = r.content
        writer.write(struct.pack(">H", len(ans)) + ans)
        await writer.drain()
        return len(payload) + len(ans)
    except Exception:
        return len(payload)


async def _tcp_pipe_raw(writer, reader, first_payload: bytes, addr: str,
                        port: int, uid: str) -> int:
    """Connect to destination and pipe over raw TCP (no WS framing)."""
    try:
        dst_r, dst_w = await asyncio.wait_for(
            asyncio.open_connection(addr, port), timeout=10)
    except (OSError, asyncio.TimeoutError):
        return 0
    dst_w.write(first_payload)
    writer.write(RESP_OK)
    await writer.drain()
    used = len(first_payload or b"")
    cfg = store.get_by_uuid(uid) or {}
    th = _Throttle(cfg.get("speed_mbps", 0))

    async def c2d():
        nonlocal used
        try:
            while True:
                chunk = await reader.read(CHUNK)
                if not chunk:
                    return
                used += len(chunk)
                await th.wait(len(chunk))
                dst_w.write(chunk)
                await dst_w.drain()
        except asyncio.CancelledError:
            raise

    async def d2c():
        nonlocal used
        while True:
            chunk = await dst_r.read(CHUNK)
            if not chunk:
                return
            used += len(chunk)
            writer.write(chunk)
            await writer.drain()

    t1 = asyncio.create_task(c2d())
    t2 = asyncio.create_task(d2c())
    try:
        await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in (t1, t2):
            if not t.done():
                t.cancel()
        try:
            dst_w.close()
        except Exception:
            pass
    return used


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
    """UDP DNS(53) → DoH upstream; reply framed [len(2B)][dns]."""
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


