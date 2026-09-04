# app/ws_bridge.py
# Goal: bridge edge WebSocket traffic (random paths) to Xray's internal WS port.
# Author: OpenCode
from __future__ import annotations

import asyncio
import logging

from starlette.types import ASGIApp, Receive, Scope, Send

from .xray_config import XRAY_WS_PORTS

log = logging.getLogger("wsbridge")


class WSBridge:
    """ASGI middleware:
    - websocket scopes on known paths → proxied to Xray via a real WS client
      (each protocol has its own internal port)
    - plain HTTP on those paths → 400 (no fingerprinting)
    - everything else → the panel app
    """

    def __init__(self, app: ASGIApp | None):
        self.app = app
        # path → internal xray ws port
        self.path_ports: dict[str, int] = {}

    def set_paths(self, paths: dict) -> None:
        self.path_ports = {}
        for proto, p in paths.items():
            if p and proto in XRAY_WS_PORTS:
                self.path_ports[p] = XRAY_WS_PORTS[proto]
        log.info("ws bridge routes: %s", self.path_ports)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path")
        if scope["type"] == "websocket" and path in self.path_ports:
            try:
                return await self._proxy_ws(scope, receive, send)
            except Exception:  # noqa: BLE001 — never take the panel down
                try:
                    await send({"type": "websocket.close", "code": 1011})
                except Exception:
                    pass
                return
        if scope["type"] == "http" and path in self.path_ports:
            return await self._deny(send)
        if self.app is not None:
            await self.app(scope, receive, send)

    async def _deny(self, send: Send) -> None:
        await send({"type": "http.response.start", "status": 400,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"Bad Request"})

    async def _proxy_ws(self, scope, receive, send) -> None:
        """Accept the edge WS, then pump bytes bidirectionally to Xray's WS."""
        import websockets

        await send({"type": "websocket.accept", "subprotocol": None})
        port = self.path_ports[scope["path"]]
        uri = f"ws://127.0.0.1:{port}{scope['path']}"
        # max_size=None: VPN frames can exceed the default 1MB
        xr = await websockets.connect(uri, max_size=None, ping_interval=None)
        try:

            async def pump_in():
                """edge → xray"""
                while True:
                    msg = await receive()
                    if msg["type"] == "websocket.disconnect":
                        return
                    data = msg.get("bytes") or (msg.get("text") or "").encode()
                    if data:
                        await xr.send(data)

            async def pump_out():
                """xray → edge"""
                async for data in xr:
                    if isinstance(data, str):
                        await send({"type": "websocket.send", "text": data})
                    else:
                        await send({"type": "websocket.send", "bytes": data})

            done, pending = await asyncio.wait(
                [asyncio.create_task(pump_in()), asyncio.create_task(pump_out())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                if task.exception() and not isinstance(task.exception(), asyncio.CancelledError):
                    raise task.exception()
        finally:
            try:
                await xr.close()
            except Exception:
                pass
        try:
            await send({"type": "websocket.close", "code": 1000})
        except Exception:
            pass
