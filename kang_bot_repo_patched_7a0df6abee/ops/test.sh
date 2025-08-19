#!/usr/bin/env bash
set -euo pipefail

# Dry-run 24 jam (testnet) dengan notifikasi error ke Telegram
export BYBIT_TESTNET=true
export LOG_LEVEL=INFO
export LOG_JSON=1

python -m kingbot --mode testnet --dry-run --duration 86400 || {
  echo "[ops/test.sh] runner exited with error" >&2
  python -c 'from core.notifier import telegram_send; telegram_send("[kang_bot] Dry-run gagal — cek logs.")' || true
  exit 1
}

echo "[ops/test.sh] Dry-run selesai"
