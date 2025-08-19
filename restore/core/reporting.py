import os, math, json, pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .utils import load_json
from .logger import get_logger

log = get_logger("reporting")

def _to_df():
    d = load_json("data/profit.json", {})
    hist = d.get("history", [])
    if not hist: 
        return pd.DataFrame()
    df = pd.DataFrame(hist)
    if "ts_epoch" in df.columns:
        df = df.sort_values("ts_epoch")
    return df

def per_mode_stats():
    df = _to_df()
    if df.empty:
        return {}
    closed = df[df.get("status","") == "CLOSED"]
    if closed.empty:
        return {}
    grouped = closed.groupby(df["mode"].fillna("unknown"))
    stats = {}
    for mode, g in grouped:
        pnl = g["pnl"].astype(float)
        wins = (pnl > 0).sum()
        loss = (pnl < 0).sum()
        wr = wins / max(1, (wins+loss))
        tot = pnl.sum()
        # simple sharpe: mean/std of daily-like chunks (approx on trades)
        s = pnl.mean() / (pnl.std() + 1e-9)
        stats[mode] = {"trades": int(len(g)), "winrate": float(wr), "pnl": float(tot), "sharpe_like": float(s)}
    return stats

def save_equity_chart(path_png: str):
    df = _to_df()
    if df.empty:
        return None
    # build equity over time
    eq0 = load_json("data/profit.json", {}).get("starting_capital", 30.0)
    pnl = df["pnl"].fillna(0).astype(float)
    eq_curve = eq0 + pnl.cumsum()
    t = df["ts_epoch"]
    plt.figure()
    plt.plot(t, eq_curve)
    plt.xlabel("time")
    plt.ylabel("equity")
    plt.title("kang_bot equity over time")
    plt.tight_layout()
    plt.savefig(path_png, dpi=140)
    plt.close()
    return path_png
