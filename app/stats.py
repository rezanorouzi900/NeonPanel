# app/stats.py
# Goal: poll Xray Stats API every 60s, aggregate per-user daily traffic (APPENDIX A.15).
# Author: OpenCode
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from .db import get_engine
from .models import TrafficLog, User

log = logging.getLogger("stats")

# email -> last cumulative bytes seen (Xray stats are cumulative)
_last_seen: dict[str, int] = {}
_warned = False


def apply_delta(session: Session, email: str, delta_up: int, delta_down: int) -> None:
    """Upsert today's traffic row and bump user.used_bytes."""
    user = session.exec(select(User).where(User.name == email)).first()
    if not user:
        return
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = session.exec(
        select(TrafficLog).where(TrafficLog.user_id == user.id, TrafficLog.day == day)
    ).first()
    if row:
        row.up_bytes += delta_up
        row.down_bytes += delta_down
    else:
        row = TrafficLog(user_id=user.id, day=day, up_bytes=delta_up, down_bytes=delta_down)
    session.add(row)
    user.used_bytes += delta_up + delta_down
    session.add(user)
    session.commit()


async def query_xray_stats() -> list[tuple[str, int, int]]:
    """Query Xray gRPC stats service (127.0.0.1:10085) for 'user>>>' counters.

    Requires grpcio + generated xray proto; returns [] when unavailable so the
    loop keeps running and retries next tick.
    """
    import grpc  # type: ignore

    from app.xray_grpc import StatsQuery, StatsServiceStub  # type: ignore

    channel = grpc.aio.insecure_channel("127.0.0.1:10085")
    try:
        stub = StatsServiceStub(channel)
        resp = await stub.QueryStats(StatsQuery(pattern="user>>>", reset=False))
        out: list[tuple[str, int, int]] = []
        for c in resp.stat:
            if ">>>" not in c.name:
                continue
            parts = c.name.split(">>>")
            if len(parts) >= 3 and parts[0] == "user":
                email = parts[1]
                is_up = parts[2] == "traffic>>>uplink"
                out.append((email, c.value if is_up else 0, 0 if is_up else c.value))
        return out
    finally:
        await channel.close()


async def tick() -> None:
    """One polling round; failure only warns — data survives since stats are cumulative."""
    global _warned
    try:
        counters = await query_xray_stats()
        _warned = False
        with Session(get_engine()) as session:
            merged: dict[str, list[int]] = {}
            for email, up, down in counters:
                m = merged.setdefault(email, [0, 0])
                m[0] += up
                m[1] += down
            for email, (up, down) in merged.items():
                total = up + down
                prev = _last_seen.get(email, 0)
                if total < prev:
                    prev = 0  # xray restarted → counter reset
                _last_seen[email] = total
                if total > prev:
                    apply_delta(session, email, 0, total - prev)
    except ImportError:
        if not _warned:
            log.warning("grpcio/xray proto not installed — traffic accounting disabled")
            _warned = True
    except Exception as e:  # noqa: BLE001 — loop must never crash the panel
        if not _warned:
            log.warning("stats tick failed (will retry): %s", e)
            _warned = True


async def loop() -> None:
    while True:
        await tick()
        await asyncio.sleep(60)
