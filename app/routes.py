# app/routes.py
# Panel API + public sub pages (single VLESS protocol — px-panel method).
# Author: OpenCode
from __future__ import annotations

import base64
import io
import json
import time

import qrcode
import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from . import auth, store
from .links import (
    build_clash_proxy,
    build_singbox_outbound,
    build_vless,
)

router = APIRouter()


def err(status: int, code: str, msg: str):
    return HTTPException(status_code=status, detail={"ok": False, "code": code, "msg_fa": msg})


def ok(data) -> dict:
    return {"ok": True, "data": data}


def detect_host(request: Request) -> tuple[str, int, bool]:
    """(host, port, tls) from request headers — fully automatic."""
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost")
    host = host.split(",")[0].strip().lower()
    proto = (request.headers.get("x-forwarded-proto") or "http").split(",")[0].strip()
    tls = proto == "https"
    if ":" in host:
        h, _, p = host.partition(":")
        return h, int(p) if p.isdigit() else (443 if tls else 80), tls
    return host, 443 if tls else 80, tls


def qr_png(link: str) -> str:
    img = qrcode.make(link)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ---------------- auth ----------------

@router.post("/api/login")
def login(body: dict, request: Request):
    ip = auth.client_ip(request)
    if auth.locked(ip):
        raise err(429, "LOCKED", "تلاش زیاد — ۱۵ دقیقه صبر کن")
    if not store.check_admin(body.get("password", "")):
        auth.record_fail(ip)
        raise err(401, "BAD_CRED", "رمز اشتباه است")
    auth.reset_fails(ip)
    tok = auth.make_token()
    resp = JSONResponse(ok({"token": tok}))
    resp.set_cookie("neon_sess", tok, httponly=True, samesite="lax", max_age=auth.TTL)
    return resp


@router.post("/api/logout")
def logout():
    resp = JSONResponse(ok({"bye": True}))
    resp.delete_cookie("neon_sess")
    return resp


@router.post("/api/change-pass")
def change_pass(body: dict, request: Request):
    auth.require_admin(request)
    new = body.get("new", "")
    if len(new) < 8:
        raise err(400, "BAD_INPUT", "رمز جدید حداقل ۸ کاراکتر")
    if not store.check_admin(body.get("old", "")):
        raise err(400, "BAD_CRED", "رمز فعلی اشتباه است")
    store.set_admin_password(new)
    return ok({"changed": True})


# ---------------- configs CRUD ----------------

@router.get("/api/configs")
def list_configs(request: Request, q: str = ""):
    auth.require_admin(request)
    items = store.list_configs(q)
    host, port, tls = detect_host(request)
    live = {row["uuid"]: row["ips"] for row in store.live_summary()}
    return ok({
        "domain": host, "port": port, "tls": tls,
        "items": [{**c, "online_ips": live.get(c["uuid"], 0)} for c in items],
    })


@router.post("/api/configs")
def create_config(body: dict, request: Request):
    auth.require_admin(request)
    cfg, code = store.create_config(
        body.get("name", ""), body.get("quota_gb", 0), body.get("expires_days", 0),
        body.get("speed_mbps", 0), body.get("max_ips", 0), body.get("note", ""),
    )
    if code:
        raise err(400 if code == "BAD_INPUT" else 409, code,
                  "نام نامعتبر" if code == "BAD_INPUT" else "نام تکراری")
    host, port, tls = detect_host(request)
    link = build_vless(cfg["uuid"], host, port, cfg["name"], tls)
    return ok({**cfg, "link": link, "qr": qr_png(link)})


def _sub_url(host: str, tls: bool, cfg: dict) -> str:
    proto = "https" if tls else "http"
    return f"{proto}://{host}/sub/{cfg['uuid']}"


@router.get("/api/configs/{cid}")
def get_config(cid: int, request: Request):
    auth.require_admin(request)
    cfg = store.get_config(cid)
    if not cfg:
        raise err(404, "NOT_FOUND", "کانفیگ پیدا نشد")
    host, port, tls = detect_host(request)
    link = build_vless(cfg["uuid"], host, port, cfg["name"], tls)
    return ok({**cfg, "link": link, "qr": qr_png(link),
               "sub_url": _sub_url(host, tls, cfg)})


@router.patch("/api/configs/{cid}")
def patch_config(cid: int, body: dict, request: Request):
    auth.require_admin(request)
    cfg, code = store.patch_config(cid, **body)
    if code:
        raise err(404 if code == "NOT_FOUND" else 400, code, "خطا در ویرایش")
    return ok(cfg)


@router.delete("/api/configs/{cid}")
def delete_config(cid: int, request: Request):
    auth.require_admin(request)
    if store.delete_config(cid):
        raise err(404, "NOT_FOUND", "پیدا نشد")
    return ok({"deleted": True})


@router.post("/api/configs/{cid}/reset")
def reset_config(cid: int, request: Request, new_uuid: bool = False):
    auth.require_admin(request)
    cfg, code = store.reset_usage(cid, new_uuid)
    if code:
        raise err(404, "NOT_FOUND", "پیدا نشد")
    return ok(cfg)


# ---------------- groups ----------------

@router.get("/api/groups")
def list_groups(request: Request):
    auth.require_admin(request)
    host, port, tls = detect_host(request)
    proto = "https" if tls else "http"
    items = [{**g,
              "url": f"{proto}://{host}/g/{g['sub_path']}"}
             for g in store.list_groups()]
    return ok(items)


@router.post("/api/groups")
def create_group(body: dict, request: Request):
    auth.require_admin(request)
    g, code = store.create_group(body.get("name", ""), body.get("members", []),
                                 body.get("password", ""))
    if code:
        raise err(400 if code == "BAD_INPUT" else 409, code, "خطا در ساخت گروه")
    return ok(g)


@router.patch("/api/groups/{gid}")
def patch_group(gid: int, body: dict, request: Request):
    auth.require_admin(request)
    g, code = store.patch_group(gid, **body)
    if code:
        raise err(404 if code == "NOT_FOUND" else 400, code, "خطا در ویرایش")
    return ok(g)


@router.delete("/api/groups/{gid}")
def delete_group(gid: int, request: Request):
    auth.require_admin(request)
    if store.delete_group(gid):
        raise err(404, "NOT_FOUND", "پیدا نشد")
    return ok({"deleted": True})


# ---------------- live + stats ----------------

@router.get("/api/live")
def live(request: Request):
    auth.require_admin(request)
    return ok(store.live_summary())


@router.get("/api/stats")
def stats(request: Request):
    auth.require_admin(request)
    cfgs = store.list_configs()
    return ok({
        "configs": len(cfgs),
        "active": len([c for c in cfgs if store.usable(c)[0]]),
        "online": len(store.live_summary()),
        "total_used": sum(c["used_bytes"] for c in cfgs),
    })


@router.get("/api/health")
def health():
    return {"ok": True, "version": "3.0.0", "proto": "vless-ws"}


# ---------------- public sub endpoints ----------------

@router.get("/sub/{uuid_str}")
def sub(uuid_str: str, request: Request, fmt: str = "raw"):
    cfg = store.get_by_uuid(uuid_str)
    if not cfg or not store.usable(cfg)[0]:
        raise err(404, "SUB_GONE", "ساب معتبر نیست")
    host, port, tls = detect_host(request)
    name = f"{cfg['name']} - NeonPanel"
    link = build_vless(cfg["uuid"], host, port, name, tls)
    ua = (request.headers.get("user-agent") or "").lower()
    browser = any(x in ua for x in ("mozilla", "chrome", "safari", "edge")) and \
        not any(x in ua for x in ("okhttp", "v2ray", "sing-box", "hiddify", "clash"))

    if fmt == "html" or (fmt == "raw" and browser):
        return _sub_page(cfg, link, host, tls)

    if fmt == "singbox":
        conf = {
            "outbounds": [build_singbox_outbound(cfg["uuid"], host, port, name, tls),
                          {"tag": "direct", "type": "direct"}],
            "route": {"rules": [{"domain_suffix": [".ir"], "outbound": "direct"}]},
        }
        return PlainTextResponse(json.dumps(conf, ensure_ascii=False, indent=2),
                                 media_type="application/json")
    if fmt == "clash":
        proxy = build_clash_proxy(cfg["uuid"], host, port, name, tls)
        conf = {"proxies": [proxy],
                "proxy-groups": [{"name": "AUTO", "type": "url-test",
                                  "proxies": [name],
                                  "url": "https://www.gstatic.com/generate_204",
                                  "interval": 300}],
                "rules": ["MATCH,AUTO"]}
        return PlainTextResponse(yaml.safe_dump(conf, allow_unicode=True, sort_keys=False),
                                 media_type="text/yaml")
    if fmt == "json":
        return JSONResponse({
            "name": cfg["name"], "link": link,
            "used_bytes": cfg["used_bytes"], "quota_bytes": cfg.get("quota_bytes", 0),
        })
    # raw → base64 (v2rayNG & friends)
    b64 = base64.b64encode((link + "\n").encode()).decode()
    resp = PlainTextResponse(b64, media_type="text/plain; charset=utf-8")
    qb = cfg.get("quota_bytes", 0)
    exp = int(cfg["expires_at"]) if cfg.get("expires_at") else 0
    resp.headers["Subscription-Userinfo"] = (
        f"upload=0; download={cfg['used_bytes']}; total={qb}; expire={exp}")
    return resp


def _sub_page(cfg: dict, link: str, host: str, tls: bool) -> HTMLResponse:
    """Beautiful public page for one config (browser view)."""
    pct = min(100, cfg["used_bytes"] / cfg["quota_bytes"] * 100) if cfg.get("quota_bytes") else 0
    gb = cfg["used_bytes"] / 1024**3
    qgb = f"{cfg['quota_bytes'] / 1024**3:.0f} GB" if cfg.get("quota_bytes") else "نامحدود"
    exp = (time.strftime("%Y-%m-%d", time.localtime(cfg["expires_at"]))
           if cfg.get("expires_at") else "بدون انقضا")
    proto = "https" if tls else "http"
    sub_url = f"{proto}://{host}/sub/{cfg['uuid']}"
    qr = qr_png(link).split(",", 1)[1]
    return HTMLResponse(f"""<!doctype html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{cfg['name']} — NeonPanel</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,'Segoe UI',Tahoma,sans-serif;background:#070b14;color:#f1f5f9;min-height:100vh;padding:24px}}
.w{{max-width:760px;margin:0 auto}}h1{{font-size:22px;margin-bottom:4px;background:linear-gradient(90deg,#22d3ee,#a78bfa);-webkit-background-clip:text;background-clip:text;color:transparent}}
.s{{color:#94a3b8;font-size:13px;margin-bottom:18px}}
.c{{background:#0c1322;border:1px solid #1e293b;border-radius:16px;padding:18px;margin-bottom:14px}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.n{{font-size:20px;font-weight:800;color:#22d3ee}}.l{{font-size:12px;color:#94a3b8;margin-top:2px}}
.bar{{height:8px;background:#111a2e;border-radius:99px;overflow:hidden;margin-top:8px}}.bar i{{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a78bfa)}}
.lb{{display:flex;gap:8px;align-items:center;background:#111a2e;border:1px solid #26344d;border-radius:12px;padding:12px;direction:ltr}}
.lb code{{flex:1;font-size:11px;color:#22d3ee;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.b{{background:linear-gradient(90deg,#22d3ee,#a78bfa);border:0;color:#06121f;font-weight:700;padding:8px 16px;border-radius:10px;cursor:pointer;font-size:12px}}
.qr{{text-align:center;margin-top:12px}}.qr img{{width:200px;height:200px;background:#fff;padding:6px;border-radius:12px}}
.f{{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}}
.f a{{color:#22d3ee;font-size:12px;background:#111a2e;border:1px solid #26344d;padding:6px 12px;border-radius:10px;text-decoration:none}}
.t{{position:fixed;bottom:20px;inset-inline-start:20px;background:#111a2e;border:1px solid #34d399;color:#34d399;padding:10px 16px;border-radius:10px;display:none}}
</style></head><body><div class="w">
<h1>⚡ {cfg['name']}</h1><div class="s">کانفیگ VLESS فعال — در هر اپ V2Ray قابل استفاده است</div>
<div class="c"><div class="g">
<div><div class="n">{gb:.2f} GB</div><div class="l">مصرف شده</div></div>
<div><div class="n">{qgb}</div><div class="l">سقف حجم</div></div>
<div><div class="n">{exp}</div><div class="l">انقضا</div><div class="bar"><i style="width:{pct}%"></i></div></div>
</div></div>
<div class="c"><b style="font-size:14px">لینک VLESS:</b>
<div class="lb" style="margin-top:8px"><code id="lnk">{link}</code><button class="b" id="cp">کپی</button></div>
<div class="f"><a href="?fmt=singbox">Sing-box</a><a href="?fmt=clash">Clash</a><a href="?fmt=json">JSON</a></div>
<div class="qr"><img alt="QR" src="data:image/png;base64,{qr}"></div>
</div>
<div class="c"><b style="font-size:14px">لینک ساب (آپدیت خودکار):</b>
<div class="lb" style="margin-top:8px"><code>{sub_url}</code><button class="b" id="cp2">کپی</button></div>
</div>
</div><div class="t" id="t">کپی شد ✅</div>
<script>
const toast=()=>{{const t=document.getElementById('t');t.style.display='block';setTimeout(()=>t.style.display='none',1500)}}
document.getElementById('cp').onclick=()=>navigator.clipboard.writeText(document.getElementById('lnk').textContent).then(toast);
document.getElementById('cp2').onclick=()=>navigator.clipboard.writeText('{sub_url}').then(toast);
</script></body></html>""")


@router.get("/g/{path}")
def group_sub(path: str, request: Request, pw: str = "", fmt: str = "raw"):
    g = store.get_group_by_path(path)
    if not g:
        raise err(404, "NOT_FOUND", "گروه پیدا نشد")
    if g.get("password") and pw != g["password"]:
        return HTMLResponse(
            "<h3 style='font-family:system-ui;direction:rtl'>این ساب رمزدار است — پارامتر ?pw=رمز را اضافه کن</h3>",
            status_code=401)
    host, port, tls = detect_host(request)
    members = [store.get_config(cid) for cid in g["members"]]
    members = [m for m in members if m and store.usable(m)[0]]
    links = [build_vless(m["uuid"], host, port, f"{m['name']} - NeonPanel", tls)
             for m in members]

    if fmt == "clash":
        proxies = [build_clash_proxy(m["uuid"], host, port, m["name"], tls) for m in members]
        conf = {"proxies": proxies,
                "proxy-groups": [{"name": "AUTO", "type": "url-test",
                                  "proxies": [p["name"] for p in proxies],
                                  "url": "https://www.gstatic.com/generate_204",
                                  "interval": 300}],
                "rules": ["MATCH,AUTO"]}
        return PlainTextResponse(yaml.safe_dump(conf, allow_unicode=True, sort_keys=False),
                                 media_type="text/yaml")
    if fmt == "json":
        return JSONResponse({"name": g["name"], "links": links})
    b64 = base64.b64encode(("\n".join(links) + "\n").encode()).decode()
    return PlainTextResponse(b64, media_type="text/plain; charset=utf-8")
