
import time, math, json
from pathlib import Path
from .utils import load_json, save_json
from .notifier import send_telegram_message

ALERT_STATE_PATH = Path("reports/alert_state.json")

def _state():
    s = load_json(ALERT_STATE_PATH, {})
    if "last" not in s: s["last"] = {}
    return s

def _save(s):
    save_json(ALERT_STATE_PATH, s)

def get_alerts_cfg():
    g = load_json("config/global.json", {})
    a = g.get("alerts", {})
    # defaults
    a.setdefault("enabled", True)
    a.setdefault("imbalance_pct", 20.0)  # %
    a.setdefault("spread_bps", 6.0)      # bps
    a.setdefault("atr_sigma", 2.5)       # placeholder for future
    a.setdefault("cooldown_sec", 300)    # 5 min
    return a

def _cooldown_ok(key, cd):
    s = _state()
    last = s["last"].get(key, 0)
    now = time.time()
    if now - last >= cd:
        s["last"][key] = now
        _save(s)
        return True
    return False

def alert_imbalance(symbol: str, imbalance_pct: float, cfg=None):
    cfg = cfg or get_alerts_cfg()
    if not cfg.get("enabled", True): return False
    thr = float(cfg.get("imbalance_pct", 20.0))
    cd  = int(cfg.get("cooldown_sec", 300))
    if abs(imbalance_pct) >= thr and _cooldown_ok(f"imb_{symbol}", cd):
        dir_ = "BID>ASK" if imbalance_pct>0 else "ASK>BID"
        msg = f"⚠️ Orderbook Imbalance {symbol}\nImbalance: {imbalance_pct:+.1f}% ({dir_})\nThreshold: ±{thr:.1f}%"
        try: send_telegram_message(msg)
        except Exception: pass
        return True
    return False

def alert_spread(symbol: str, spread_bps: float, cfg=None):
    cfg = cfg or get_alerts_cfg()
    if not cfg.get("enabled", True): return False
    thr = float(cfg.get("spread_bps", 6.0))
    cd  = int(cfg.get("cooldown_sec", 300))
    if spread_bps >= thr and _cooldown_ok(f"spr_{symbol}", cd):
        msg = f"⚠️ Spread Lebar {symbol}\nSpread: {spread_bps:.2f} bps ≥ {thr:.2f} bps\nAksi: skip trade sementara."
        try: send_telegram_message(msg)
        except Exception: pass
        return True
    return False

def alert_daily_loss(equity_change_pct: float, max_daily_loss_pct: float, cfg=None):
    cfg = cfg or get_alerts_cfg()
    if not cfg.get("enabled", True): return False
    cd  = int(cfg.get("cooldown_sec", 300))
    key = "ddaily"
    if equity_change_pct <= -abs(max_daily_loss_pct) and _cooldown_ok(key, cd):
        msg = f"🛑 Cap Loss Harian Tercapai\nP/L Hari ini: {equity_change_pct:.2f}% ≤ -{abs(max_daily_loss_pct):.2f}%\nBot dipause otomatis."
        try: send_telegram_message(msg)
        except Exception: pass
        return True
    return False
