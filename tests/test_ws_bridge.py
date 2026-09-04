# tests/test_ws_bridge.py — v2: path→port routing, WS proxy, HTTP deny.
# Author: OpenCode
import asyncio

import pytest

from app.ws_bridge import WSBridge


class FakeApp:
    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True


def _ws_scope(path):
    return {"type": "websocket", "path": path, "headers": [], "query_string": b""}


def _http_scope(path):
    return {"type": "http", "path": path, "method": "GET", "headers": [], "query_string": b""}


async def _noop_receive():
    return {"type": "websocket.disconnect", "code": 1000}


async def _noop_send(msg):
    pass


def test_bridge_routes_path_to_proto_port():
    from app.xray_config import XRAY_WS_PORTS

    app = FakeApp()
    br = WSBridge(app)
    br.set_paths({"vless": "/vless-x12345", "vmess": "/vmess-y67890", "trojan": "/trojan-z11111"})
    assert br.path_ports["/vless-x12345"] == XRAY_WS_PORTS["vless"]
    assert br.path_ports["/vmess-y67890"] == XRAY_WS_PORTS["vmess"]
    assert br.path_ports["/trojan-z11111"] == XRAY_WS_PORTS["trojan"]
    assert "/api/health" not in br.path_ports


@pytest.mark.asyncio
async def test_http_on_ws_path_gets_400():
    """plain HTTP on a WS path → 400 (no fingerprint), never reaches the panel"""
    app = FakeApp()
    br = WSBridge(app)
    br.set_paths({"vless": "/vless-x"})

    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    await br(_http_scope("/vless-x"), receive, send)
    assert app.called is False
    assert sent[0]["status"] == 400


@pytest.mark.asyncio
async def test_other_paths_fall_through_to_panel():
    app = FakeApp()
    br = WSBridge(app)
    br.set_paths({"vless": "/vless-x"})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        pass

    await br(_http_scope("/api/health"), receive, send)
    assert app.called is True


@pytest.mark.asyncio
async def test_ws_scope_on_other_path_falls_through():
    app = FakeApp()
    br = WSBridge(app)
    br.set_paths({"vless": "/vless-x"})

    await br(_ws_scope("/other"), _noop_receive, _noop_send)
    assert app.called is True


@pytest.mark.asyncio
async def test_ws_on_bridge_path_connects_or_closes_cleanly():
    """WS on a known path: upstream absent → close frame, panel untouched."""
    app = FakeApp()
    br = WSBridge(app)
    br.set_paths({"vless": "/vless-x"})

    sent = []

    async def receive():
        await asyncio.sleep(0)
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(msg):
        sent.append(msg)

    await br(_ws_scope("/vless-x"), receive, sent.append if False else send)
    assert app.called is False
    kinds = [m["type"] for m in sent]
    assert any(k in ("websocket.accept", "websocket.close") for k in kinds)
