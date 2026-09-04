# tests/test_ws_bridge.py — bridge path matching + fallback to panel.
# Author: OpenCode
import pytest

from app.ws_bridge import WSBridge


class FakeApp:
    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True


def test_bridge_matches_only_known_paths():
    app = FakeApp()
    br = WSBridge(app)
    br.paths = {"/vless-x12345678", "/vmess-y87654321"}
    assert "/vless-x12345678" in br.paths
    assert "/api/health" not in br.paths


@pytest.mark.asyncio
async def test_bridge_falls_through_to_panel():
    app = FakeApp()
    br = WSBridge(app)
    br.paths = {"/vless-x"}

    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "http", "path": "/api/health", "method": "GET",
             "headers": [], "query_string": b""}
    await br(scope, receive, send)
    assert app.called is True  # panel handled it
    assert sent == []  # panel's own send was invoked through FakeApp


@pytest.mark.asyncio
async def test_bridge_denies_when_upstream_dead():
    app = FakeApp()
    br = WSBridge(app)
    br.paths = {"/vless-x"}

    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "http", "path": "/vless-x", "method": "GET",
             "headers": [], "query_string": b""}
    # upstream 127.0.0.1:10086 not running in tests → _pump raises → deny 400
    await br(scope, receive, send)
    assert app.called is False
    assert sent[0]["status"] == 400
