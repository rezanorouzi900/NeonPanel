# tests/test_xray_gen.py — generated config: tags, reality keys, SS skip, atomic write.
# Author: OpenCode
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from app.config import Settings
from app.models import User
from app.xray_config import build_config, validate_config, write_config


def make_user(name="reza-01"):
    return User(id=1, name=name, uuid="11111111-2222-3333-4444-555555555555",
                trojan_pass="tp", ss_pass="sp", sub_token="tok",
                expires_at=datetime.utcnow() + timedelta(days=30))


def test_config_has_required_tags():
    cfg = build_config([make_user()], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    tags = {i["tag"] for i in cfg["inbounds"]}
    assert {"vless-ws", "vmess-ws", "trojan-ws", "reality-in", "api-in"} <= tags


def test_reality_settings_present():
    cfg = build_config([make_user()], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    reality = [i for i in cfg["inbounds"] if i["tag"] == "reality-in"][0]
    rs = reality["streamSettings"]["realitySettings"]
    assert rs["privateKey"] and rs["shortIds"]
    assert rs["serverNames"] == ["www.microsoft.com"]
    assert rs["dest"] == "www.microsoft.com:443"


def test_ss_port_zero_skips_inbound():
    s = Settings()
    s.ss_port = 0
    cfg = build_config([make_user()], s, {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    tags = {i["tag"] for i in cfg["inbounds"]}
    assert "ss-in" not in tags


def test_disabled_users_excluded():
    u = make_user()
    u.enabled = False
    cfg = build_config([u], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    vless = [i for i in cfg["inbounds"] if i["tag"] == "vless-ws"][0]
    assert vless["settings"]["clients"] == []


def test_validate_ok_and_missing_tag():
    cfg = build_config([make_user()], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    assert validate_config(cfg)[0] is True
    bad = {"inbounds": [{"tag": "x", "port": 1}]}
    assert validate_config(bad)[0] is False


def test_atomic_write_no_partial(tmp_path):
    cfg = build_config([make_user()], Settings(), {"vless": "/a", "vmess": "/b", "trojan": "/c"})
    path = str(tmp_path / "xray-config.json")
    write_config(cfg, path)
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)  # must parse — no partial file
    assert loaded["log"]["loglevel"] == "warning"
    assert not os.path.exists(path + ".tmp")
