import sys, json, time
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from core.logger import get_logger
from core.utils import load_json
from core.ai_signal import combine_signals

log = get_logger("walkforward")

def _ensure_features(df: pd.DataFrame) -> pd.DataFrame:
    if "ema_fast" not in df.columns:
        df["ema_fast"] = df["close"].rolling(10).mean().bfill()
    if "ema_slow" not in df.columns:
        df["ema_slow"] = df["close"].rolling(30).mean().bfill()
    if "macd_hist" not in df.columns:
        df["macd_hist"] = df["close"].diff().rolling(12).mean().fillna(0)
    if "vol" not in df.columns:
        df["vol"] = df["close"].pct_change().abs().rolling(20).mean().fillna(0.002)
    return df

def _hit_tpsl_path(high: np.ndarray, low: np.ndarray, entry: float, tp: float, sl: float, side: str):
    tp_price = entry * (1 + tp) if side == "BUY" else entry * (1 - tp)
    sl_price = entry * (1 - sl) if side == "BUY" else entry * (1 + sl)
    for i in range(len(high)):
        if side == "BUY":
            if high[i] >= tp_price: return "TP", i+1
            if low[i]  <= sl_price: return "SL", i+1
        else:
            if low[i]  <= tp_price: return "TP", i+1
            if high[i] >= sl_price: return "SL", i+1
    return "NONE", len(high)

def _simulate_trade_path(df_future: pd.DataFrame, entry: float, side: str, tp: float, sl: float) -> Dict[str, Any]:
    res, bars = _hit_tpsl_path(df_future["high"].values, df_future["low"].values, entry, tp, sl, side)
    if res == "TP":
        pnl = tp
    elif res == "SL":
        pnl = -sl
    else:
        last = float(df_future["close"].iloc[-1])
        pnl = (last-entry)/entry if side=="BUY" else (entry-last)/entry
    return {"result":res, "bars":int(bars), "pnl_frac":float(pnl)}

def _fetch_data(symbol: str, timeframe: str, limit: int, source: str, csv_path: str, testnet: bool) -> pd.DataFrame:
    if source == "csv":
        df = pd.read_csv(csv_path)
        df["start"] = pd.to_datetime(df["start"], utc=True, errors="coerce")
        return df[["start","open","high","low","close"]].dropna().tail(limit).reset_index(drop=True)
    else:
        try:
            from core.data_pipeline import fetch_klines
            return fetch_klines(symbol, timeframe, limit=limit, testnet=testnet)
        except Exception as e:
            log.warning(f"fetch_klines failed: {e}; fallback synthetic")
            idx = pd.date_range(end=pd.Timestamp.utcnow(), periods=limit, freq="5min")
            close = 30000 + np.cumsum(np.random.normal(0,20,limit))
            high = close + np.random.rand(limit)*10
            low  = close - np.random.rand(limit)*10
            return pd.DataFrame({"start": idx, "open": close, "high": high, "low": low, "close": close})

def walkforward(mode: str, symbol: str, timeframe: str="15m", train_bars: int=2000, test_bars: int=300, step_bars: int=300,
                source: str="api", csv_path: str="", horizon_bars: int=96, testnet: bool=True,
                fee_rt: float=0.0006, slip_rt: float=0.0003) -> Dict[str, Any]:
    g = load_json("config/global.json", {})
    mcfg = load_json(f"config/{mode}.json", {})
    total = train_bars + test_bars*4 + 100
    df = _fetch_data(symbol, timeframe, total, source, csv_path, testnet)
    df["start"] = pd.to_datetime(df["start"], utc=True, errors="coerce")
    df = df.dropna().reset_index(drop=True)
    df = _ensure_features(df)

    trades = []; eq = 1.0
    i = train_bars
    while i + test_bars < len(df):
        test_slice = df.iloc[i:i+test_bars].reset_index(drop=True)
        for j in range(50, len(test_slice)-horizon_bars-1):
            ctx = test_slice.iloc[:j+1].copy()
            sig = combine_signals(mode, ctx, mcfg, symbol=symbol, testnet=testnet)
            if sig.get("action","SKIP") == "SKIP": 
                continue
            entry = float(ctx["close"].iloc[-1]); side = sig["action"]
            tp = float(sig["tp"]); sl = float(sig["sl"])
            future = test_slice.iloc[j+1:j+1+horizon_bars][["open","high","low","close"]]
            sim = _simulate_trade_path(future, entry, side, tp, sl)
            cost = fee_rt + 2*slip_rt
            pnl_net = sim["pnl_frac"] - cost
            eq *= (1 + pnl_net)
            trades.append({"ts":str(ctx["start"].iloc[-1]),"mode":mode,"symbol":symbol,"side":side,"entry":entry,"tp":tp,"sl":sl,"result":sim["result"],"pnl":float(pnl_net),"bars":sim["bars"]})
        i += step_bars

    outdir = ROOT/"reports"; outdir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    if trades:
        import pandas as _pd
        dftr = _pd.DataFrame(trades)
        wr = float((dftr["pnl"]>0).mean()); pnl_sum=float(dftr["pnl"].sum()); avg=float(dftr["pnl"].mean())
        m = {"mode":mode,"symbol":symbol,"timeframe":timeframe,"trades":int(len(trades)),"winrate":wr,"pnl_sum":pnl_sum,"avg_pnl":avg,"equity_final":float(eq)}
        (outdir/f"walk_{mode}_{ts}.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
        (outdir/f"walk_{mode}_{ts}.csv").write_text(dftr.to_csv(index=False),encoding="utf-8")
    else:
        m = {"mode":mode,"trades":0,"note":"No trades generated"}
        (outdir/f"walk_{mode}_{ts}.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    return m
