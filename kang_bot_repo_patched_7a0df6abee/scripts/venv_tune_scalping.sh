#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

# Aktifkan virtualenv (ubah path sesuai env Anda)
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

mkdir -p logs
python tools/tune_xgb_optuna.py --mode scalping --csv data/BTCUSDT_5m.csv --timeframe 5m --trials 150 --confidence_target 0.75 >> logs/cron_tune_scalping.log 2>&1
