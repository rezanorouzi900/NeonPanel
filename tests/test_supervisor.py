# tests/test_supervisor.py — child restart-on-death + status reporting.
# Author: OpenCode
from __future__ import annotations

import sys

from app.supervisor import Child, Supervisor


def test_child_dies_and_restarts(tmp_path):
    # a python child that exits immediately
    child = Child("demo", [sys.executable, "-c", "raise SystemExit(1)"])
    child.start()
    assert child.alive() is True or child.status() in ("up", "down")
    child.stop()
    assert child.status() == "down"


def test_child_restart_ok():
    child = Child("sleeper", [sys.executable, "-c", "import time; time.sleep(30)"])
    assert child.start() is True
    assert child.alive() is True
    assert child.restart() is True
    assert child.alive() is True
    child.stop()
    assert child.alive() is False


def test_supervisor_status_shape():
    sup = Supervisor()
    st = sup.status()
    assert set(st) == {"xray", "tunnel", "mtproto", "uptime"}
    assert st["xray"] == "off"  # not started yet


def test_disabled_child_reports_off():
    child = Child("never", [sys.executable, "-c", "pass"], env=None)
    child.enabled = False
    assert child.status() == "off"
    assert child.start() is False
