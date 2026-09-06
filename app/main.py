# app/main.py
# NeonPanel — pure-python VLESS panel (WS + optional raw TCP relay).
# Author: OpenCode
from __future__ import annotations

import asyncio
import contextlib
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__, store

logging.basicConfig(level=os.getenv("LOG_LEVEL", "info").upper())
log = logging.getLogger("main")

_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
_TCP_PORT = int(os.getenv("TCP_PORT", "0") or 0)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    generated = store.ensure_admin()
    if generated:
        log.warning(">>> رمز ادمین (فقط یک‌بار): %s <<<", generated)
    default = store.ensure_default_link()
    if default:
        log.warning(">>> لینک پیش‌فرض ساخته شد: config id=%s uuid=%s <<<",
                    default["id"], default["uuid"])
    tcp_task = None
    if _TCP_PORT:
        from . import relay

        tcp_task = asyncio.create_task(
            asyncio.start_server(relay.handle_tcp_stream, "0.0.0.0", _TCP_PORT))
        log.info("raw TCP VLESS listener on 0.0.0.0:%s", _TCP_PORT)
    yield
    if tcp_task:
        tcp_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tcp_task


def create_app() -> FastAPI:
    app = FastAPI(title="NeonPanel", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    from .routes import router

    app.include_router(router)
    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")
    return app


# uvicorn entry: bridge wraps the app so /vl WS goes to the relay
from .bridge import Bridge  # noqa: E402

app = Bridge(create_app())
