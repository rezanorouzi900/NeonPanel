# tests/test_e2e_relay.py — real VLESS handshake through the pure-python relay.
# Author: OpenCode
import asyncio

import pytest

from app import store
from app.bridge import Bridge
from app.vless import RESP_OK, build_header


class _FakePanel:
    async def __call__(self, scope, receive, send):
        raise AssertionError("panel must not see /vl traffic")


async def _ws_client_flow(scope_app, path, ip_hdrs=None):
    """Simulate the edge websocket client; returns (accepted_frames, close_code)."""
    sent = []

    async def send(msg):
        sent.append(msg)

    header_done = asyncio.Event()

    async def receive():
        # first frame: VLESS header (client → server)
        if not header_done.is_set():
            header_done.set()
            return {"type": "websocket.receive",
                    "bytes": build_header(store.list_configs()[0]["uuid"], "127.0.0.1", ECHO_PORT)}
        await asyncio.sleep(30)
        return {"type": "websocket.disconnect", "code": 1000}

    scope = {"type": "websocket", "path": path, "headers": ip_hdrs or [],
             "client": ("9.9.9.9", 1234)}
    await scope_app(scope, receive, send)
    return sent


ECHO_PORT = 19876


async def _echo_server():
    async def handler(reader, writer):
        try:
            while True:
                d = await reader.read(65536)
                if not d:
                    break
                writer.write(d.upper())
                await writer.drain()
        finally:
            writer.close()

    return await asyncio.start_server(handler, "127.0.0.1", ECHO_PORT)


@pytest.mark.asyncio
async def test_full_vless_relay_roundtrip(tmp_path, monkeypatch):
    """Real flow: VLESS header → relay connects to echo → data uppercased back."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store._state = {"configs": {}, "groups": {}, "admin_hash": "x", "seq": 1}
    cfg, code = store.create_config("e2e-user")
    assert code == ""
    store.save = lambda: None  # no disk in test

    srv = await _echo_server()
    bridge = Bridge(_FakePanel())
    try:
        task = asyncio.create_task(_ws_client_flow(bridge, "/vl"))
        # wait for accept + response header + echo data
        deadline = asyncio.get_event_loop().time() + 5
        got_resp_ok = got_payload = False
        while asyncio.get_event_loop().time() < deadline and not (got_resp_ok and got_payload):
            # peek is impossible on a task; instead poll by awaiting briefly
            await asyncio.sleep(0.1)
            # we cannot read `sent` from outside; run flow inline instead
            break
        task.cancel()
        # simpler: run the flow synchronously with an echo that replies instantly
        sent = await _flow_inline(bridge, cfg)
        frames = [s for s in sent if s["type"] == "websocket.send"]
        payloads = [s.get("bytes") for s in frames if s.get("bytes")]
        assert RESP_OK in payloads, f"missing VLESS OK header: {payloads}"
        assert b"HELLO" in payloads or b"hello".upper() in payloads, f"echo missing: {payloads}"
    finally:
        srv.close()
        await srv.wait_closed()


async def _flow_inline(bridge, cfg):
    """Full client flow with immediate payload after header."""
    sent = []
    step = {"i": 0}

    async def receive():
        i = step["i"]
        step["i"] += 1
        if i == 0:
            return {"type": "websocket.receive",
                    "bytes": build_header(cfg["uuid"], "127.0.0.1", ECHO_PORT) + b"hello"}
        await asyncio.sleep(30)
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "websocket", "path": "/vl", "headers": [], "client": ("9.9.9.9", 1)}
    done = asyncio.Event()

    async def runner():
        try:
            await bridge(scope, receive, send)
        finally:
            done.set()

    t = asyncio.create_task(runner())
    # echo reply should arrive within ~3s
    for _ in range(40):
        if any(s.get("bytes") == b"HELLO" for s in sent):
            break
        await asyncio.sleep(0.1)
    # graceful close
    for s in sent:
        if s["type"] == "websocket.close":
            t.cancel()
            break
    else:
        t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    return sent


@pytest.mark.asyncio
async def test_relay_rejects_bad_uuid(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store._state = {"configs": {}, "groups": {}, "admin_hash": "x", "seq": 1}
    cfg, _ = store.create_config("some-user")
    store.save = lambda: None

    bridge = Bridge(_FakePanel())
    sent = []

    async def receive():
        return {"type": "websocket.receive",
                "bytes": build_header("99999999-9999-9999-9999-999999999999", "127.0.0.1", 80)}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "websocket", "path": "/vl", "headers": [], "client": ("9.9.9.9", 1)}
    await bridge(scope, receive, send)
    kinds = [s["type"] for s in sent]
    assert "websocket.accept" in kinds
    assert "websocket.close" in kinds  # rejected → closed, no data frames
    assert all(s["type"] != "websocket.send" for s in sent)


@pytest.mark.asyncio
async def test_reject_disabled_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store._state = {"configs": {}, "groups": {}, "admin_hash": "x", "seq": 1}
    cfg, _ = store.create_config("off-user")
    cfg["enabled"] = False
    store.save = lambda: None

    bridge = Bridge(_FakePanel())
    sent = []

    async def receive():
        return {"type": "websocket.receive",
                "bytes": build_header(cfg["uuid"], "127.0.0.1", ECHO_PORT) + b"x"}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "websocket", "path": "/vl", "headers": [], "client": ("8.8.8.8", 1)}
    await bridge(scope, receive, send)
    assert all(s["type"] != "websocket.send" for s in sent)
    assert "websocket.close" in [s["type"] for s in sent]
