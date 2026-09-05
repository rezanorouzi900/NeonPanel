# tests/probe_client.py — simulate a real v2rayNG-style client end-to-end.
# Author: OpenCode
import asyncio
import base64
import socket

import httpx
import websockets

from app.vless import build_header

BASE = "http://127.0.0.1:8181"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def main():
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
    async with httpx.AsyncClient() as cx:
        lr = await cx.post(f"{BASE}/api/login", json={"password": "smoke-pass-1"})
        cookie = lr.cookies.get("neon_sess")
        headers = {"Cookie": f"neon_sess={cookie}"} if cookie else {}
        cr = await cx.post(f"{BASE}/api/configs",
                           json={"name": "probe", "quota_gb": 5, "expires_days": 30},
                           headers=headers)
        print("create cfg status:", cr.status_code, cr.text[:80])
        uid = cr.json()["data"]["uuid"]
        print("uuid:", uid)

        hdr = build_header(uid, "127.0.0.1", echo_port)
        print("header len:", len(hdr))

        # --- mode 1: normal (header in first frame, no ed) ---
        async with websockets.connect("ws://127.0.0.1:8181/vl",
                                      open_timeout=6, ping_interval=None) as ws:
            await ws.send(hdr + b"payload1")
            r1 = await asyncio.wait_for(ws.recv(), timeout=4)
            r2 = await asyncio.wait_for(ws.recv(), timeout=4)
            print("mode1 normal:", r1[:2] == b"\x00\x00", r2 == b"ECHO:payload1")

        # --- mode 2: ed=2560 (header in subprotocol, no frame) ---
        ed_path = base64.urlsafe_b64encode(hdr + b"payload2").decode().rstrip("=")
        async with websockets.connect("ws://127.0.0.1:8181/vl?ed=2560",
                                      subprotocols=[ed_path],
                                      open_timeout=6, ping_interval=None) as ws:
            r1 = await asyncio.wait_for(ws.recv(), timeout=4)
            r2 = await asyncio.wait_for(ws.recv(), timeout=4)
            print("mode2 ed2560:", r1[:2] == b"\x00\x00", r2 == b"ECHO:payload2")
            # round-trip after early data
            await ws.send(b"more")
            r3 = await asyncio.wait_for(ws.recv(), timeout=4)
            print("mode2 roundtrip:", r3 == b"ECHO:more")

        # --- mode 3: bad uuid should be instantly closed ---
        bad = build_header("99999999-9999-9999-9999-999999999999", "127.0.0.1", echo_port)
        try:
            async with websockets.connect("ws://127.0.0.1:8181/vl",
                                          open_timeout=6, ping_interval=None) as ws:
                await ws.send(bad + b"x")
                await asyncio.wait_for(ws.recv(), timeout=3)
                print("mode3 bad-uuid: got data (BAD!)")
        except Exception as e:
            print("mode3 bad-uuid: refused OK", type(e).__name__)

    srv.close()


asyncio.run(main())
