# app/xray_config.py
# Goal: build & validate Xray-core JSON config (internal WS port + real x25519 Reality keys).
# Author: OpenCode
from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import string

from sqlmodel import Session, select

from .config import Settings, settings

log = logging.getLogger("xray")

XRAY_API_PORT = int(os.getenv("XRAY_API_PORT", "10085"))
XRAY_WS_PORT = int(os.getenv("XRAY_WS_PORT", "10086"))
REQUIRED_TAGS = {"vless-ws", "vmess-ws", "trojan-ws", "reality-in"}


def generate_reality_keys() -> dict:
    """Real x25519 keypair + shortId (base64url without padding, as Xray expects)."""
    from cryptography.hazmat.primitives.asymmetric import x25519

    priv = x25519.X25519PrivateKey.generate()

    def enc(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return {
        "privateKey": enc(priv.private_bytes_raw()),
        "publicKey": enc(priv.public_key().public_bytes_raw()),
        "shortId": secrets.token_hex(2),
    }


def random_ws_path(prefix: str) -> str:
    """Readable yet unguessable path: /<proto>-XXXXXXXX (62^8 combos)."""
    alpha = string.ascii_letters + string.digits
    return f"/{prefix}-" + "".join(secrets.choice(alpha) for _ in range(8))


def config_path() -> str:
    return os.path.join(os.path.abspath(settings.data_dir), "xray-config.json")


def _clients_vless(users):
    return [{"id": u.uuid, "email": u.name} for u in users]


def _clients_vmess(users):
    return [{"id": u.uuid, "email": u.name, "alterId": 0} for u in users]


def _clients_trojan(users):
    return [{"password": u.trojan_pass, "email": u.name} for u in users]


def _clients_ss(users):
    return [{"password": u.ss_pass, "email": u.name} for u in users]


def build_config(
    users: list,
    s: Settings,
    paths: dict,
    reality_keys: dict | None = None,
    api_port: int = XRAY_API_PORT,
    ws_port: int = XRAY_WS_PORT,
) -> dict:
    """Full Xray config. WS inbounds listen on a private port bridged by the panel."""
    users = [u for u in users if u.enabled]
    rk = reality_keys or generate_reality_keys()
    inbounds: list[dict] = [
        {
            "tag": "api-in", "listen": "127.0.0.1", "port": api_port,
            "protocol": "dokodemo-door", "settings": {"address": "127.0.0.1"},
        },
        {
            "tag": "vless-ws", "listen": "127.0.0.1", "port": ws_port, "protocol": "vless",
            "settings": {"clients": _clients_vless(users), "decryption": "none"},
            "streamSettings": {"network": "ws", "wsSettings": {"path": paths["vless"]}},
        },
        {
            "tag": "vmess-ws", "listen": "127.0.0.1", "port": ws_port, "protocol": "vmess",
            "settings": {"clients": _clients_vmess(users)},
            "streamSettings": {"network": "ws", "wsSettings": {"path": paths["vmess"]}},
        },
        {
            "tag": "trojan-ws", "listen": "127.0.0.1", "port": ws_port, "protocol": "trojan",
            "settings": {"clients": _clients_trojan(users)},
            "streamSettings": {"network": "ws", "wsSettings": {"path": paths["trojan"]}},
        },
    ]
    if s.ss_port and s.ss_port > 0:
        inbounds.append({
            "tag": "ss-in", "port": s.ss_port, "protocol": "shadowsocks",
            "settings": {"method": "aes-256-gcm", "clients": _clients_ss(users), "network": "tcp,udp"},
        })
    inbounds.append({
        "tag": "reality-in", "port": s.reality_port, "protocol": "vless",
        "settings": {"clients": [{"id": u.uuid, "email": u.name, "flow": "xtls-rprx-vision"} for u in users],
                     "decryption": "none"},
        "streamSettings": {
            "network": "tcp", "security": "reality",
            "realitySettings": {
                "show": False, "dest": f"{s.reality_sni}:443", "xver": 0,
                "serverNames": [s.reality_sni],
                "privateKey": rk["privateKey"], "shortIds": [rk["shortId"]],
            },
        },
    })
    return {
        "log": {"loglevel": "warning", "access": "none"},
        "api": {"tag": "api", "services": ["HandlerService", "StatsService"]},
        "stats": {},
        "policy": {"levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}}},
        "inbounds": inbounds,
        "outbounds": [
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "blocked", "protocol": "blackhole"},
        ],
        "routing": {"rules": [{"type": "field", "inboundTag": ["api-in"], "outboundTag": "api"}]},
    }


def _decode_key_b32(key: str) -> bytes | None:
    try:
        pad = "=" * (-len(key) % 4)
        return base64.urlsafe_b64decode(key + pad)
    except Exception:
        return None


def validate_config(cfg: dict) -> tuple[bool, str]:
    """Check required tags, numeric ports, and a real 32-byte Reality private key."""
    try:
        inbounds = cfg["inbounds"]
    except (KeyError, TypeError):
        return False, "inbounds missing"
    tags = {i.get("tag") for i in inbounds}
    for tag in REQUIRED_TAGS:
        if tag not in tags:
            return False, f"missing inbound {tag}"
    for i in inbounds:
        if not isinstance(i.get("port"), int):
            return False, f"port of {i.get('tag')} not numeric"
    reality = next((i for i in inbounds if i["tag"] == "reality-in"), None)
    if reality:
        priv = reality["streamSettings"]["realitySettings"]["privateKey"]
        raw = _decode_key_b32(priv)
        if not raw or len(raw) != 32:
            return False, "reality privateKey must be a 32-byte x25519 key"
    return True, ""


def write_config(cfg: dict, path: str) -> None:
    """Atomic write: tmp file + rename so a crash never leaves a partial config."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def rebuild_and_reload(session: Session | None = None, supervisor=None) -> bool:
    """Build → validate → write → graceful reload (only if xray child is active)."""
    users: list = []
    paths: dict = {}
    rk: dict | None = None
    if session is not None:
        from .db import get_setting
        from .models import User

        users = session.exec(select(User)).all()
        raw = get_setting(session, "ws_paths", "")
        try:
            paths = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            paths = {}
        priv = get_setting(session, "reality_priv", "")
        if priv:
            rk = {"privateKey": priv,
                  "publicKey": get_setting(session, "reality_pub", ""),
                  "shortId": get_setting(session, "reality_sid", "")}
    if not paths:
        paths = {p: random_ws_path(p) for p in ("vless", "vmess", "trojan")}
    if rk is None:
        rk = generate_reality_keys()
    cfg = build_config(users, settings, paths, rk)
    ok, reason = validate_config(cfg)
    if not ok:
        log.error("config invalid: %s", reason)
        return False
    write_config(cfg, config_path())
    if supervisor is not None and "xray" in supervisor.children:
        return supervisor.reload_xray()
    return True
