# app/db.py
# Goal: engine + session + init + admin seeding + settings helpers.
# Author: OpenCode
from __future__ import annotations

import os
import secrets
import string

from passlib.context import CryptContext
from sqlmodel import Session, SQLModel, create_engine, select

from .models import Admin, Setting, User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

_engines: dict[str, object] = {}


def db_url(data_dir: str) -> str:
    os.makedirs(data_dir, exist_ok=True)
    return f"sqlite:///{data_dir}/panel.db"


def get_engine(data_dir: str = ".data"):
    if data_dir not in _engines:
        _engines[data_dir] = create_engine(db_url(data_dir), echo=False)
    return _engines[data_dir]


def init_db(engine) -> None:
    os.makedirs(os.path.dirname(engine.url.database) or ".", exist_ok=True)
    SQLModel.metadata.create_all(engine)


def random_password(n: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def seed_admin(session: Session, username: str, password: str) -> str | None:
    """Create the first admin if missing. Return a generated password if env was empty."""
    admin = session.exec(select(Admin).where(Admin.username == username)).first()
    if admin:
        return None
    generated: str | None = None
    if not password:
        generated = random_password(12)
        password = generated
    session.add(Admin(username=username, pass_hash=pwd.hash(password)))
    session.commit()
    return generated


def get_setting(session: Session, key: str, default: str = "") -> str:
    row = session.get(Setting, key)
    return row.value if row and row.value else default


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row:
        row.value = value
        row.updated_at = __import__("datetime").datetime.utcnow()
        session.add(row)
    else:
        session.add(Setting(key=key, value=value))
    session.commit()


def get_user_by_name(session: Session, name: str) -> User | None:
    return session.exec(select(User).where(User.name == name)).first()


def get_user_by_token(session: Session, token: str) -> User | None:
    return session.exec(select(User).where(User.sub_token == token)).first()
