# app/ws_bridge.py
# Goal: bridge edge WebSocket traffic (random paths) to the internal Xray WS port.
# Author: OpenCode
from __future__ import annotations

import logging

import httpx
from starlette.types import ASGIApp, Receive, Scope, Send

from .xray_config import XRAY_WS_PORT

log = logging.getLogger("wsbridge")

HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
}


class WSBridge:
    """ASGI middleware: requests whose path matches a WS path are pumped to Xray
    (plain HTTP + Upgrade), everything else falls through to the panel."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self._client = httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{XRAY_WS_PORT}",
            timeout=httpx.Timeout(600, connect=10),
        )
        self.paths: set[str] = set()

    def set_paths(self, paths: dict) -> None:
        self.paths = {v for v in paths.values() if v}
        log.info("ws bridge paths: %s", self.paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] in self.paths:
            try:
                return await self._pump(scope, receive, send)
            except Exception:  # noqa: BLE001 — never take the panel down
                return await self._deny(send)
        await self.app(scope, receive, send)

    async def _deny(self, send: Send) -> None:
        await send({"type": "http.response.start", "status": 400,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"Bad Request"})

    async def _pump(self, scope, receive, send) -> None:
        req_headers = [
            (k, v) for k, v in scope["headers"]
            if k.decode().lower() not in HOP_HEADERS
        ] + [(b"host", f"127.0.0.1:{XRAY_WS_PORT}".encode())]

        method = scope["method"]
        url_path = scope["path"] + (("?" + scope["query_string"].decode()) if scope.get("query_string") else "")

        upstream_req = self._client.build_request(
            method, url_path, headers=dict(
                (k.decode(), v.decode()) for k, v in req_headers
            ),
        )

        upstream = await self._client.send(upstream_req, stream=True)
        try:
            resp_headers = [
                (k.lower().encode(), v.encode())
                for k, v in upstream.headers.items()
                if k.lower() not in HOP_HEADERS
            ]
            await send({
                "type": "http.response.start",
                "status": upstream.status_code,
                "headers": resp_headers,
            })
            async for chunk in upstream.aiter_bytes(65536):
                if chunk:
                    await send({"type": "http.response.body", "body": chunk, "more_body": True})
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        finally:
            await upstream.aclose()
