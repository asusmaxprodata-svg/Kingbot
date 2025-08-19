from typing import Dict
from .utils import risk_check, load_json, save_json, sync_bybit_closed_pnl, cooldown_active, update_loss_streak_on_new_trades
from .logger import get_logger
from .notifier import telegram_send_direct
log = get_logger("risk")

def can_trade() -> Dict:

    state = load_json("data/state.json", {})
    g = load_json("config/global.json", {})
    # Equity floor check (only strict in REAL; TESTNET always OK)
    if not state.get("testnet", True):
        eq = load_json("data/profit.json", {}).get("equity", 0.0)
        if eq < float(g.get("equity_floor", 0)):
            state["testnet"] = True
            try:
                telegram_send_direct(f"[kang_bot] Equity {eq:.2f} < floor → auto switch ke TESTNET.")
            except Exception:
                pass
            save_json("data/state.json", state)
            return {"ok": False, "reason": f"Equity {eq} < floor; switched to TESTNET"}
    # Sync recent PnL & update streak/cooldown
    symbols = g.get("symbols", [g.get("symbol","BTCUSDT")])
    try:
        sync_bybit_closed_pnl(symbols, testnet=state.get("testnet", True))
    except Exception:
        pass
    update_loss_streak_on_new_trades(int(g.get("loss_streak_pause",3)), int(g.get("cooldown_minutes_after_loss",15)))
    # Cooldown gate
    cd = cooldown_active()
    if cd.get("active"):
        return {"ok": False, "reason": f"Cooldown active {cd['remaining_s']}s"}
    # Existing pause/daily loss gate
    if state.get("paused"):
        return {"ok": False, "reason": "Paused by risk control/state flag"}
    r = risk_check()
    if r.get("paused"):
        return {"ok": False, "reason": r.get("reason")}
    return {"ok": True}
