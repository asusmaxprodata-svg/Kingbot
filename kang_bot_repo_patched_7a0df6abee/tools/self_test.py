# -*- coding: utf-8 -*-
"""
Self test for KANG_BOT (run in your environment).
Checks:
- ENV keys presence
- Telegram ping
- Bybit tickers connectivity (public)
- rank_symbols(top_n=3)
- tune_and_train quick run (n_trials=2) [may take few minutes]
"""
from __future__ import annotations
import os, sys, json, traceback
from typing import Dict, Any
sys.path.append(".")

from core.logger import get_logger
log = get_logger("self_test")

def _ok(title): print(f"[OK] {title}")
def _fail(title, e): print(f"[FAIL] {title}: {e}")

def check_env():
    keys = ["BYBIT_TESTNET","TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID"]
    miss = [k for k in keys if not os.getenv(k)]
    if miss:
        raise RuntimeError(f"Missing env keys: {', '.join(miss)}")
    _ok("ENV presence (BYBIT_TESTNET, TELEGRAM_*)")

def ping_telegram():
    import requests
    t = os.getenv("TELEGRAM_BOT_TOKEN"); c = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_ADMIN_USER_ID")
    if not t or not c:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN/CHAT_ID for ping")
    r = requests.get(
        f"https://api.telegram.org/bot{t}/sendMessage",
        params={"chat_id": c, "text": "🧪 Self-test: Telegram OK"},
        timeout=15,
    )
    r.raise_for_status()
    _ok("Telegram ping")

def bybit_public():
    from pybit.unified_trading import HTTP
    http = HTTP(testnet=os.getenv("BYBIT_TESTNET","true").lower() in ("1","true","yes","y","on"))
    res = http.get_tickers(category="linear")
    if not (res or {}).get("retCode", 1)==0:
        raise RuntimeError(res)
    _ok("Bybit public tickers")

def rank_syms():
    from core.symbol_scanner import rank_symbols
    syms = rank_symbols(top_n=3, testnet=os.getenv("BYBIT_TESTNET","true").lower() in ("1","true","yes","y","on"))
    print("Symbols:", syms)
    if not syms:
        raise RuntimeError("No symbols returned")
    _ok("rank_symbols()")

def quick_tune():
    from core.optuna_tuner import tune_and_train
    res = tune_and_train("swing", n_trials=2)  # minimal trials
    print(json.dumps(res, indent=2))
    _ok("tune_and_train() quick run")

def main():
    failures = 0
    for title, fn in [
        ("ENV", check_env),
        ("Telegram", ping_telegram),
        ("Bybit", bybit_public),
        ("rank_symbols", rank_syms),
        ("tune_and_train", quick_tune),
    ]:
        try:
            fn()
        except Exception as e:
            _fail(title, e)
            failures += 1
    if failures == 0:
        print("\n✅ SELF TEST PASSED")
    else:
        print(f"\n⚠️ SELF TEST completed with {failures} failure(s)")

if __name__ == "__main__":
    main()
