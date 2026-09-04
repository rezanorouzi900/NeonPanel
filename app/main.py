# app/main.py
# NeonPanel v3 — pure-python VLESS relay panel (px-panel method, faster).
# Author: OpenCode
from __future__ import annotations

import contextlib
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__, store

logging.basicConfig(level=os.getenv("LOG_LEVEL", "info").upper())
log = logging.getLogger("main")

_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    generated = store.ensure_admin()
    if generated:
        log.warning(">>> رمز ادمین (فقط یک‌بار): %s <<<", generated)
    yield


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
