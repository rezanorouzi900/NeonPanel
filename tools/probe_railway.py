# tests/probe_railway.py — probe the LIVE Railway deployment over wss://
# Author: OpenCode
import asyncio
import base64
import socket

import websockets

from app.vless import build_header

HOST = "neonpanel-production.up.railway.app"
UUID = "bd15590f-e310-4b70-b12f-ed0d760c81d3"  # the user's config uuid
DEST = "1.1.1.1"
DPORT = 80  # 1.1.1.1 http


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def main():
    # mode A: header in first frame (no ed)
    hdr = build_header(UUID, DEST, DPORT)
    print("trying normal WS ...")
    try:
        async with websockets.connect(f"wss://{HOST}/vl",
                                      open_timeout=12, ping_interval=None, ssl=True) as ws:
            await ws.send(hdr + b"GET / HTTP/1.1\r\nHost: 1.1.1.1\r\n\r\n")
            resp = await asyncio.wait_for(ws.recv(), timeout=8)
            print("normal: first frame OK len", len(resp), "resp-ok?", resp[:2] == b"\x00\x00")
            data = await asyncio.wait_for(ws.recv(), timeout=8)
            print("normal: got upstream data, head:", data[:30].replace(b"\r\n", b"|"))
    except Exception as e:
        print("normal FAIL:", type(e).__name__, str(e)[:160])

    # mode B: ed=2560
    ed = base64.urlsafe_b64encode(hdr + b"GET / HTTP/1.1\r\nHost: 1.1.1.1\r\n\r\n").decode().rstrip("=")
    print("trying ed=2560 WS ...")
    try:
        async with websockets.connect(f"wss://{HOST}/vl?ed=2560",
                                      subprotocols=[ed],
                                      open_timeout=12, ping_interval=None, ssl=True) as ws:
            resp = await asyncio.wait_for(ws.recv(), timeout=8)
            print("ed2560: first frame OK len", len(resp), "resp-ok?", resp[:2] == b"\x00\x00")
            data = await asyncio.wait_for(ws.recv(), timeout=8)
            print("ed2560: got upstream data, head:", data[:30].replace(b"\r\n", b"|"))
    except Exception as e:
        print("ed2560 FAIL:", type(e).__name__, str(e)[:160])


if __name__ == "__main__":
    asyncio.run(main())
