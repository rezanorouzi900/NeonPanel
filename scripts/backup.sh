#!/usr/bin/env bash
# scripts/backup.sh — zip .data with timestamp.
# Author: OpenCode
set -euo pipefail
DATA="${DATA_DIR:-.data}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="backup-${STAMP}.zip"
[ -d "$DATA" ] || { echo "پوشه داده پیدا نشد: $DATA"; exit 1; }
zip -q -r "$OUT" "$DATA" -x "*.log*"
echo "بکاپ ساخته شد: $OUT (حتماً بیرون از سرور نگه دار)"
