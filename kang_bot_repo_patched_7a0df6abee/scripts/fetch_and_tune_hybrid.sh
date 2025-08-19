#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
[ -f ".venv/bin/activate" ] && source .venv/bin/activate
mkdir -p logs data
python tools/fetch_bybit_ohlcv.py --symbol BTCUSDT --timeframe 15m --days 90 --out data/BTCUSDT_15m.csv --category linear
python tools/tune_xgb_optuna.py --mode hybrid --csv data/BTCUSDT_15m.csv --timeframe 15m --trials 150 --confidence_target 0.75 >> logs/cron_tune_hybrid.log 2>&1
