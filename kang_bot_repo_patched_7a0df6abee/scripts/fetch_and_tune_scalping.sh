#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
[ -f ".venv/bin/activate" ] && source .venv/bin/activate
mkdir -p logs data
python tools/fetch_bybit_ohlcv.py --symbol BTCUSDT --timeframe 5m --days 30 --out data/BTCUSDT_5m.csv --category linear
python tools/tune_xgb_optuna.py --mode scalping --csv data/BTCUSDT_5m.csv --timeframe 5m --trials 150 --confidence_target 0.75 >> logs/cron_tune_scalping.log 2>&1
