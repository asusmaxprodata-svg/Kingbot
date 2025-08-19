# Cron Templates (UTC)

Contoh jadwal **tuning harian** (sesuaikan path Python dan zona waktu VPS Anda).
Tambahkan ke crontab dengan `crontab -e`.

## Prasyarat
- Virtualenv/conda aktifkan via wrapper script (opsional).
- Log akan disimpan ke `logs/` (pastikan folder ada).

## Template (letakkan ini di crontab)

# ===== Scalping (5m) =====
10 3 * * *  cd ~/kang_bot && /usr/bin/python3 tools/tune_xgb_optuna.py --mode scalping --csv data/BTCUSDT_5m.csv --timeframe 5m --trials 150 --confidence_target 0.75 >> logs/cron_tune_scalping.log 2>&1

# ===== Hybrid (15m) =====
40 3 * * *  cd ~/kang_bot && /usr/bin/python3 tools/tune_xgb_optuna.py --mode hybrid --csv data/BTCUSDT_15m.csv --timeframe 15m --trials 150 --confidence_target 0.75 >> logs/cron_tune_hybrid.log 2>&1

# ===== Swing (1h) =====
10 4 * * *  cd ~/kang_bot && /usr/bin/python3 tools/tune_xgb_optuna.py --mode swing --csv data/BTCUSDT_1h.csv --timeframe 1h --trials 150 --confidence_target 0.75 >> logs/cron_tune_swing.log 2>&1

## Tips
- Gunakan jam sepi server (tidak bentrok dengan run bot).
- Pastikan `data/*.csv` rutin di-update (fetcher Anda).
- Jika pakai virtualenv:
  10 3 * * *  cd ~/kang_bot && /bin/bash scripts/venv_tune_scalping.sh

---

## Fetch dulu, lalu tuning (otomatis)
Contoh (UTC):
```
# Update data 5m 30 hari, lalu tuning scalping
5 3 * * *  cd ~/kang_bot && /usr/bin/python3 tools/fetch_bybit_ohlcv.py --symbol BTCUSDT --timeframe 5m --days 30 --out data/BTCUSDT_5m.csv --category linear && /usr/bin/python3 tools/tune_xgb_optuna.py --mode scalping --csv data/BTCUSDT_5m.csv --timeframe 5m --trials 150 --confidence_target 0.75 >> logs/cron_tune_scalping.log 2>&1

# Update data 15m 90 hari, lalu tuning hybrid
35 3 * * *  cd ~/kang_bot && /usr/bin/python3 tools/fetch_bybit_ohlcv.py --symbol BTCUSDT --timeframe 15m --days 90 --out data/BTCUSDT_15m.csv --category linear && /usr/bin/python3 tools/tune_xgb_optuna.py --mode hybrid --csv data/BTCUSDT_15m.csv --timeframe 15m --trials 150 --confidence_target 0.75 >> logs/cron_tune_hybrid.log 2>&1

# Update data 1h 180 hari, lalu tuning swing
5 4 * * *  cd ~/kang_bot && /usr/bin/python3 tools/fetch_bybit_ohlcv.py --symbol BTCUSDT --timeframe 1h --days 180 --out data/BTCUSDT_1h.csv --category linear && /usr/bin/python3 tools/tune_xgb_optuna.py --mode swing --csv data/BTCUSDT_1h.csv --timeframe 1h --trials 150 --confidence_target 0.75 >> logs/cron_tune_swing.log 2>&1
```
