# app/routes.py
# Goal: all /api routes — auth, users, sub, domain, tunnel, mtproto, system (PART 2 §7).
# Author: OpenCode
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

import qrcode
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlmodel import Session, select

from .auth import client_ip, create_access, create_refresh, decode, get_current_admin, guard, verify_password
from .backup import make_backup, restore_backup
from .config import settings
from .db import get_engine, pwd, seed_admin
from .domain import detect_domain, domain_source, is_local
from .links import build_all, user_usable
from .models import Admin, Setting, TrafficLog, User
from .sub import render_base64, render_clash, render_json, render_singbox, userinfo_header
from .supervisor import Child, supervisor
from .users import create_user, delete_user, patch_user, reset_usage

router = APIRouter()


def db_session():
    with Session(get_engine(settings.data_dir)) as s:
        yield s


def err(status: int, code: str, msg: str, fields: list | None = None):
    detail = {"ok": False, "code": code, "msg_fa": msg}
    if fields:
        detail["fields"] = fields
    return HTTPException(status_code=status, detail=detail)


def ok_data(data: dict) -> dict:
    return {"ok": True, "data": data}


def get_paths(s: Session) -> dict:
    row = s.exec(select(Setting).where(Setting.key == "ws_paths")).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            pass
    return {"vless": "/vless", "vmess": "/vmess", "trojan": "/trojan"}


def link_ctx(s: Session, request: Request) -> dict:
    domain = detect_domain(request)
    # host part without port (for sni/host fields)
    host = domain.split(":")[0]
    tls = not is_local(domain)
    if ":" not in domain:
        # no explicit port in Host — either 443 edge (https) or plain dev
        port = 443 if tls else settings.port
    else:
        _host_only, _, port_str = domain.partition(":")
        port = int(port_str) if port_str.isdigit() else settings.port
    return {"domain": host, "port": port, "tls": tls,
            "paths": get_paths(s), "ss_port": settings.ss_port}


def qr_png(link: str) -> str:
    img = qrcode.make(link)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ---------------- auth ----------------

@router.post("/api/auth/login")
def login(body: dict, request: Request, s: Session = Depends(db_session)):
    ip = client_ip(request)
    if guard.is_locked(ip):
        raise err(429, "LOCKED", "به دلیل تلاش زیاد، موقتاً قفل شدی — ۱۵ دقیقه صبر کن")
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    adm = s.exec(select(Admin).where(Admin.username == username)).first()
    if not adm or not pwd.verify(password, adm.pass_hash):
        guard.record(ip)
        raise err(401, "BAD_CRED", "نام کاربری یا رمز عبور اشتباه است")
    guard.reset(ip)
    return ok_data({"access": create_access(username), "refresh": create_refresh(username)})


@router.post("/api/auth/refresh")
def refresh(body: dict):
    username = decode(body.get("refresh") or "", expected="refresh")
    if not username:
        raise err(401, "NO_AUTH", "توکن رفرش نامعتبر است")
    return ok_data({"access": create_access(username)})


@router.post("/api/auth/change-pass")
def change_pass(body: dict, admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    old, new = body.get("old") or "", body.get("new") or ""
    if len(new) < 8:
        raise err(400, "BAD_INPUT", "رمز جدید حداقل ۸ کاراکتر باشد", ["new"])
    adm = s.exec(select(Admin).where(Admin.username == admin)).first()
    if not adm or not verify_password(old, adm.pass_hash):
        raise err(400, "BAD_CRED", "رمز فعلی اشتباه است")
    adm.pass_hash = pwd.hash(new)
    s.add(adm)
    s.commit()
    return ok_data({"changed": True})


# ---------------- users ----------------

@router.get("/api/users")
def list_users(page: int = 1, per: int = 20, q: str = "",
               admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    per = min(per, 100)
    stmt = select(User)
    if q:
        stmt = stmt.where(User.name.contains(q))
    rows = s.exec(stmt.order_by(User.id)).all()
    start = max(0, (page - 1) * per)
    return ok_data({"total": len(rows), "page": page,
                    "items": [u.dict() for u in rows[start:start + per]]})


@router.post("/api/users")
def add_user(body: dict, request: Request,
             admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    user, code = create_user(
        s, body.get("name") or "", body.get("quota_gb") or 0,
        body.get("expires_days") or 0, body.get("enabled", True),
    )
    if code:
        msg = "ورودی نامعتبر است" if code == "BAD_INPUT" else "این نام قبلاً استفاده شده"
        raise err(400 if code == "BAD_INPUT" else 409, code, msg,
                  ["name"] if code == "BAD_INPUT" else None)
    ctx = link_ctx(s, request)
    links = build_all(user, ctx)
    return ok_data({
        "id": user.id, "name": user.name, "uuid": user.uuid, "sub_token": user.sub_token,
        "links": links, "sub_url": f"https://{ctx['domain']}/sub/{user.sub_token}",
        "qr": [qr_png(links["vless"])],
    })


@router.get("/api/users/{user_id}")
def get_user(user_id: int, request: Request,
             admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    user = s.get(User, user_id)
    if not user:
        raise err(404, "NOT_FOUND", "کاربر پیدا نشد")
    ctx = link_ctx(s, request)
    links = build_all(user, ctx)
    return ok_data({**user.dict(), "links": links,
                    "sub_url": f"https://{ctx['domain']}/sub/{user.sub_token}",
                    "qr": [qr_png(lnk) for lnk in links.values()]})


@router.patch("/api/users/{user_id}")
def edit_user(user_id: int, body: dict,
              admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    user, code = patch_user(s, user_id, **body)
    if code:
        raise err(404 if code == "NOT_FOUND" else 400, code,
                  "کاربر پیدا نشد" if code == "NOT_FOUND" else "خطا در ویرایش")
    return ok_data(user.dict())


@router.delete("/api/users/{user_id}")
def remove_user(user_id: int, wipe: bool = False,
                admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    code = delete_user(s, user_id, wipe)
    if code:
        raise err(404, "NOT_FOUND", "کاربر پیدا نشد")
    return ok_data({"deleted": True})


@router.post("/api/users/{user_id}/reset")
def reset_user(user_id: int, new_token: bool = False,
               admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    user, code = reset_usage(s, user_id, new_token)
    if code:
        raise err(404, "NOT_FOUND", "کاربر پیدا نشد")
    return ok_data(user.dict())


@router.get("/api/users/{user_id}/qr")
def user_qr(user_id: int, proto: str = "vless", request: Request = None,
            admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    user = s.get(User, user_id)
    if not user:
        raise err(404, "NOT_FOUND", "کاربر پیدا نشد")
    links = build_all(user, link_ctx(s, request))
    if proto not in links:
        raise err(400, "BAD_INPUT", "پروتکل نامعتبر است")
    img = qrcode.make(links[proto])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


# ---------------- subscription (public, token-only) ----------------

@router.get("/sub/{token}")
def subscription(token: str, fmt: str = "base64", request: Request = None,
                 s: Session = Depends(db_session)):
    user = s.exec(select(User).where(User.sub_token == token)).first()
    if not user:
        raise err(404, "SUB_GONE", "لینک ساب معتبر نیست")
    usable, _reason = user_usable(user)
    if not usable:
        return PlainTextResponse("این ساب دیگر فعال نیست", status_code=404)
    ctx = link_ctx(s, request)
    links = build_all(user, ctx)
    entries = []
    for proto, link in links.items():
        entries.append({
            "proto": proto, "label": f"{user.name}-{proto.upper()}", "domain": ctx["domain"],
            "port": ctx["port"], "path": ctx["paths"].get(proto, "/"), "uuid": user.uuid,
            "password": user.trojan_pass if proto == "trojan" else user.ss_pass,
        })
    if fmt == "clash":
        return PlainTextResponse(render_clash(entries), media_type="text/yaml; charset=utf-8")
    if fmt == "singbox":
        return JSONResponse(json.loads(render_singbox(entries)))
    if fmt == "json":
        resp = JSONResponse(render_json(user, links, ctx["domain"]))
        resp.headers["Subscription-Userinfo"] = userinfo_header(user)
        return resp
    resp = PlainTextResponse(render_base64(list(links.values())),
                             media_type="text/plain; charset=utf-8")
    resp.headers["Subscription-Userinfo"] = userinfo_header(user)
    return resp


# ---------------- system ----------------

@router.get("/api/health")
def health(request: Request):
    from . import __version__

    st = supervisor.status()
    return {"ok": True, "version": __version__, "xray": st["xray"],
            "tunnel": st["tunnel"], "mtproto": st["mtproto"],
            "domain": detect_domain(request)}


@router.get("/api/stats/summary")
def stats_summary(days: int = 30, admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    users = s.exec(select(User)).all()
    active = [u for u in users if user_usable(u)[0]]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_rows = s.exec(select(TrafficLog).where(TrafficLog.day == today)).all()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    all_rows = s.exec(select(TrafficLog).where(TrafficLog.day >= cutoff)).all()
    per_day: dict[str, int] = {}
    for r in all_rows:
        per_day[r.day] = per_day.get(r.day, 0) + r.up_bytes + r.down_bytes
    daily = [{"day": d, "bytes": per_day[d]} for d in sorted(per_day)]
    return ok_data({
        "active_users": len(active), "total_users": len(users),
        "today_bytes": sum(t.down_bytes + t.up_bytes for t in today_rows),
        "daily": daily,
    })


@router.get("/api/domain")
def current_domain(request: Request, admin: str = Depends(get_current_admin),
                   s: Session = Depends(db_session)):
    row = s.exec(select(Setting).where(Setting.key == "detected_at")).first()
    return ok_data({"domain": detect_domain(request), "source": domain_source(),
                    "detected_at": row.value if row else ""})


@router.post("/api/domain/override")
def override_domain(body: dict, admin: str = Depends(get_current_admin)):
    new = body.get("domain")
    if new is None:
        os.environ.pop("PUBLIC_DOMAIN", None)
        return ok_data({"domain": None, "cleared": True})
    if not new or len(new) > 253:
        raise err(400, "BAD_INPUT", "دامنه نامعتبر است", ["domain"])
    clean = new.strip().lower()
    os.environ["PUBLIC_DOMAIN"] = clean
    return ok_data({"domain": clean})


@router.get("/api/tunnel")
def tunnel_status(admin: str = Depends(get_current_admin)):
    from . import tunnel

    return ok_data(tunnel.status())


@router.get("/api/mtproto")
def mtproto_status(admin: str = Depends(get_current_admin)):
    from . import mtproto

    secret = mtproto.ensure_secret(settings.data_dir)
    return ok_data({
        "enabled": settings.mt_enabled, "port": settings.mt_port,
        "links": mtproto.build_links(mtproto.suggested_host(), settings.mt_port, secret),
    })


@router.post("/api/mtproto/toggle")
def mtproto_toggle(body: dict, admin: str = Depends(get_current_admin)):
    on = bool(body.get("on"))
    settings.mt_enabled = on
    child = supervisor.children.get("mtproto")
    if on:
        if child is None:
            import sys

            child = Child("mtproto", [sys.executable, "-m", "app.mtproto"])
            supervisor.children["mtproto"] = child
        child.enabled = True
        child.start()
    elif child:
        child.enabled = False
        child.stop()
    return ok_data({"enabled": on})


@router.post("/api/xray/reload")
def xray_reload(admin: str = Depends(get_current_admin), s: Session = Depends(db_session)):
    from .xray_config import rebuild_and_reload

    ok = rebuild_and_reload(session=s, supervisor=supervisor)
    if not ok:
        raise err(500, "XRAY_FAIL", "بازسازی کانفیگ Xray شکست خورد")
    return ok_data({"reloaded": True})


@router.get("/api/backup")
def download_backup(admin: str = Depends(get_current_admin)):
    blob = make_backup(settings.data_dir)
    return Response(content=blob, media_type="application/zip",
                    headers={"Content-Disposition": "attachment; filename=backup.zip"})


@router.post("/api/restore")
def restore(file: UploadFile = File(...), admin: str = Depends(get_current_admin)):
    blob = file.file.read()
    ok, reason = restore_backup(blob, settings.data_dir)
    if not ok:
        raise err(400, "BAD_INPUT", reason)
    return ok_data({"restored": True})


# ---------------- startup helpers ----------------

def random_ws_paths() -> dict:
    alpha = string.ascii_letters + string.digits
    return {p: "/" + "".join(secrets.choice(alpha) for _ in range(12))
            for p in ("vless", "vmess", "trojan")}


def init_ws_paths(s: Session) -> dict:
    row = s.exec(select(Setting).where(Setting.key == "ws_paths")).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            pass
    paths = random_ws_paths()
    s.add(Setting(key="ws_paths", value=json.dumps(paths)))
    s.commit()
    return paths


def seed_first_admin(s: Session) -> str | None:
    return seed_admin(s, settings.admin_user, settings.admin_pass)
