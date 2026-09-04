# app/sub.py
# Goal: 4 subscription formats + v2board userinfo header (PART 3 §10).
# Author: OpenCode
from __future__ import annotations

import base64
import json
from datetime import timezone

import yaml

from .links import build_all
from .models import User

PROTOS = ["vless", "vmess", "trojan", "ss"]


def build_links(user: User, ctx: dict) -> dict:
    return build_all(user, ctx)


def render_base64(links: list) -> str:
    body = "\n".join(links)
    return base64.b64encode(body.encode()).decode()


def render_clash(entries: list[dict]) -> str:
    proxies = []
    for e in entries:
        p = e["proto"]
        d = e["domain"]
        if p == "vless":
            proxies.append({
                "name": e["label"], "type": "vless", "server": d.split(":")[0], "port": e["port"],
                "uuid": e["uuid"], "tls": True, "servername": d.split(":")[0],
                "fingerprint": "chrome", "network": "ws",
                "ws-opts": {"path": e["path"], "headers": {"Host": d.split(":")[0]}},
            })
        elif p == "vmess":
            proxies.append({
                "name": e["label"], "type": "vmess", "server": d.split(":")[0], "port": e["port"],
                "uuid": e["uuid"], "tls": True, "network": "ws",
                "ws-opts": {"path": e["path"], "headers": {"Host": d.split(":")[0]}},
            })
        elif p == "trojan":
            proxies.append({
                "name": e["label"], "type": "trojan", "server": d.split(":")[0], "port": e["port"],
                "password": e["password"], "tls": True, "network": "ws",
                "ws-opts": {"path": e["path"], "headers": {"Host": d.split(":")[0]}},
            })
        elif p == "ss":
            proxies.append({
                "name": e["label"], "type": "ss", "server": d.split(":")[0], "port": e["port"],
                "cipher": "aes-256-gcm", "password": e["password"],
            })
    doc = {
        "proxies": proxies,
        "proxy-groups": [{
            "name": "AUTO", "type": "url-test", "proxies": [p["name"] for p in proxies],
            "url": "https://www.gstatic.com/generate_204", "interval": 300,
        }],
        "rules": ["MATCH,AUTO"],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


IR_SITES = [
    "domain:ir", "domain:xn--mgbaam7a8h", "geosite:category-ir",
]


def render_singbox(entries: list[dict]) -> str:
    outbounds = []
    names = []
    for e in entries:
        p = e["proto"]
        host = e["domain"].split(":")[0]
        names.append(e["label"])
        if p == "vless":
            outbounds.append({
                "tag": e["label"], "type": "vless", "server": host, "server_port": e["port"],
                "uuid": e["uuid"], "tls": {"enabled": True, "server_name": host, "utls": {"enabled": True, "fingerprint": "chrome"}},
                "transport": {"type": "ws", "path": e["path"], "headers": {"Host": host}},
            })
        elif p == "vmess":
            outbounds.append({
                "tag": e["label"], "type": "vmess", "server": host, "server_port": e["port"],
                "uuid": e["uuid"], "tls": {"enabled": True, "server_name": host},
                "transport": {"type": "ws", "path": e["path"], "headers": {"Host": host}},
            })
        elif p == "trojan":
            outbounds.append({
                "tag": e["label"], "type": "trojan", "server": host, "server_port": e["port"],
                "password": e["password"], "tls": {"enabled": True, "server_name": host},
                "transport": {"type": "ws", "path": e["path"], "headers": {"Host": host}},
            })
        elif p == "ss":
            outbounds.append({
                "tag": e["label"], "type": "shadowsocks", "server": host, "server_port": e["port"],
                "method": "aes-256-gcm", "password": e["password"],
            })
    outbounds.append({
        "tag": "auto", "type": "urltest", "outbounds": names,
        "url": "https://www.gstatic.com/generate_204", "interval": "5m",
    })
    outbounds.append({"tag": "direct", "type": "direct"})
    doc = {
        "outbounds": outbounds,
        "route": {"rules": [{"domain_suffix": [".ir"], "outbound": "direct"}]},
    }
    return json.dumps(doc, ensure_ascii=False, indent=2)


def render_json(user: User, links: dict, domain: str) -> dict:
    return {
        "name": user.name,
        "domain": domain,
        "links": links,
        "quota_gb": user.quota_gb,
        "used_bytes": user.used_bytes,
        "expire": int(user.expires_at.timestamp()) if user.expires_at else 0,
        "updated": user.updated_at.isoformat() if user.updated_at else None,
    }


def userinfo_header(user: User) -> str:
    total = int(user.quota_gb * 1024**3) if user.quota_gb > 0 else 0
    expire = int(user.expires_at.replace(tzinfo=timezone.utc).timestamp()) if user.expires_at else 0
    return f"upload=0; download={user.used_bytes}; total={total}; expire={expire}"
