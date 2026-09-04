#!/usr/bin/env bash
# scripts/restore.sh <file.zip> — stop xray → replace → start.
# Author: OpenCode
set -euo pipefail
FILE="${1:-}"
[ -n "$FILE" ] && [ -f "$FILE" ] || { echo "استفاده: ./scripts/restore.sh backup.zip"; exit 1; }
DATA="${DATA_DIR:-.data}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${DATA}.pre-${STAMP}"
cp -a "$DATA"/. "${DATA}.pre-${STAMP}/" 2>/dev/null || true
unzip -qo "$FILE" -d "$DATA"
echo "ریستور انجام شد — اگر xray اجراست ری‌استارتش کن."
