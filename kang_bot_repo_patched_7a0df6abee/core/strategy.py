from typing import Dict, Any
import numpy as np
from .logger import get_logger

log = get_logger("strategy")

def dynamic_trailing(price: float, vol: float) -> float:
    """Return trailing stop fraction function of volatility (0.2%..1.5%)."""
    v = np.clip(vol, 0, 0.03)
    return float(np.clip(0.002 + 20*v, 0.002, 0.015))

def _atr_scaled(tp_base: float, sl_base: float, features: dict, k_tp=1.0, k_sl=1.0):
    atr_frac = float(features.get("atr_frac", 0.0) or 0.0)
    if atr_frac > 0:
        tp = max(tp_base, k_tp * atr_frac)
        sl = max(sl_base, k_sl * atr_frac * 0.5)  # SL biasanya lebih ketat
        return tp, sl
    return tp_base, sl_base

def gate_by_volatility(mode: str, features: dict, cfg: dict) -> Dict[str, Any]:
    """Simple vol regime gate: skip certain modes outside preferred vol range."""
    vol = float(features.get("vol", 0.0) or 0.0)
    # defaults
    ranges = {
        "scalping": (0.002, 0.025),  # butuh vol minimal
        "hybrid":   (0.0015, 0.03),
        "swing":    (0.0, 0.02),     # hindari terlalu volatil
    }
    r = cfg.get("vol_gates", {}).get(mode, None)
    lo, hi = r if r else ranges.get(mode, (0.0, 1.0))
    ok = (vol >= lo) and (vol <= hi)
    return {"ok": ok, "vol": vol, "range": (lo, hi)}

def apply_mode_overrides(mode: str, signal: Dict[str, Any], cfg: dict, features: dict) -> Dict[str, Any]:
    s = dict(signal)

    # Mode-specific TP/SL via ATR
    if mode == "scalping":
        tp, sl = _atr_scaled(s.get("tp", 0.02), s.get("sl", 0.01), features, k_tp=0.8, k_sl=1.2)
        s["tp"], s["sl"] = min(tp, 0.025), min(sl, 0.012)
    elif mode == "swing":
        tp, sl = _atr_scaled(s.get("tp", 0.02), s.get("sl", 0.01), features, k_tp=1.8, k_sl=1.0)
        s["tp"], s["sl"] = max(tp, 0.02), max(sl, 0.01)
    elif mode == "hybrid":
        # hybrid tengah-tengah
        tp, sl = _atr_scaled(s.get("tp", 0.02), s.get("sl", 0.01), features, k_tp=1.2, k_sl=1.0)
        s["tp"], s["sl"] = tp, sl
    elif mode == "adaptive":
        # akan diatur oleh pemilihan mode bawah
        pass

    # Leverage hard-cap per mode
    cap = (cfg.get('leverage_cap') or {}).get(mode, None)
    if cap:
        try:
            s['leverage'] = min(int(s.get('leverage', 10)), int(cap))
        except Exception:
            pass

    # Trailing based on vol
    trail = dynamic_trailing(price=features.get("close",0.0), vol=features.get("vol",0.005))
    s["trailing"] = trail
    return s
