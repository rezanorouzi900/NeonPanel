# app/bridge.py
# ASGI router: /vl+/<token> WS → relay; sub pages/API/static → FastAPI app.
# Author: OpenCode
from __future__ import annotations

import re

from starlette.types import ASGIApp, Receive, Scope, Send

from . import relay

_VL_RE = re.compile(r"^/vl(/[0-9A-Za-z_\-]{4,64})?$")


class Bridge:
    """Outermost ASGI middleware.

    - websocket on /vl (with optional suffix) → relay.handle_vless_ws
    - anything else → the FastAPI panel (routes, subs, static)
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket" and _VL_RE.match(scope.get("path", "")):
            return await relay.handle_vless_ws(scope, receive, send)
        await self.app(scope, receive, send)
