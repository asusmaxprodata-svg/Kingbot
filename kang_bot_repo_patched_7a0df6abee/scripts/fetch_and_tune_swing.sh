#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
[ -f ".venv/bin/activate" ] && source .venv/bin/activate
mkdir -p logs data
python tools/fetch_bybit_ohlcv.py --symbol BTCUSDT --timeframe 1h --days 180 --out data/BTCUSDT_1h.csv --category linear
python tools/tune_xgb_optuna.py --mode swing --csv data/BTCUSDT_1h.csv --timeframe 1h --trials 150 --confidence_target 0.75 >> logs/cron_tune_swing.log 2>&1
