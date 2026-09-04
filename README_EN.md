# NeonPanel — Admin panel for Xray-based VPN (remix of rezanorouzi900/-)

## Features
- 4 protocols: VLESS / VMess / Trojan (WS) + Shadowsocks + Reality
- Subscriptions: base64 / Clash / Sing-box / JSON with `Subscription-Userinfo`
- Auto domain detection (Host / X-Forwarded-Host / Railway / Cloudflare tunnel)
- Telegram MTProto proxy (optional, one-click toggle)
- Dark neon UI, Persian (RTL) + English, instant switch
- JWT auth + bcrypt + rate limits + security headers
- Deploy: Docker / Railway one-click

## Quick start (Docker)
```bash
cp .env.example .env
docker compose up -d
# panel: http://localhost:8080
```

## Deploy on Railway
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?repo=https://github.com/rezanorouzi900/NeonPanel)
Set `ADMIN_USER` and `ADMIN_PASS` variables — done.

## Full docs
See `docs/` (Persian, with English API examples in `docs/API.md`).

License: MIT
