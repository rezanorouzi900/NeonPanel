# app/stats.py
# Goal: poll Xray Stats gRPC API every 60s — hand-rolled protobuf (no codegen needed).
# Author: OpenCode
from __future__ import annotations

import asyncio
import logging
import struct
from datetime import datetime, timezone

from sqlmodel import Session, select

from .db import get_engine
from .models import TrafficLog, User
from .xray_config import XRAY_API_PORT

log = logging.getLogger("stats")

# Xray StatsService.QueryStats proto (xray.app.stats.command):
#   QueryStatsRequest { repeated string pattern = 1; bool reset = 2; }
#   QueryStatsResponse { repeated Stat stat = 1; }
#   Stat { string name = 1; int64 value = 2; }
_last_seen: dict[str, int] = {}
_warned = False


def _pb_varint(n: int) -> bytes:
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _pb_tag(field: int, wire: int) -> bytes:
    return _pb_varint((field << 3) | wire)


def _pb_str(field: int, s: str) -> bytes:
    raw = s.encode()
    return _pb_tag(field, 2) + _pb_varint(len(raw)) + raw


def _pb_bool(field: int, v: bool) -> bytes:
    return _pb_tag(field, 0) + (b"\x01" if v else b"\x00")


def encode_query(pattern: str = "", reset: bool = False) -> bytes:
    """Serialize QueryStatsRequest."""
    out = b""
    if pattern:
        out += _pb_str(1, pattern)
    out += _pb_bool(2, reset)
    return out


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    shift = 0
    val = 0
    while True:
        b = data[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            return val, pos
        shift += 7


def decode_stats(data: bytes) -> list[tuple[str, int]]:
    """Parse QueryStatsResponse → [(name, value), ...]."""
    stats: list[tuple[str, int]] = []
    pos = 0
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        field, wire = tag >> 3, tag & 7
        if field == 1 and wire == 2:
            ln, pos = _read_varint(data, pos)
            stat = data[pos:pos + ln]
            pos += ln
            name, value = "", 0
            sp = 0
            while sp < len(stat):
                st, sp = _read_varint(stat, sp)
                sf, sw = st >> 3, st & 7
                if sf == 1 and sw == 2:
                    l2, sp = _read_varint(stat, sp)
                    name = stat[sp:sp + l2].decode(errors="replace")
                    sp += l2
                elif sf == 2 and sw == 0:
                    value, sp = _read_varint(stat, sp)
            if name:
                stats.append((name, value))
        else:
            if wire == 0:
                _, pos = _read_varint(data, pos)
            elif wire == 2:
                l3, pos = _read_varint(data, pos)
                pos += l3
    return stats


async def query_xray_stats() -> dict[str, dict[str, int]]:
    """One gRPC call → {email: {up: bytes, down: bytes}} (cumulative)."""
    reader, writer = await asyncio.open_connection("127.0.0.1", XRAY_API_PORT)

    body = encode_query("user>>>", reset=False)
    msg = b"\x00" + struct.pack(">I", len(body)) + body

    path = b"/xray.app.stats.command.StatsService/QueryStats"
    writer.write(
        b"POST " + path + b" HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\nContent-Type: application/grpc\r\n"
        b"te: trailers\r\ngrpc-encoding: identity\r\n"
        b"Content-Length: " + str(len(msg)).encode() + b"\r\n\r\n" + msg
    )
    await writer.drain()

    # read headers
    headers = {}
    while True:
        line = await asyncio.wait_for(reader.readline(), 10)
        if line in (b"\r\n", b"\n", b""):
            break
        if b":" in line:
            k, _, v = line.partition(b":")
            headers[k.strip().lower()] = v.strip()

    length = int(headers.get(b"content-length", b"0") or 0)
    payload = b""
    while len(payload) < length:
        chunk = await asyncio.wait_for(reader.read(length - len(payload)), 10)
        if not chunk:
            break
        payload += chunk
    writer.close()

    # grpc frame: 1 byte compressed + 4-byte length + body
    if len(payload) >= 5:
        body_len = struct.unpack(">I", payload[1:5])[0]
        counters = decode_stats(payload[5:5 + body_len])
        out: dict[str, dict[str, int]] = {}
        for name, value in counters:
            parts = name.split(">>>")
            if len(parts) >= 3 and parts[0] == "user":
                email = parts[1]
                slot = out.setdefault(email, {"up": 0, "down": 0})
                if "uplink" in name:
                    slot["up"] += value
                elif "downlink" in name:
                    slot["down"] += value
        return out
    return {}


def apply_delta(session: Session, email: str, delta: int) -> None:
    user = session.exec(select(User).where(User.name == email)).first()
    if not user:
        return
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = session.exec(
        select(TrafficLog).where(TrafficLog.user_id == user.id, TrafficLog.day == day)
    ).first()
    if row:
        row.down_bytes += delta
    else:
        row = TrafficLog(user_id=user.id, day=day, up_bytes=0, down_bytes=delta)
    session.add(row)
    user.used_bytes += delta
    session.add(user)
    session.commit()


async def tick() -> None:
    """Poll cumulative counters; persist deltas. Xray restart resets → prev=0."""
    global _warned
    try:
        counters = await query_xray_stats()
        _warned = False
        with Session(get_engine()) as session:
            for email, c in counters.items():
                total = c["up"] + c["down"]
                prev = _last_seen.get(email, 0)
                if total < prev:
                    prev = 0
                _last_seen[email] = total
                if total > prev:
                    apply_delta(session, email, total - prev)
    except Exception as e:  # noqa: BLE001 — loop must never crash the panel
        if not _warned:
            log.warning("stats tick failed (will retry): %s", e)
            _warned = True


async def loop() -> None:
    while True:
        await tick()
        await asyncio.sleep(60)
