# tests/probe_wss_simple.py — minimal wss probe. Author: OpenCode
import asyncio
import base64
import sys

sys.path.insert(0, r"C:\Users\GOD\Projects\NeonPanel")
from app.vless import build_header

HOST = "neonpanel-production.up.railway.app"
UUID = "bd15590f-e310-4b70-b12f-ed0d760c81d3"

import websockets


async def main():
    hdr = build_header(UUID, "1.1.1.1", 80)
    ed = base64.urlsafe_b64encode(hdr + b"GET / HTTP/1.1\r\nHost: 1.1.1.1\r\n\r\n").decode().rstrip("=")
    print("ed len:", len(ed))
    try:
        print("connecting...")
        async with websockets.connect(
            f"wss://{HOST}/vl?ed=2560",
            subprotocols=[ed],
            open_timeout=25,
            ping_interval=20,
            ssl=True,
        ) as ws:
            print("connected!")
            r1 = await asyncio.wait_for(ws.recv(), timeout=10)
            print("frame1 ok:", r1[:2] == b"\x00\x00", "len", len(r1))
            r2 = await asyncio.wait_for(ws.recv(), timeout=10)
            print("frame2 head:", r2[:24])
    except Exception as e:
        print("FAIL:", type(e).__name__, str(e)[:200])


asyncio.run(main())
