# tests/test_e2e_real.py — REAL end-to-end: live uvicorn server + websockets client.
# The exact same path a real v2rayNG client walks: wss upgrade → Bridge → relay
# → VLESS parse → TCP to an echo server → data both ways.
# Author: OpenCode
import asyncio
import os
import socket
import subprocess
import sys

import pytest
import websockets

from app.vless import build_header


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_live_server_vless_roundtrip(tmp_path, monkeypatch):
    """Boot the real app (uvicorn) on a random port, log in, create a config,
    then connect a real websockets client to /vl and exchange data."""
    import httpx

    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, app_dir)

    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    monkeypatch.setenv("ADMIN_PASS", "test-pass-123")

    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=app_dir, env={**os.environ, "DATA_DIR": data_dir,
                          "ADMIN_PASS": "test-pass-123", "TESTING": "1"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # wait for readiness
        base = f"http://127.0.0.1:{port}"
        ready = False
        for _ in range(40):
            try:
                async with httpx.AsyncClient() as cx:
                    r = await cx.get(f"{base}/api/health", timeout=2)
                    if r.status_code == 200:
                        ready = True
                        break
            except Exception:
                pass
            await asyncio.sleep(0.25)
        assert ready, "server did not become ready"

        # create a config through the real API (auth cookie)
        async with httpx.AsyncClient() as cx:
            lr = await cx.post(f"{base}/api/login", json={"password": "test-pass-123"})
            cookie = lr.cookies.get("neon_sess")
            cr = await cx.post(f"{base}/api/configs",
                               json={"name": "e2e-real"},
                               headers={"Cookie": f"neon_sess={cookie}"})
            assert cr.status_code == 200, cr.text
            uid = cr.json()["data"]["uuid"]

        # echo server to tunnel to
        echo_port = free_port()

        async def echo():
            async def h(r, w):
                try:
                    while True:
                        d = await r.read(65536)
                        if not d:
                            break
                        w.write(b"ECHO:" + d)
                        await w.drain()
                finally:
                    w.close()

            return await asyncio.start_server(h, "127.0.0.1", echo_port)

        srv = await echo()
        try:
            hdr = build_header(uid, "127.0.0.1", echo_port)
            async with websockets.connect(
                f"ws://127.0.0.1:{port}/vl",
                open_timeout=8, ping_interval=None,
            ) as ws:
                await ws.send(hdr + b"hello")
                a = await asyncio.wait_for(ws.recv(), timeout=6)
                b = await asyncio.wait_for(ws.recv(), timeout=6)
                assert a[:2] == b"\x00\x00"
                assert b == b"ECHO:hello"
                # persistence
                await ws.send(b"again")
                c = await asyncio.wait_for(ws.recv(), timeout=6)
                assert c == b"ECHO:again"
        finally:
            srv.close()
            await srv.wait_closed()
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.asyncio
async def test_live_server_rejects_bad_uuid(tmp_path, monkeypatch):
    import httpx

    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, app_dir)

    from app import store

    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("DATA_DIR", data_dir)
    monkeypatch.setenv("ADMIN_PASS", "test-pass-123")
    store._state = {"configs": {}, "groups": {}, "admin_hash": "x", "seq": 1}
    store.save = lambda: None
    store.create_config("e2e2")

    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=app_dir, env={**os.environ, "DATA_DIR": data_dir,
                          "ADMIN_PASS": "test-pass-123", "TESTING": "1"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                async with httpx.AsyncClient() as cx:
                    r = await cx.get(f"{base}/api/health", timeout=2)
                    if r.status_code == 200:
                        break
            except Exception:
                pass
            await asyncio.sleep(0.25)

        bad = build_header("99999999-9999-9999-9999-999999999999", "1.1.1.1", 80)
        with pytest.raises(websockets.exceptions.ConnectionClosed):
            async with websockets.connect(f"ws://127.0.0.1:{port}/vl",
                                          open_timeout=8, ping_interval=None) as ws:
                await ws.send(bad + b"x")
                await asyncio.wait_for(ws.recv(), timeout=5)
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
