# app/config.py
# Goal: read & validate all environment variables into one Settings object.
# Author: OpenCode
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (ValueError, AttributeError):
        return default


@dataclass
class Settings:
    """Central config loaded once at startup from environment variables."""

    project_name: str = field(default_factory=lambda: _env("PROJECT_NAME", "NeonPanel"))
    version: str = field(default_factory=lambda: _env("VERSION", "1.0.0"))
    admin_user: str = field(default_factory=lambda: _env("ADMIN_USER", "RXpanel"))
    admin_pass: str = field(default_factory=lambda: _env("ADMIN_PASS", ""))
    jwt_secret: str = field(default_factory=lambda: _env("JWT_SECRET", ""))
    port: int = field(default_factory=lambda: _env_int("PORT", 8080))
    public_domain: str = field(default_factory=lambda: _env("PUBLIC_DOMAIN", ""))
    allowed_hosts: str = field(default_factory=lambda: _env("ALLOWED_HOSTS", ""))
    reality_port: int = field(default_factory=lambda: _env_int("REALITY_PORT", 8443))
    reality_sni: str = field(default_factory=lambda: _env("REALITY_SNI", "www.microsoft.com"))
    ss_port: int = field(default_factory=lambda: _env_int("SS_PORT", 8388))
    mt_enabled: bool = field(default_factory=lambda: _env("MT_ENABLED", "0") == "1")
    mt_port: int = field(default_factory=lambda: _env_int("MT_PORT", 4433))
    cf_mode: str = field(default_factory=lambda: _env("CF_MODE", "off"))
    cf_token: str = field(default_factory=lambda: _env("CF_TUNNEL_TOKEN", ""))
    xray_version: str = field(default_factory=lambda: _env("XRAY_VERSION", "26.3.27"))
    data_dir: str = field(default_factory=lambda: _env("DATA_DIR", ".data"))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "info"))
    cors_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", ""))
    need_random_admin: bool = False

    def validate(self) -> None:
        """Raise ValueError with a Persian message when config is invalid."""
        if not (1 <= self.port <= 65535):
            raise ValueError("پورت باید بین ۱ تا ۶۵۵۳۵ باشد")
        if self.cf_mode not in ("off", "token", "quick"):
            raise ValueError("CF_MODE باید یکی از off/token/quick باشد")
        if self.cf_mode == "token" and not self.cf_token:
            raise ValueError("حالت token برای تانل انتخاب شده ولی CF_TUNNEL_TOKEN خالی است")
        if self.admin_pass == "":
            self.need_random_admin = True


settings = Settings()
