# tests/test_e2e_ws.py — end-to-end: real xray binary + real WS through the bridge.
# Author: OpenCode
import asyncio
import os
import shutil
import socket
import subprocess

import pytest


def xray_binary() -> str | None:
    return os.getenv("XRAY_PATH_OVERRIDE") or shutil.which("xray")


requires_xray = pytest.mark.skipif(not xray_binary(), reason="xray binary not available")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@requires_xray
@pytest.mark.asyncio
async def test_xray_accepts_ws_on_configured_path(tmp_path):
    """Real xray: WS connect on the right path succeeds; wrong path is refused."""
    from datetime import datetime, timedelta

    from app import xray_config
    from app.config import Settings
    from app.models import User

    api_port = free_port()
    ws_ports = {p: free_port() for p in ("vless", "vmess", "trojan")}
    user = User(id=1, name="e2e", uuid="11111111-2222-3333-4444-555555555555",
                trojan_pass="tp", ss_pass="sp0123456789", sub_token="tok",
                expires_at=datetime.utcnow() + timedelta(days=1))
    paths = {"vless": "/vless-e2e12345", "vmess": "/vmess-e2e67890", "trojan": "/trojan-e2e54321"}
    s = Settings()
    s.reality_port = free_port()
    s.ss_port = free_port()
    cfg = xray_config.build_config([user], s, paths, api_port=api_port, ws_ports=ws_ports)
    ok, reason = xray_config.validate_config(cfg)
    assert ok, reason

    cfg_path = str(tmp_path / "x.json")
    xray_config.write_config(cfg, cfg_path)

    proc = subprocess.Popen(
        [xray_binary(), "run", "-c", cfg_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        await asyncio.sleep(1.5)
        assert proc.poll() is None, "xray died at startup"

        import websockets

        # right path → 101 upgrade succeeds
        async with websockets.connect(
            f"ws://127.0.0.1:{ws_ports['vless']}/vless-e2e12345", max_size=None,
            open_timeout=5, ping_interval=None,
        ) as ws:
            # connected means the 101 handshake completed — xray accepted the path
            await asyncio.wait_for(ws.send(b""), timeout=3)
        # wrong path → refused
        with pytest.raises(Exception):
            await asyncio.wait_for(
                websockets.connect(f"ws://127.0.0.1:{ws_ports['vless']}/wrong-path",
                                   open_timeout=3, ping_interval=None),
                timeout=4,
            )
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


@requires_xray
@pytest.mark.asyncio
async def test_full_bridge_to_xray(tmp_path):
    """Edge WS → WSBridge ASGI → real xray: connection is established & routed."""
    from datetime import datetime, timedelta

    from app import xray_config
    from app.config import Settings
    from app.models import User
    from app.ws_bridge import WSBridge

    api_port = free_port()
    ws_ports = {p: free_port() for p in ("vless", "vmess", "trojan")}
    user = User(id=1, name="e2e2", uuid="11111111-2222-3333-4444-555555555555",
                trojan_pass="tp", ss_pass="sp0123456789", sub_token="tok2",
                expires_at=datetime.utcnow() + timedelta(days=1))
    path = "/vless-bridge99"
    s = Settings()
    s.reality_port = free_port()
    s.ss_port = free_port()
    cfg = xray_config.build_config(
        [user], s,
        {"vless": path, "vmess": "/vmess-x1", "trojan": "/trojan-x1"},
        api_port=api_port, ws_ports=ws_ports,
    )
    cfg_path = str(tmp_path / "x2.json")
    xray_config.write_config(cfg, cfg_path)

    proc = subprocess.Popen(
        [xray_binary(), "run", "-c", cfg_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    class Panel:
        async def __call__(self, scope, receive, send):
            raise AssertionError("panel must not see bridged WS traffic")

    bridge = WSBridge(Panel())
    bridge.path_ports = {path: ws_ports["vless"]}  # direct route to the test xray

    accepted = []

    async def edge_receive():
        # simulate the edge client staying connected
        await asyncio.sleep(10)
        return {"type": "websocket.disconnect", "code": 1000}

    async def edge_send(msg):
        accepted.append(msg["type"])

    try:
        await asyncio.sleep(1.5)
        assert proc.poll() is None

        # run the bridge ASGI call as a task; the xray side must accept the WS
        bridge_task = asyncio.create_task(
            bridge({"type": "websocket", "path": path, "headers": [],
                    "query_string": b""},
                   edge_receive, edge_send)
        )
        await asyncio.sleep(1.5)
        assert "websocket.accept" in accepted, f"bridge did not accept: {accepted}"
        bridge_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await bridge_task
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


@requires_xray
def test_xray_binary_runs_version():
    out = subprocess.run([xray_binary(), "version"], capture_output=True, text=True, timeout=10)
    assert out.returncode == 0
    assert "Xray" in (out.stdout + out.stderr)
