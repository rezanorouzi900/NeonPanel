# app/links.py
# VLESS link builder — px-panel format (single protocol, ed=2560, clean params).
# Author: OpenCode
from __future__ import annotations

from urllib.parse import quote

FP = "chrome"
ED = 2560  # 0-RTT early-data via Sec-WebSocket-Protocol (px-panel standard)


def ws_path(token: str = "") -> str:
    """Optional random suffix path — keeps the URL unguessable."""
    return "/vl" + (f"-{token}" if token else "")


def build_vless(uuid: str, host: str, port: int, name: str, tls: bool,
               path: str | None = None, fp: str = FP) -> str:
    """vless:// link — explicit port always (px-panel shape, ed=2560 early data)."""
    p = path or ws_path()
    q = "&".join([
        "encryption=none",
        "security=tls" if tls else "security=none",
        f"sni={host}" if tls else "",
        f"fp={fp}",
        "type=ws",
        f"host={host}",
        f"path={quote(p)}?ed={ED}",
        "alpn=http/1.1" if tls else "",
    ])
    q = "&".join(x for x in q.split("&") if x)
    # explicit :port — some clients mis-detect the server port otherwise
    return f"vless://{uuid}@{host}:{port}?{q}#{quote(name)}"


def build_singbox_outbound(uuid: str, host: str, port: int, tag: str, tls: bool,
                           path: str | None = None) -> dict:
    p = path or ws_path()
    ob = {
        "tag": tag, "type": "vless", "server": host, "server_port": port,
        "uuid": uuid, "network": "tcp",
        "transport": {
            "type": "ws", "path": p, "max_early_data": ED,
            "early_data_header_name": "Sec-WebSocket-Protocol",
            "headers": {"Host": host},
        },
    }
    if tls:
        ob["tls"] = {
            "enabled": True, "server_name": host,
            "alpn": ["http/1.1"], "utls": {"enabled": True, "fingerprint": FP},
        }
    return ob


def build_clash_proxy(uuid: str, host: str, port: int, name: str, tls: bool,
                      path: str | None = None) -> dict:
    p = path or ws_path()
    proxy = {
        "name": name, "type": "vless", "server": host, "port": port,
        "uuid": uuid, "network": "ws",
        "ws-opts": {
            "path": p, "max-early-data": ED,
            "early-data-header-name": "Sec-WebSocket-Protocol",
            "headers": {"Host": host},
        },
    }
    if tls:
        proxy.update({
            "tls": True, "servername": host, "client-fingerprint": FP,
            "skip-cert-verify": False,
        })
    return proxy


def build_xray_outbound(uuid: str, host: str, port: int, tag: str, tls: bool,
                        path: str | None = None) -> dict:
    p = path or ws_path()
    ob = {
        "tag": tag, "protocol": "vless",
        "settings": {"vnext": [{
            "address": host, "port": port,
            "users": [{"id": uuid, "encryption": "none"}],
        }]},
        "streamSettings": {
            "network": "ws",
            "wsSettings": {"path": f"{p}?ed={ED}", "headers": {"Host": host}},
        },
    }
    if tls:
        ob["streamSettings"].update({
            "security": "tls",
            "tlsSettings": {
                "serverName": host, "fingerprint": FP, "alpn": ["http/1.1"],
                "allowInsecure": False,
            },
        })
    return ob
