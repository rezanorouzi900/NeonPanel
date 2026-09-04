# app/supervisor.py
# Goal: child-process manager for xray / cloudflared / mtproto with backoff restarts.
# Author: OpenCode
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from threading import Thread

from .config import settings

log = logging.getLogger("supervisor")

BACKOFF = [1, 2, 4, 8, 15, 30, 60]


class Child:
    """One managed child process with restart backoff."""

    def __init__(self, name: str, cmd: list[str], env: dict | None = None):
        self.name = name
        self.cmd = cmd
        self.env = env
        self.proc: subprocess.Popen | None = None
        self.fails = 0
        self.started_at = 0.0
        self.enabled = True

    def start(self) -> bool:
        if not self.enabled:
            return False
        try:
            self.proc = subprocess.Popen(
                self.cmd,
                env={**os.environ, **(self.env or {})},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.started_at = time.time()
            return True
        except OSError as e:
            log.warning("start %s failed: %s", self.name, e)
            return False

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def uptime(self) -> int:
        return int(time.time() - self.started_at) if self.alive() else 0

    def status(self) -> str:
        if not self.enabled:
            return "off"
        return "up" if self.alive() else "down"

    def stop(self, grace: int = 5) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def restart(self) -> bool:
        self.stop()
        ok = self.start()
        if ok:
            self.fails = 0
        return ok


class Supervisor:
    """Start/keep xray + optional cloudflared/mtproto; poll every 5s."""

    def __init__(self):
        self.children: dict[str, Child] = {}
        self._thread: Thread | None = None
        self._running = False
        self._boot = time.time()

    def setup(self) -> None:
        cfg_path = os.path.join(settings.data_dir, "xray-config.json")
        self.children["xray"] = Child("xray", ["xray", "run", "-c", cfg_path])
        if settings.cf_mode == "token" and settings.cf_token:
            self.children["tunnel"] = Child(
                "tunnel",
                ["cloudflared", "tunnel", "--no-autoupdate", "run", "--token", settings.cf_token],
            )
        elif settings.cf_mode == "quick":
            self.children["tunnel"] = Child(
                "tunnel", ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{settings.port}"]
            )
        if settings.mt_enabled:
            self.children["mtproto"] = Child("mtproto", [sys.executable, "-m", "app.mtproto"])

    def start(self) -> None:
        self.setup()
        self._running = True
        self._boot = time.time()
        for child in self.children.values():
            child.start()
        self._thread = Thread(target=self._watch, daemon=True)
        self._thread.start()

    def _watch(self) -> None:
        while self._running:
            for child in self.children.values():
                if child.enabled and not child.alive():
                    wait = BACKOFF[min(child.fails, len(BACKOFF) - 1)]
                    log.info("%s down — restarting in %ss", child.name, wait)
                    time.sleep(wait)
                    if child.restart():
                        child.fails = 0
                    else:
                        child.fails += 1
            time.sleep(5)

    def status(self) -> dict:
        return {
            "xray": self.children.get("xray").status() if "xray" in self.children else "off",
            "tunnel": self.children.get("tunnel").status() if "tunnel" in self.children else "off",
            "mtproto": self.children.get("mtproto").status() if "mtproto" in self.children else "off",
            "uptime": int(time.time() - self._boot),
        }

    def reload_xray(self) -> bool:
        """Graceful xray restart (SIGHUP unsupported → restart with 5s drain)."""
        child = self.children.get("xray")
        if child is None:
            return False
        child.stop(grace=5)
        return child.start()

    def stop(self) -> None:
        self._running = False
        for child in self.children.values():
            child.stop()


supervisor = Supervisor()
