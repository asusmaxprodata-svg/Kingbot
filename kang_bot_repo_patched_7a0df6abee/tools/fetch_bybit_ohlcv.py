#!/usr/bin/env python3
"""
Bybit OHLCV fetcher (public REST). Saves to CSV for tuning/backtests.

Example:
  python tools/fetch_bybit_ohlcv.py --symbol BTCUSDT --timeframe 5m --days 60 --out data/BTCUSDT_5m.csv --category linear
  python tools/fetch_bybit_ohlcv.py --symbol BTCUSDT --timeframe 1h --days 180 --out data/BTCUSDT_1h.csv --testnet

Notes:
- Uses v5 public endpoint: /v5/market/kline
- Timeframe map: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
- We auto map '5m' -> '5', '15m' -> '15', '1h' -> '60'
"""

import argparse, time, math, sys, csv
from pathlib import Path
from datetime import datetime, timedelta, timezone
import requests

TF_MAP = {"1m":"1","3m":"3","5m":"5","15m":"15","30m":"30","1h":"60","2h":"120","4h":"240","6h":"360","12h":"720","1d":"D","1w":"W","1M":"M"}

def parse_timeframe(tf: str) -> str:
    tf = tf.strip().lower()
    if tf in TF_MAP: return TF_MAP[tf]
    if tf.endswith("m") and tf[:-1].isdigit():
        return tf[:-1]
    if tf.endswith("h") and tf[:-1].isdigit():
        return str(int(tf[:-1])*60)
    if tf in ["d","1d","day"]: return "D"
    raise SystemExit(f"Unsupported timeframe: {tf}")

def to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int, testnet=False, category="linear", limit=1000):
    base = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
    url = f"{base}/v5/market/kline"
    params = {
        "category": category,    # "linear" for USDT perpetuals
        "symbol": symbol,
        "interval": interval,
        "start": start_ms,
        "end": end_ms,
        "limit": limit
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("retCode") != 0:
        raise RuntimeError(f"Bybit error: {j.get('retMsg')} ({j.get('retCode')})")
    # Result format: list of list [start, open, high, low, close, volume, turnover]
    data = j["result"]["list"]
    # API returns most-recent-first; reverse to oldest-first
    data = list(reversed(data))
    return data

def write_csv(rows, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["start","open","high","low","close","volume"])
        for r in rows:
            # r: [start, open, high, low, close, volume, turnover]
            w.writerow([int(r[0]), r[1], r[2], r[3], r[4], r[5]])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--timeframe", required=True, help="e.g., 5m, 15m, 1h")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--testnet", action="store_true")
    ap.add_argument("--category", type=str, default="linear", help="linear|inverse|option")
    args = ap.parse_args()

    interval = parse_timeframe(args.timeframe)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    all_rows = []
    # Page in chunks of up to ~1000 bars
    # We step by bars*duration: kline count per request depends on interval
    # We'll compute step_ms from interval
    if interval in ["D","W","M"]:
        step_ms = 1000 * 24 * 3600 * 1000  # 1000 days rough for D; W/M will just be fewer bars
    else:
        # minutes
        minutes = int(interval)
        step_ms = minutes * 60 * 1000 * 1000  # 1000 bars * interval
    cur_start = to_ms(start)
    end_ms = to_ms(end)

    while cur_start < end_ms:
        cur_end = min(end_ms, cur_start + step_ms - 1)
        try:
            chunk = fetch_klines(args.symbol, interval, cur_start, cur_end, testnet=args.testnet, category=args.category)
            if not chunk:
                cur_start = cur_end + 1
                time.sleep(0.1)
                continue
            all_rows.extend(chunk)
            # move to next after last returned
            last_ts = int(chunk[-1][0])
            # avoid loops if API returns same segment
            if last_ts <= cur_start:
                cur_start = cur_end + 1
            else:
                cur_start = last_ts + 1
            time.sleep(0.2)  # polite rate limiting
        except Exception as e:
            print("fetch error:", e, "retry after 1s...", file=sys.stderr)
            time.sleep(1)
            cur_start = cur_end + 1

    # Deduplicate by timestamp
    dedup = {}
    for r in all_rows:
        dedup[int(r[0])] = r
    final_rows = [dedup[k] for k in sorted(dedup.keys())]
    write_csv(final_rows, Path(args.out))
    print(f"[FETCH] Wrote {len(final_rows)} bars to {args.out}")

if __name__ == "__main__":
    main()
