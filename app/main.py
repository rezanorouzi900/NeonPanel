# app/main.py
# Goal: entrypoint — lifespan (config write BEFORE xray start) + WS bridge + routes.
# Author: OpenCode
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from . import __version__
from .config import settings
from .db import get_engine, get_setting, init_db, set_setting
from .routes import init_ws_paths, router, seed_first_admin
from .security import SecurityHeadersMiddleware, build_rate_limiters
from .stats import loop as stats_loop
from .supervisor import supervisor
from .ws_bridge import WSBridge

logging.basicConfig(level=settings.log_level.upper())
log = logging.getLogger("main")

_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
ws_bridge = WSBridge(None)  # wired in create_app()


def ensure_reality_keys(session: Session) -> None:
    """Persist a real x25519 keypair once — links must embed the matching public key."""
    if get_setting(session, "reality_priv"):
        return
    from .xray_config import generate_reality_keys

    rk = generate_reality_keys()
    set_setting(session, "reality_priv", rk["privateKey"])
    set_setting(session, "reality_pub", rk["publicKey"])
    set_setting(session, "reality_sid", rk["shortId"])
    log.info("reality x25519 keys generated (shortId=%s)", rk["shortId"])


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    engine = get_engine(settings.data_dir)
    init_db(engine)
    with Session(engine) as s:
        init_ws_paths(s)
        ensure_reality_keys(s)
        generated = seed_first_admin(s)
        paths_raw = get_setting(s, "ws_paths", "")
    if generated:
        log.warning(">>> رمز ادمین ساخته‌شده (فقط همین یک‌بار): %s <<<", generated)
        log.warning(">>> بعد از ورود، حتماً رمز را عوض کن <<<")
    # config write must happen BEFORE supervisor.start() or xray dies instantly;
    # use_db=True so EXISTING users are included in xray's client lists
    from .xray_config import rebuild_and_reload

    rebuild_and_reload(use_db=True)
    try:
        supervisor.start()
    except Exception as e:  # noqa: BLE001 — panel must boot even without xray
        log.warning("supervisor not started: %s", e)
    try:
        ws_bridge.set_paths(json.loads(paths_raw) if paths_raw else {})
    except json.JSONDecodeError:
        ws_bridge.set_paths({})
    stats_task = asyncio.create_task(stats_loop())
    yield
    stats_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await stats_task
    supervisor.stop()


def create_app() -> FastAPI:
    """Build the FastAPI app, then wrap it with the outermost WS bridge."""
    fast = FastAPI(title=settings.project_name, version=__version__, lifespan=lifespan)
    fast.include_router(router)

    if not os.getenv("TESTING"):
        for lim in build_rate_limiters():
            fast.add_middleware(lim.__class__, prefix=lim.prefix, limit=lim.limit,
                                window=lim.window, code=lim.code)
    fast.add_middleware(SecurityHeadersMiddleware)
    fast.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")

    # bridge outermost: edge WS traffic is pumped to xray before hitting the router
    ws_bridge.app = fast
    return fast


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
