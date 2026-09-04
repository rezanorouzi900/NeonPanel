# app/reset_admin.py — CLI: reset admin password (FAQ #5).
# Author: OpenCode
import sys

from sqlmodel import Session

from app.config import settings
from app.db import get_engine, init_db, pwd, random_password
from app.models import Admin


def main(username: str) -> None:
    engine = get_engine(settings.data_dir)
    init_db(engine)
    new = random_password(12)
    with Session(engine) as s:
        adm = s.query(Admin).where(Admin.username == username).first()
        if not adm:
            adm = Admin(username=username, pass_hash="")
            s.add(adm)
        adm.pass_hash = pwd.hash(new)
        s.add(adm)
        s.commit()
    print(f"رمز جدید ادمین «{username}»: {new} (همین‌جا ذخیره کن)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "admin")
