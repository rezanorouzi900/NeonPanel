# scripts/bulk.py — create users from CSV (name,quota_gb,expires_days).
# Author: OpenCode
import csv
import sys

from sqlmodel import Session

from app.config import settings
from app.db import get_engine, init_db
from app.users import create_user


def main(path: str) -> None:
    engine = get_engine(settings.data_dir)
    init_db(engine)
    ok_count = fail_count = 0
    with open(path, newline="", encoding="utf-8") as f, Session(engine) as s:
        for row in csv.DictReader(f):
            _, code = create_user(
                s,
                row["name"],
                float(row.get("quota_gb") or 0),
                int(row.get("expires_days") or 0),
            )
            if code:
                print(f"SKIP {row['name']}: {code}")
                fail_count += 1
            else:
                print(f"OK   {row['name']}")
                ok_count += 1
    print(f"ساخته‌شده: {ok_count} / خطا: {fail_count}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("استفاده: python -m scripts.bulk users.csv")
        sys.exit(1)
    main(sys.argv[1])
