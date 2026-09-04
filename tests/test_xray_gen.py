# tests/test_xray_gen.py — v2 config: per-proto internal WS ports, real x25519 keys.
# Author: OpenCode
import base64
import json
from datetime import datetime, timedelta

from app.config import Settings
from app.models import User
from app.xray_config import (
    XRAY_WS_PORTS,
    build_config,
    config_path,
    generate_reality_keys,
    random_ws_path,
    validate_config,
    write_config,
)


def make_user(name="reza-01"):
    return User(id=1, name=name, uuid="11111111-2222-3333-4444-555555555555",
                trojan_pass="tp", ss_pass="sp", sub_token="tok",
                expires_at=datetime.utcnow() + timedelta(days=30))


def test_ws_paths_readable_not_random_garbage():
    p = random_ws_path("vless")
    assert p.startswith("/vless-") and len(p) == len("/vless-") + 8
    assert p.isascii() and p[1:].replace("-", "").isalnum()


def test_config_has_required_tags():
    cfg = build_config([make_user()], Settings(), {"vless": "/vless-x", "vmess": "/vmess-x", "trojan": "/trojan-x"})
    tags = {i["tag"] for i in cfg["inbounds"]}
    assert {"vless-ws", "vmess-ws", "trojan-ws", "reality-in", "api-in"} <= tags


def test_ws_inbounds_distinct_internal_ports():
    """xray cannot bind two inbounds to one port — each proto needs its own."""
    cfg = build_config([make_user()], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    ports = {}
    for tag in ("vless-ws", "vmess-ws", "trojan-ws"):
        ib = next(i for i in cfg["inbounds"] if i["tag"] == tag)
        assert ib["listen"] == "127.0.0.1"
        ports[tag] = ib["port"]
    assert len(set(ports.values())) == 3, "WS inbounds must have distinct ports"
    for tag, proto in (("vless-ws", "vless"), ("vmess-ws", "vmess"), ("trojan-ws", "trojan")):
        assert ports[tag] == XRAY_WS_PORTS[proto]


def test_reality_keys_are_real_x25519():
    rk = generate_reality_keys()
    pad = "=" * (-len(rk["privateKey"]) % 4)
    raw = base64.urlsafe_b64decode(rk["privateKey"] + pad)
    assert len(raw) == 32
    pad2 = "=" * (-len(rk["publicKey"]) % 4)
    raw2 = base64.urlsafe_b64decode(rk["publicKey"] + pad2)
    assert len(raw2) == 32
    assert len(rk["shortId"]) >= 2


def test_validate_rejects_fake_hex_key():
    cfg = build_config([make_user()], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    cfg["inbounds"][-1]["streamSettings"]["realitySettings"]["privateKey"] = "f" * 64
    ok, reason = validate_config(cfg)
    assert ok is False and "x25519" in reason


def test_ss_port_zero_skips_inbound():
    s = Settings()
    s.ss_port = 0
    cfg = build_config([make_user()], s, {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    tags = {i["tag"] for i in cfg["inbounds"]}
    assert "ss-in" not in tags


def test_ss_clients_carry_method_per_client():
    """xray 26.x: method must be inside each client entry."""
    s = Settings()
    cfg = build_config([make_user()], s, {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    ss = next(i for i in cfg["inbounds"] if i["tag"] == "ss-in")
    for c in ss["settings"]["clients"]:
        assert c["method"] == "aes-256-gcm"
        assert c["password"]


def test_disabled_users_excluded():
    u = make_user()
    u.enabled = False
    cfg = build_config([u], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    vless = next(i for i in cfg["inbounds"] if i["tag"] == "vless-ws")
    assert vless["settings"]["clients"] == []


def test_atomic_write_no_partial(tmp_path):
    cfg = build_config([make_user()], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    path = str(tmp_path / "xray-config.json")
    write_config(cfg, path)
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["log"]["loglevel"] == "warning"
    import os

    assert not os.path.exists(path + ".tmp")


def test_config_path_in_data_dir():
    assert config_path().endswith("xray-config.json")
    assert ".data" in config_path() or "data" in config_path()
