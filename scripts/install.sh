#!/usr/bin/env bash
# scripts/install.sh — local install (Linux): venv + pip + xray + .env + seed.
# Author: OpenCode
set -euo pipefail

echo "==> نصب NeonPanel (لوکال)"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> .env ساخته شد — مقادیر را ویرایش کن"
fi

if ! command -v xray >/dev/null 2>&1; then
  echo "==> دانلود Xray-core"
  XV="$(grep XRAY_VERSION .env | cut -d= -f2 | tail -n1 || echo 26.3.27)"
  wget -qO /tmp/x.zip "https://github.com/XTLS/Xray-core/releases/download/v${XV}/Xray-linux-64.zip"
  unzip -o /tmp/x.zip -d "$HOME/.local/bin" xray || sudo unzip -o /tmp/x.zip -d /usr/local/bin xray
  chmod +x "$HOME/.local/bin/xray" 2>/dev/null || sudo chmod +x /usr/local/bin/xray
fi

echo "==> آماده. اجرا: python -m app.main"
