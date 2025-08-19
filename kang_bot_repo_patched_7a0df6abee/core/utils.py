import json, os, time, pathlib
from datetime import datetime, timezone
from typing import Any, Dict

BASE = pathlib.Path(__file__).resolve().parents[1]

def load_json(path: str, default: Any = None):
    p = BASE / path
    if not p.exists():
        return default
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path: str, obj: Any):
    p = BASE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)

def load_config(mode: str) -> Dict[str, Any]:
    from .logger import get_logger
    log = get_logger("utils")
    g = load_json("config/global.json", {})
    m = load_json(f"config/{mode}.json", {})
    cfg = {**g, **m}
    log.debug(f"Loaded config for mode={mode}: {cfg}")
    return cfg

def timestamp():
    return datetime.now(timezone.utc).isoformat()

def save_profit(trade):
    data = load_json("data/profit.json", {"starting_capital":30.0,"equity":30.0,"history":[]})
    if trade:
        data["history"].append(trade)
        if "pnl" in trade:
            data["equity"] = round(data.get("equity", 0.0) + trade["pnl"], 4)
    save_json("data/profit.json", data)
    return data

def risk_check() -> Dict[str, Any]:
    """Evaluate daily risk: stop if equity drawdown > 10% in last 24h."""
    from .logger import get_logger
    log = get_logger("risk_check")
    data = load_json("data/profit.json", {})
    equity = data.get("equity", 0.0)
    start = data.get("starting_capital", 0.0)
    history = data.get("history", [])
    cutoff = time.time() - 24*3600
    daily_pnl = sum(h.get("pnl", 0.0) for h in history if h.get("ts_epoch", 0) >= cutoff)
    max_loss = 0.10 * max(equity, start)
    paused = False
    reason = None
    if -daily_pnl > max_loss:
        paused = True
        reason = f"Daily loss {round(-daily_pnl, 4)} exceeds {round(max_loss, 4)}"
        state = load_json("data/state.json", {})
        state["paused"] = True
        save_json("data/state.json", state)
    return {"paused": paused, "reason": reason, "equity": equity, "daily_pnl": daily_pnl, "max_loss": max_loss}

def _bybit_client(testnet: bool):
    from pybit.unified_trading import HTTP
    return HTTP(testnet=testnet, api_key=os.getenv("BYBIT_API_KEY"), api_secret=os.getenv("BYBIT_API_SECRET"))

def _parse_float_any(d: dict, keys: list, default: float = 0.0) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except Exception:
                continue
    return default

def sync_bybit_closed_pnl(symbols, testnet: bool = True):
    """Fetch recent closed PnL from Bybit and merge into data/profit.json history.

    This relies on best-effort parsing of Bybit response fields.
    """
    from .logger import get_logger
    log = get_logger("sync_pnl")
    http = _bybit_client(testnet)
    data = load_json("data/profit.json", {"starting_capital":30.0,"equity":30.0,"history":[]})
    known = set(h.get("uid") for h in data.get("history", []) if "uid" in h)
    history = data.get("history", [])
    new_count = 0
    for sym in symbols:
        try:
            res = http.get_closed_pnl(category="linear", symbol=sym, limit=50)
            rows = res.get("result", {}).get("list", []) or res.get("result",{}).get("data",[])
        except Exception as e:
            log.warning(f"get_closed_pnl failed for {sym}: {e}")
            rows = []
        for r in rows:
            ts = _parse_float_any(r, ["updatedTime","createdTime","execTime","ts"], default=time.time()*1000.0)
            pnl = _parse_float_any(r, ["closedPnl","realisedPnl","realizedPnl","pnl","profit"], default=0.0)
            uid = str(r.get("orderId") or r.get("positionIdx") or f"{sym}_{int(ts)}_{pnl:.4f}")
            # Update existing OPEN record if uid matches to preserve mode/side
            if uid in known:
                for h in history:
                    if h.get('uid') == uid:
                        h['pnl'] = pnl
                        h['status'] = 'CLOSED'
                        h['ts_close'] = datetime.utcfromtimestamp(float(ts)/1000.0).isoformat()+"Z"
                        break
                continue
            trade = {
                "uid": uid, "symbol": sym,
                "pnl": pnl, "ts_epoch": float(ts)/1000.0, "ts": datetime.utcfromtimestamp(float(ts)/1000.0).isoformat()+"Z",
                "status": "CLOSED"
            }
            data["history"].append(trade)
            data["equity"] = round(float(data.get("equity", 0.0)) + pnl, 6)
            known.add(uid)
            new_count += 1
    if new_count:
        save_json("data/profit.json", data)
    return {"merged": new_count, "equity": data.get("equity")}

def cooldown_active() -> dict:
    state = load_json("data/state.json", {})
    until = state.get("cooldown_until", 0)
    now = time.time()
    return {"active": now < until, "remaining_s": max(0, int(until-now))}

def set_cooldown(minutes: int):
    state = load_json("data/state.json", {})
    state["cooldown_until"] = time.time() + minutes*60
    save_json("data/state.json", state)

def update_loss_streak_on_new_trades(loss_streak_pause: int, cooldown_minutes: int):
    """Inspect latest history to update loss_streak & cooldown state."""
    state = load_json("data/state.json", {})
    hist = load_json("data/profit.json", {}).get("history", [])
    if not hist:
        return
    # Compute streak from the end
    streak = 0
    for h in reversed(hist):
        pnl = h.get("pnl", 0.0)
        if pnl < 0:
            streak += 1
        elif pnl > 0:
            break
    state["loss_streak"] = streak
    # Trigger cooldown if threshold reached and not already cooling
    active = cooldown_active()["active"]
    if not active and loss_streak_pause and streak >= loss_streak_pause:
        set_cooldown(cooldown_minutes)
    save_json("data/state.json", state)

import math

def _instrument_cache_path():
    return BASE / "data" / "instruments.json"

def get_instrument_info(symbol: str, testnet: bool = True) -> dict:
    """Fetch Bybit instrument info for symbol and cache it."""
    cache = load_json("data/instruments.json", {})
    key = f"{'test' if testnet else 'real'}:{symbol}"
    if key in cache and (cache[key].get("_ts",0) + 6*3600) > time.time():
        return cache[key]
    http = _bybit_client(testnet)
    try:
        res = http.get_instruments_info(category="linear", symbol=symbol)
        lst = res.get("result", {}).get("list", [])
        if not lst:
            return cache.get(key, {})
        it = lst[0]
        lot = it.get("lotSizeFilter", {}) or {}
        price = it.get("priceFilter", {}) or {}
        info = {
            "symbol": symbol,
            "tickSize": float(price.get("tickSize", "0.1")),
            "qtyStep": float(lot.get("qtyStep", "0.001")),
            "minOrderQty": float(lot.get("minOrderQty", "0.001")),
            "minNotional": float(lot.get("minNotional", "0")) if isinstance(lot.get("minNotional"), (int,float,str)) else 0.0,
            "_ts": time.time()
        }
        cache[key] = info
        save_json("data/instruments.json", cache)
        return info
    except Exception:
        return cache.get(key, {})

def round_price(symbol: str, price: float, testnet: bool = True) -> float:
    info = get_instrument_info(symbol, testnet)
    ts = float(info.get("tickSize", 0.1)) or 0.1
    return math.floor(price / ts) * ts

def round_qty(symbol: str, qty: float, testnet: bool = True) -> float:
    info = get_instrument_info(symbol, testnet)
    step = float(info.get("qtyStep", 0.001)) or 0.001
    minq = float(info.get("minOrderQty", 0.001)) or 0.001
    q = math.floor(qty / step) * step
    if q < minq:
        return 0.0
    # normalize floats
    return float(f"{q:.10f}".rstrip('0').rstrip('.')) if q!=0 else 0.0

# --- Cooldown notifications ---
def telegram_admin_id() -> int:
    try:
        return int(os.getenv("TELEGRAM_ADMIN_USER_ID","0"))
    except Exception:
        return 0

def check_and_notify_cooldown():
    """Send Telegram message on cooldown start/end transitions."""
    from .logger import get_logger
    from .notifier import telegram_send_direct
    log = get_logger("cooldown_notify")
    state = load_json("data/state.json", {})
    now = time.time()
    until = state.get("cooldown_until", 0)
    started_sent = state.get("cooldown_notified_start", False)
    clear_sent = state.get("cooldown_notified_clear", False)
    admin = telegram_admin_id()
    if until > now:
        # Active cooldown
        if not started_sent and admin:
            mins = int((until - now) / 60) + 1
            telegram_send_direct(f"[kang_bot] Cooldown aktif {mins} menit (loss-streak).")
            state["cooldown_notified_start"] = True
            state["cooldown_notified_clear"] = False
            save_json("data/state.json", state)
    elif until > 0:
        # Cooldown ended
        if not clear_sent and admin:
            telegram_send_direct("[kang_bot] Cooldown berakhir — trading dilanjutkan.")
            state["cooldown_notified_clear"] = True
            save_json("data/state.json", state)

def log_event(event: dict):
    data = load_json("data/profit.json", {"starting_capital":30.0,"equity":30.0,"history":[]})
    event = dict(event)
    event.setdefault("ts_epoch", time.time())
    event.setdefault("ts", datetime.now(timezone.utc).isoformat())
    data["history"].append(event)
    save_json("data/profit.json", data)
