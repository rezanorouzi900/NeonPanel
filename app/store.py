# app/store.py
# Persistence + live registry: configs, groups, usage, per-IP concurrency.
# Author: OpenCode
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone
from pathlib import Path

from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

DATA_DIR = os.getenv("DATA_DIR", ".data")
DEFAULT_ADMIN = os.getenv("ADMIN_USER", "RXpanel")
DEFAULT_PASS = os.getenv("ADMIN_PASS", "")
_lock = threading.Lock()
_state: dict = {"configs": {}, "groups": {}, "admin_hash": "", "seq": 1}


def _now() -> float:
    return time.time()


def _path() -> Path:
    return Path(DATA_DIR) / "state.json"


def load() -> None:
    global _state
    os.makedirs(DATA_DIR, exist_ok=True)
    p = _path()
    if p.exists():
        try:
            _state = json.loads(p.read_text(encoding="utf-8"))
            _state.setdefault("configs", {})
            _state.setdefault("groups", {})
            _state.setdefault("admin_hash", "")
            _state.setdefault("seq", 1)
            return
        except (json.JSONDecodeError, OSError):
            pass
    _state["admin_hash"] = pwd.hash(DEFAULT_PASS) if DEFAULT_PASS else ""
    _state["need_admin_print"] = not DEFAULT_PASS
    save()


def save() -> None:
    with _lock:
        _path().write_text(json.dumps(_state, ensure_ascii=False, indent=1),
                           encoding="utf-8")


def ensure_admin() -> str | None:
    """Return a generated password once when ADMIN_PASS was empty."""
    if _state.get("admin_hash"):
        return None
    generated = secrets.token_urlsafe(9)
    _state["admin_hash"] = pwd.hash(generated)
    _state.pop("need_admin_print", None)
    save()
    return generated


def check_admin(password: str) -> bool:
    h = _state.get("admin_hash", "")
    try:
        return bool(h) and pwd.verify(password, h)
    except Exception:
        return False


def set_admin_password(new: str) -> None:
    _state["admin_hash"] = pwd.hash(new)
    save()


# ---------------- configs ----------------

def _new_row(name: str) -> dict:
    with _lock:
        n = _state["seq"]
        _state["seq"] = n + 1
    return {
        "id": n, "name": name, "uuid": str(uuid_mod.uuid4()),
        "enabled": True, "note": "",
        "quota_bytes": 0, "speed_mbps": 0, "max_ips": 0,
        "expires_at": None,
        "used_bytes": 0, "created_at": _now(),
    }


def list_configs(q: str = "") -> list[dict]:
    items = list(_state["configs"].values())
    if q:
        items = [c for c in items if q.lower() in c["name"].lower()]
    return sorted(items, key=lambda c: c["id"])


def get_config(cid: int) -> dict | None:
    return _state["configs"].get(str(cid))


def get_by_uuid(uid: str) -> dict | None:
    for c in _state["configs"].values():
        if c["uuid"] == uid:
            return c
    return None


def create_config(name: str, quota_gb: float = 0, expires_days: int = 0,
                  speed_mbps: int = 0, max_ips: int = 0, note: str = "") -> tuple[dict | None, str]:
    name = " ".join(name.split())
    if not (2 <= len(name) <= 32):
        return None, "BAD_INPUT"
    if any(c["name"] == name for c in _state["configs"].values()):
        return None, "DUPLICATE"
    cfg = _new_row(name)
    cfg["quota_bytes"] = int(quota_gb * 1024**3)
    cfg["speed_mbps"] = speed_mbps
    cfg["max_ips"] = max_ips
    cfg["note"] = note
    if expires_days:
        cfg["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=expires_days)).timestamp()
    _state["configs"][str(cfg["id"])] = cfg
    save()
    return cfg, ""


def patch_config(cid: int, **fields) -> tuple[dict | None, str]:
    cfg = get_config(cid)
    if not cfg:
        return None, "NOT_FOUND"
    allowed = {"enabled", "note", "quota_bytes", "speed_mbps", "max_ips",
               "expires_at", "quota_gb", "expires_days", "name"}
    for k, v in fields.items():
        if k not in allowed:
            return None, "BAD_INPUT"
        if k == "quota_gb":
            cfg["quota_bytes"] = int(v * 1024**3)
        elif k == "expires_days":
            cfg["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=v)).timestamp() if v else None
        elif k == "name":
            v2 = " ".join(v.split())
            if not (2 <= len(v2) <= 32) or any(c["name"] == v2 and c["id"] != cid for c in _state["configs"].values()):
                return None, "BAD_INPUT"
            cfg["name"] = v2
        else:
            cfg[k] = v
    save()
    return cfg, ""


def delete_config(cid: int) -> str:
    if str(cid) not in _state["configs"]:
        return "NOT_FOUND"
    del _state["configs"][str(cid)]
    for g in _state["groups"].values():
        g["members"] = [m for m in g["members"] if m != cid]
    save()
    return ""


def reset_usage(cid: int, new_uuid: bool = False) -> tuple[dict | None, str]:
    cfg = get_config(cid)
    if not cfg:
        return None, "NOT_FOUND"
    cfg["used_bytes"] = 0
    if new_uuid:
        cfg["uuid"] = str(uuid_mod.uuid4())
    save()
    return cfg, ""


def usable(cfg: dict) -> tuple[bool, str]:
    if not cfg.get("enabled"):
        return False, "disabled"
    exp = cfg.get("expires_at")
    if exp and exp < _now():
        return False, "expired"
    qb = cfg.get("quota_bytes", 0)
    if qb and cfg.get("used_bytes", 0) >= qb:
        return False, "quota_full"
    return True, "ok"


def add_usage(cfg_id: str, n: int) -> None:
    cfg = _state["configs"].get(cfg_id)
    if cfg:
        cfg["used_bytes"] = cfg.get("used_bytes", 0) + n


# ---------------- groups ----------------

def create_group(name: str, member_ids: list[int], password: str = "") -> tuple[dict | None, str]:
    name = " ".join(name.split())
    if not (2 <= len(name) <= 32):
        return None, "BAD_INPUT"
    if any(g["name"] == name for g in _state["groups"].values()):
        return None, "DUPLICATE"
    members = [m for m in member_ids if get_config(m)]
    with _lock:
        gid = _state["seq"]
        _state["seq"] = gid + 1
    g = {"id": gid, "name": name, "members": members, "sub_path": secrets.token_urlsafe(12),
         "password": password, "created_at": _now()}
    _state["groups"][str(gid)] = g
    save()
    return g, ""


def list_groups() -> list[dict]:
    return sorted(_state["groups"].values(), key=lambda g: g["id"])


def get_group(gid: int) -> dict | None:
    return _state["groups"].get(str(gid))


def get_group_by_path(path: str) -> dict | None:
    for g in _state["groups"].values():
        if g["sub_path"] == path:
            return g
    return None


def delete_group(gid: int) -> str:
    if str(gid) not in _state["groups"]:
        return "NOT_FOUND"
    del _state["groups"][str(gid)]
    save()
    return ""


def patch_group(gid: int, **fields) -> tuple[dict | None, str]:
    g = get_group(gid)
    if not g:
        return None, "NOT_FOUND"
    if "name" in fields:
        v = " ".join(fields.pop("name").split())
        if not (2 <= len(v) <= 32):
            return None, "BAD_INPUT"
        g["name"] = v
    if "members" in fields:
        g["members"] = [m for m in fields["members"] if get_config(m)]
    if "password" in fields:
        g["password"] = fields["password"]
    save()
    return g, ""


# ---------------- live connections registry ----------------

_live: dict[str, dict] = {}  # uuid -> {"ips": set, "since": ts}


def live_start(uid: str, ip: str) -> bool:
    """Track concurrent IP per config; enforce max_ips. False = rejected."""
    cfg = get_by_uuid(uid)
    if not cfg:
        return False
    slot = _live.setdefault(uid, {"ips": set(), "since": _now()})
    max_ips = cfg.get("max_ips", 0)
    if max_ips and ip not in slot["ips"] and len(slot["ips"]) >= max_ips:
        return False
    slot["ips"].add(ip)
    return True


def live_end(uid: str, ip: str) -> None:
    slot = _live.get(uid)
    if slot:
        slot["ips"].discard(ip)
        if not slot["ips"]:
            _live.pop(uid, None)


def live_summary() -> list[dict]:
    return [{"uuid": u, "ips": len(s["ips"]), "since": int(s["since"])}
            for u, s in _live.items()]
