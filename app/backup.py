# app/backup.py
# Goal: zip/unzip backup of db + paths + secrets with verify & rollback (APPENDIX A.13).
# Author: OpenCode
from __future__ import annotations

import io
import os
import shutil
import zipfile
from datetime import datetime

FILES = ["panel.db", "paths.json", "secret.txt", "jwt_secret", "settings-export.json"]


def make_backup(data_dir: str) -> bytes:
    """Zip the data dir (no logs) into in-memory bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            p = os.path.join(data_dir, name)
            if os.path.isfile(p):
                z.write(p, arcname=name)
    return buf.getvalue()


def verify_backup(blob: bytes) -> tuple[bool, str]:
    """Check zip magic bytes + presence of panel.db."""
    if not blob:
        return False, "فایل بکاپ خالی است"
    if blob[:2] != b"PK":
        return False, "فایل بکاپ معتبر نیست (zip نیست)"
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = z.namelist()
            if "panel.db" not in names:
                return False, "بکاپ دیتابیس ندارد"
            return True, ""
    except zipfile.BadZipFile:
        return False, "فایل zip خراب است"


def restore_backup(blob: bytes, data_dir: str) -> tuple[bool, str]:
    """Stop-safe restore: auto-backup current data first, then replace files."""
    ok, reason = verify_backup(blob)
    if not ok:
        return False, reason
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    rollback = os.path.join(data_dir, f"rollback-{stamp}")
    os.makedirs(rollback, exist_ok=True)
    for name in FILES:
        p = os.path.join(data_dir, name)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(rollback, name))
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for name in FILES:
                if name in z.namelist():
                    z.extract(name, data_dir)
                    target = os.path.join(data_dir, name)
                    if name in ("secret.txt", "jwt_secret"):
                        os.chmod(target, 0o600)
        return True, ""
    except (OSError, zipfile.BadZipFile) as e:
        # rollback
        for name in FILES:
            src = os.path.join(rollback, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(data_dir, name))
        return False, f"ریستور شکست خورد: {e}"
