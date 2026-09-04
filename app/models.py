# app/models.py
# Goal: SQLModel tables — admins, users, traffic_log, settings (PART 2 §6).
# Author: OpenCode
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Admin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=64)
    pass_hash: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=32)
    uuid: str = Field(unique=True, index=True, max_length=36)
    trojan_pass: str = Field(max_length=64)
    ss_pass: str = Field(max_length=64)
    quota_gb: float = Field(default=0)
    used_bytes: int = Field(default=0)
    expires_at: Optional[datetime] = None
    enabled: bool = True
    sub_token: str = Field(unique=True, index=True, max_length=43)
    note: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TrafficLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    day: str = Field(index=True, max_length=10)  # YYYY-MM-DD
    up_bytes: int = 0
    down_bytes: int = 0


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True, max_length=64)
    value: str = Field(default="", max_length=4000)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
