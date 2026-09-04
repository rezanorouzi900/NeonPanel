# app/users.py
# Goal: VPN-user CRUD + validation + quota/enabled/expire logic (APPENDIX A.6).
# Author: OpenCode
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlmodel import Session, select

from .models import TrafficLog, User

NAME_RE = re.compile(r"^[a-zA-Z0-9-_ء-ي ]{2,32}$")


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name or ""))


def create_user(
    session: Session,
    name: str,
    quota_gb: float = 0,
    expires_days: int = 0,
    enabled: bool = True,
    note: str = "",
) -> tuple[User | None, str]:
    """Create a user. Return (user, err) — err is a stable code or ''."""
    name = normalize_name(name)
    if not valid_name(name):
        return None, "BAD_INPUT"
    if session.exec(select(User).where(User.name == name)).first():
        return None, "DUPLICATE"
    if not (0 <= quota_gb <= 10000):
        return None, "BAD_INPUT"
    if not (0 <= expires_days <= 3650):
        return None, "BAD_INPUT"
    user = User(
        name=name,
        uuid=str(uuid4()),
        trojan_pass=secrets.token_hex(8),
        ss_pass=secrets.token_hex(8),
        sub_token=secrets.token_urlsafe(16),
        quota_gb=quota_gb,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=expires_days)).replace(tzinfo=None)
        if expires_days
        else None,
        enabled=enabled,
        note=note or "",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, ""


def patch_user(session: Session, user_id: int, **fields) -> tuple[User | None, str]:
    user = session.get(User, user_id)
    if not user:
        return None, "NOT_FOUND"
    allowed = {"note", "quota_gb", "expires_at", "enabled", "expires_days"}
    for key, val in fields.items():
        if key not in allowed:
            return None, "BAD_INPUT"
        if key == "expires_days":
            user.expires_at = (
                (datetime.now(timezone.utc) + timedelta(days=val)).replace(tzinfo=None) if val else None
            )
        elif key == "quota_gb":
            if not (0 <= val <= 10000):
                return None, "BAD_INPUT"
            user.quota_gb = val
        else:
            setattr(user, key, val)
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, ""


def delete_user(session: Session, user_id: int, wipe: bool = False) -> str:
    user = session.get(User, user_id)
    if not user:
        return "NOT_FOUND"
    if wipe:
        for log in session.exec(select(TrafficLog).where(TrafficLog.user_id == user_id)).all():
            session.delete(log)
    session.delete(user)
    session.commit()
    return ""


def reset_usage(session: Session, user_id: int, new_token: bool = False) -> tuple[User | None, str]:
    user = session.get(User, user_id)
    if not user:
        return None, "NOT_FOUND"
    user.used_bytes = 0
    cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    for log in session.exec(select(TrafficLog).where(TrafficLog.user_id == user_id)).all():
        if log.day >= cutoff:
            session.delete(log)
    if new_token:
        user.sub_token = secrets.token_urlsafe(16)
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, ""
