# -*- coding: utf-8 -*-
"""
tools/tune_and_select.py
Run weekly maintenance: select symbols and tune strategies, then notify via Telegram.
"""
from __future__ import annotations
import os, argparse, json, sys, traceback
from typing import List, Dict, Any

# Local imports
sys.path.append(".")
from core.logger import get_logger
from core.utils import load_json, save_json, now_ts
from core.symbol_scanner import rank_symbols
from core.optuna_tuner import tune_and_train
from core.notifier import telegram_send

log = get_logger("tune_and_select")

def _notify(msg: str):
    try:
        ok = telegram_send(msg)
        if not ok:
            log.warning("Notify returned False")
    except Exception as e:
        log.warning("Notify failed: %s", e)

def main(args=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["scalping","swing","hybrid"])
    ap.add_argument("--topn", type=int, default=3)
    ap.add_argument("--timeframe", default=None)
    ap.add_argument("--trials", type=int, default=25)  # make it fast by default
    ap.add_argument("--testnet", default=os.getenv("BYBIT_TESTNET","true"))
    ns = ap.parse_args(args=args)

    testnet = str(ns.testnet).lower() in ("1","true","yes","y","on")

    # 1) Rank symbols
    try:
        symbols = rank_symbols(top_n=ns.topn, testnet=testnet)
    except Exception as e:
        log.error("rank_symbols error: %s", e)
        symbols = [os.getenv("SYMBOL","BTCUSDT")]

    # Save into config/global.json
    g = load_json("config/global.json", {})
    g.setdefault("general", {})
    g["general"]["symbols"] = symbols
    g["general"]["last_auto_symbols_at"] = now_ts()
    save_json("config/global.json", g)

    # 2) Tune each mode
    results: Dict[str, Any] = {}
    for m in ns.modes:
        try:
            res = tune_and_train(m, n_trials=ns.trials, timeframe=ns.timeframe, symbol=symbols[0] if symbols else None, testnet=testnet)
            results[m] = res
        except Exception as e:
            log.error("tune_and_train(%s) failed: %s", m, e)
            results[m] = {"error": str(e)}

    # 3) Notify summary
    lines = ["🛠️ *Weekly Maintenance Completed*",
             f"• Symbols: {', '.join(symbols)}",
             f"• Testnet: {testnet}",
             f"• Trials per mode: {ns.trials}"]
    for m, r in results.items():
        if "error" in r:
            lines.append(f"  - {m}: ❌ {r['error']}")
        else:
            lines.append(f"  - {m}: ✅ best_score={r.get('best_score',0):.4f}")
    _notify("\n".join(lines))

    print(json.dumps({"symbols":symbols, "results":results}, indent=2))

if __name__ == "__main__":
    main()
