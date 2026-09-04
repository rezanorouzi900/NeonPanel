# tests/smoke_live.py — manual live smoke: real WS client against running server.
# Author: OpenCode
import asyncio
import socket

import httpx
import websockets

from app.vless import build_header

BASE = "http://127.0.0.1:8181"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


ECHO = free_port()


async def echo():
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

    return await asyncio.start_server(handler, "127.0.0.1", ECHO)


async def main():
    srv = await echo()
    async with httpx.AsyncClient() as cx:
        lr = await cx.post(f"{BASE}/api/login", json={"password": "smoke-pass-1"})
        cookie = lr.cookies.get("neon_sess")
        cr = await cx.post(
            f"{BASE}/api/configs",
            json={"name": "ws-e2e", "quota_gb": 1, "expires_days": 30},
            headers={"Cookie": f"neon_sess={cookie}"},
        )
        uid = cr.json()["data"]["uuid"]
        print("cfg uuid:", uid[:8])

        hdr = build_header(uid, "127.0.0.1", ECHO) + b"ping-px"
        async with websockets.connect("ws://127.0.0.1:8181/vl",
                                      open_timeout=6, ping_interval=None) as ws:
            await ws.send(hdr)
            resp = await asyncio.wait_for(ws.recv(), timeout=5)
            print("vless-ok-header:", resp[:2] == b"\x00\x00")
            data = await asyncio.wait_for(ws.recv(), timeout=5)
            print("echo round1:", data == b"PING-PX")
            await ws.send(b"second")
            data2 = await asyncio.wait_for(ws.recv(), timeout=5)
            print("echo round2:", data2 == b"SECOND")

        st = await cx.get(f"{BASE}/api/stats",
                          headers={"Cookie": f"neon_sess={cookie}"})
        used = st.json()["data"]["total_used"]
        print("usage-counted:", used, used > 0)
    srv.close()
    await srv.wait_closed()


asyncio.run(main())
