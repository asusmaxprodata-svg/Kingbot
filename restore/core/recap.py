
import json, time
from pathlib import Path
from .utils import load_json
from .templates import card_daily_recap

def build_daily_recap():
    prof = load_json("data/profit.json", {})
    hist = prof.get("history", [])
    import time
    cutoff = time.time() - 24*3600
    trades = [h for h in hist if h.get("ts_epoch", 0) >= cutoff]
    pnl_pct = sum(h.get("pnl_pct", 0.0) for h in trades)
    wins = sum(1 for h in trades if h.get("pnl_pct", 0.0) > 0)
    loss = sum(1 for h in trades if h.get("pnl_pct", 0.0) <= 0)
    wr = (wins / max(1, wins+loss)) * 100.0
    eq = prof.get("equity", 0.0)
    mode = prof.get("mode", "-")
    return card_daily_recap(len(trades), wr, pnl_pct, eq, mode)
