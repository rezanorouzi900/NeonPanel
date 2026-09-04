# tests/test_backup.py — make → verify → corrupt → restore cycle.
# Author: OpenCode
from __future__ import annotations

import io
import os
import sqlite3
import zipfile


def _login(client):
    r = client.post("/api/auth/login", json={"username": "RXpanel", "password": "test-pass-123"})
    return {"Authorization": f"Bearer {r.json()['data']['access']}"}


def test_backup_verify_ok(client):
    h = _login(client)
    client.post("/api/users", json={"name": "bkp-user"}, headers=h)
    r = client.get("/api/backup", headers=h)
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert "panel.db" in z.namelist()


def test_verify_rejects_garbage():
    from app.backup import verify_backup

    ok, why = verify_backup(b"not a zip")
    assert ok is False
    ok2, _ = verify_backup(b"")
    assert ok2 is False


def test_verify_rejects_zip_without_db():
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("random.txt", "hi")
    from app.backup import verify_backup

    ok, _ = verify_backup(buf.getvalue())
    assert ok is False


def test_restore_roundtrip(client, tmp_path):
    h = _login(client)
    client.post("/api/users", json={"name": "restore-me"}, headers=h)
    blob = client.get("/api/backup", headers=h).content
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    from app.backup import restore_backup

    ok, reason = restore_backup(blob, str(fresh))
    assert ok, reason
    conn = sqlite3.connect(str(fresh / "panel.db"))
    names = [r[0] for r in conn.execute("SELECT name FROM user")]
    conn.close()
    assert "restore-me" in names


def test_restore_rolls_back_on_corrupt(client, tmp_path):
    from app.backup import restore_backup

    data = str(tmp_path / "d1")
    os.makedirs(data, exist_ok=True)
    # a valid zip that lacks panel.db → verify fails → restore must refuse
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("random.txt", "no db here")
    blob = buf.getvalue()
    ok2, _ = restore_backup(blob, data)
    assert ok2 is False
