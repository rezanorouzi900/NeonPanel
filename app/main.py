# app/main.py
# Goal: entrypoint — lifespan (db init, seed, supervisor, stats loop) + routes + static.
# Author: OpenCode
from __future__ import annotations

import asyncio
import contextlib
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from . import __version__
from .config import settings
from .db import get_engine, init_db
from .routes import init_ws_paths, router, seed_first_admin
from .security import SecurityHeadersMiddleware, build_rate_limiters
from .stats import loop as stats_loop
from .supervisor import supervisor

logging.basicConfig(level=settings.log_level.upper())
log = logging.getLogger("main")

_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    engine = get_engine(settings.data_dir)
    init_db(engine)
    with Session(engine) as s:
        init_ws_paths(s)
        generated = seed_first_admin(s)
    if generated:
        log.warning(">>> رمز ادمین ساخته‌شده (فقط همین یک‌بار): %s <<<", generated)
        log.warning(">>> بعد از ورود، حتماً رمز را عوض کن <<<")
    # supervisor disabled in dev/test when xray binary is absent
    try:
        supervisor.start()
    except Exception as e:  # noqa: BLE001 — panel must boot even without xray
        log.warning("supervisor not started: %s", e)
    stats_task = asyncio.create_task(stats_loop())
    yield
    stats_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await stats_task
    supervisor.stop()


app = FastAPI(title=settings.project_name, version=__version__, lifespan=lifespan)
app.include_router(router)

if not os.getenv("TESTING"):
    for lim in build_rate_limiters():
        app.add_middleware(lim.__class__, prefix=lim.prefix, limit=lim.limit,
                           window=lim.window, code=lim.code)
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
