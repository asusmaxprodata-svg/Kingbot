
# Walk-Forward Backtest Patch

Tambahkan dua file berikut ke project `kang_bot` kamu:
- `core/backtest_walkforward.py`
- `tools/run_walkforward.py`

## Cara pakai
```bash
# API (testnet; fallback ke data sintetis jika fetch gagal)
python tools/run_walkforward.py --mode hybrid --testnet

# CSV lokal (wajib: start,open,high,low,close)
python tools/run_walkforward.py --mode swing --source csv --csv data/BTCUSDT_15m.csv
```

Output:
- `reports/walk_<mode>_<ts>.json` → ringkasan (trades, winrate, pnl_sum, equity_final)
- `reports/walk_<mode>_<ts>.csv`  → detail setiap trade.
