# app/links.py
# Goal: build & parse the 4 protocol links from the auto-detected domain (PART 3 §10).
# Author: OpenCode
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from .models import User

FP = "chrome"


def _b64_std(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def _b64_url(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def parse_vmess(link: str) -> dict:
    """Decode a vmess:// link back into its JSON config."""
    raw = link[len("vmess://"):].replace("-", "+").replace("_", "/")
    pad = "=" * (-len(raw) % 4)
    data = base64.urlsafe_b64decode(raw + pad)
    return json.loads(data.decode())


def _addr(domain: str, port: int) -> str:
    """host:port, omitting port when it is the standard 443."""
    return domain if port == 443 else f"{domain}:{port}"


def build_vless(user: User, domain: str, port: int, path: str, tls: bool) -> str:
    security = "tls" if tls else "none"
    sni = domain if tls else ""
    q = (
        f"encryption=none&security={security}"
        + (f"&sni={sni}" if sni else "")
        + f"&fp={FP}&type=ws&host={domain}&path={path}"
    )
    return f"vless://{user.uuid}@{_addr(domain, port)}?{q}#{quote_plus(user.name)}-VLESS"


def build_vmess(user: User, domain: str, port: int, path: str, tls: bool) -> str:
    cfg = {
        "v": "2",
        "ps": f"{user.name}-VMESS",
        "add": domain,
        "port": str(port),
        "id": user.uuid,
        "aid": "0",
        "net": "ws",
        "type": "none",
        "host": domain,
        "path": path,
        "tls": "tls" if tls else "",
        "sni": domain if tls else "",
        "fp": FP,
    }
    return "vmess://" + _b64_url(json.dumps(cfg, ensure_ascii=False))


def build_trojan(user: User, domain: str, port: int, path: str, tls: bool) -> str:
    security = "tls" if tls else "none"
    q = f"security={security}&sni={domain}&fp={FP}&type=ws&host={domain}&path={path}"
    return f"trojan://{user.trojan_pass}@{_addr(domain, port)}?{q}#{quote_plus(user.name)}-TROJAN"


def build_ss(user: User, domain: str, ss_port: int) -> str:
    userinfo = _b64_std(f"aes-256-gcm:{user.ss_pass}")
    return f"ss://{userinfo}@{domain}:{ss_port}#{quote_plus(user.name)}-SS"


def build_all(user: User, ctx: dict) -> dict:
    """Build all links. ctx = {domain, port, tls, paths, ss_port}."""
    d = ctx["domain"]
    port = ctx["port"]
    tls = ctx["tls"]
    paths = ctx["paths"]
    out = {
        "vless": build_vless(user, d, port, paths["vless"], tls),
        "vmess": build_vmess(user, d, port, paths["vmess"], tls),
        "trojan": build_trojan(user, d, port, paths["trojan"], tls),
    }
    if ctx.get("ss_port"):
        out["ss"] = build_ss(user, d, ctx["ss_port"])
    return out


def parse_vless(link: str) -> dict:
    u = urlparse(link)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    return {
        "uuid": u.username,
        "domain": u.hostname,
        "port": u.port,
        "path": unquote(q.get("path", "")),
        "security": q.get("security", ""),
        "name": unquote(u.fragment),
    }


def parse_trojan(link: str) -> dict:
    return parse_vless(link) | {"password": u_password(link)}


def u_password(link: str) -> str:
    return urlparse(link).username or ""


def parse_ss(link: str) -> dict:
    u = urlparse(link)
    raw = u.netloc.split("@")[0]
    pad = "=" * (-len(raw) % 4)
    method_pass = base64.b64decode(raw + pad).decode()
    method, _, password = method_pass.partition(":")
    return {
        "method": method,
        "password": password,
        "domain": u.hostname,
        "port": u.port,
        "name": unquote(u.fragment),
    }


def user_usable(user: User, now: datetime | None = None) -> tuple[bool, str]:
    """(usable, reason) — reason in {ok, disabled, expired, quota_full}."""
    now = now or datetime.now(timezone.utc)
    if not user.enabled:
        return False, "disabled"
    if user.expires_at is not None:
        exp = user.expires_at if user.expires_at.tzinfo else user.expires_at.replace(tzinfo=timezone.utc)
        if exp < now:
            return False, "expired"
    if user.quota_gb > 0 and user.used_bytes >= int(user.quota_gb * 1024**3):
        return False, "quota_full"
    return True, "ok"
