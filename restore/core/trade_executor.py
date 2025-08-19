import os, time, random
from typing import Dict, Any
from .logger import get_logger
from core.ai_signal import llm_confirm
from .utils import load_json, save_json, round_price, round_qty, get_instrument_info, log_event
from pybit.unified_trading import HTTP
import utils.env_loader  # auto-load .env

log = get_logger("trade_executor")

def _client(testnet: bool):
    return HTTP(
        testnet=testnet,
        api_key=os.getenv("BYBIT_API_KEY"),
        api_secret=os.getenv("BYBIT_API_SECRET"),
        recv_window=5000
    )

def _retry(fn, *args, **kwargs):
    max_try = kwargs.pop("_max_try", 3)
    back = 0.5
    for i in range(max_try):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if i == max_try - 1:
                raise
            time.sleep(back)
            back *= 2.0 + random.random() * 0.3

def place_order(symbol: str, side: str, qty: float, tp_frac: float, sl_frac: float, leverage: int, trailing: float, testnet: bool = True) -> Dict[str, Any]:
    """Place a market order with leverage and set TP/SL.
    side: "BUY" or "SELL"
    tp_frac/sl_frac: fractions (e.g., 0.02, 0.01)
    """

    # Simulation guard
    g = load_json("config/global.json", {})
    st = load_json("data/state.json", {})
    sim = bool(g.get("simulation_mode", False) or st.get("simulation_mode", False))
    # Global kill-switch from .env
    import os
    if os.getenv("ENABLE_TRADING","false").lower() in ("false","0","no"):
        log.info("Trading disabled by ENABLE_TRADING", extra={"pair": symbol})
        return {"status":"blocked","reason":"ENABLE_TRADING=false"}

    # Simulation guard
    g = load_json("config/global.json", {})
    st = load_json("data/state.json", {})
    sim = bool(g.get("simulation_mode", False) or st.get("simulation_mode", False))
    if sim:
        log_event({"type":"SIM_MANAGE","symbol":symbol})
        return
    # Optional LLM confirm/veto if model confidence is low
    try:
        from core.config_manager import load_config
        _cfg = load_config() or {}
        _llm = _cfg.get("llm", {})
        _t = float(_llm.get("confirm_min_conf", 0.58))
        _mc = locals().get("model_confidence", locals().get("model_conf", 1.0))
        if _llm.get("confirm", False) and _mc < _t:
            _ok = llm_confirm({
                "symbol": symbol, "side": side, "qty": qty,
                "spread_bps": locals().get("spread_bps", 0.0),
                "vol": locals().get("vol_now", 0.0),
                "model_conf": float(_mc)
            })
            if not _ok.get("ok", True):
                log.info(f"LLM veto: {_ok.get('why','-')}", extra={"pair": symbol})
                return {"status":"hold","reason":"llm_veto"}
    except Exception as __e:
        log.debug(f"LLM confirm skipped: {__e}")

    http = _client(testnet)
    # Set leverage (best effort)
    try:
        _retry(http.set_leverage, category="linear", symbol=symbol, buyLeverage=str(leverage), sellLeverage=str(leverage))
    except Exception as e:
        log.warning(f"set_leverage failed: {e}")

    # Get last price
    try:
        t = _retry(http.get_tickers, category="linear", symbol=symbol)
        last = float(t["result"]["list"][0]["lastPrice"])
    except Exception:
        last = None

    # Compute TP/SL prices if last available
    if last:
        info = get_instrument_info(symbol, testnet)
        min_notional = float(info.get('minNotional', 0.0) or 0.0)
        if side == "BUY":
            tp = round_price(symbol, last * (1 + tp_frac), testnet)
            sl = round_price(symbol, last * (1 - sl_frac), testnet)
        else:
            tp = round_price(symbol, last * (1 - tp_frac), testnet)
            sl = round_price(symbol, last * (1 + sl_frac), testnet)
    else:
        tp = sl = None
        min_notional = 0.0

    # Round qty & validate
    rq = round_qty(symbol, qty, testnet)
    if rq <= 0:
        return {"status": "blocked", "reason": "Qty below min step/minOrderQty"}
    if min_notional and last and (rq * last) < min_notional:
        return {"status": "blocked", "reason": f"Notional {rq*last:.4f} < minNotional {min_notional}"}

    # Place market order
    try:
        coid = f"kang_{int(time.time()*1000)}_{side[:1]}"
        ord_res = _retry(
            http.place_order,
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=str(rq),
            clientOrderId=coid,
            timeInForce="GoodTillCancel",
            reduceOnly=False
        )
        orderId = (ord_res.get("result", {}) or {}).get("orderId", "N/A")
        # Set TP/SL
        if tp and sl:
            try:
                _retry(http.set_trading_stop, category="linear", symbol=symbol, takeProfit=str(tp), stopLoss=str(sl), tpslMode="Partial")
            except Exception as e:
                log.warning(f"set_trading_stop failed: {e}")
        return {"status": "ok", "orderId": orderId, "tp": tp, "sl": sl}
    except Exception as e:
        log.exception(e)
        return {"status": "error", "reason": str(e)}

def manage_open_positions(symbol: str, testnet: bool = True):
    """Manage open position with partial TP (TP1/TP2) and breakeven move after TP1 touch.
    Avoid duplicate reduce-only orders by checking open orders first.
    """
    http = _client(testnet)
    state = load_json("data/state.json", {})
    mode = state.get("mode", "hybrid")
    g = load_json("config/global.json", {})
    m = load_json(f"config/{mode}.json", {})
    split = m.get("tp_split", {"tp1": 0.5, "tp2": 0.5, "breakeven_trigger": 0.5})
    tp1_part = float(split.get("tp1", 0.5))
    tp2_part = float(split.get("tp2", 0.5))

    try:
        pos_res = _retry(http.get_positions, category="linear", symbol=symbol)
        pos = (pos_res.get("result", {}) or {}).get("list", []) or []
        if not pos:
            return
        p = pos[0]
        side = p.get("side")
        size = float(p.get("size", 0) or 0)
        if size <= 0:
            return
        entry = float(p.get("entryPrice", 0) or 0)
        last = float(_retry(http.get_tickers, category="linear", symbol=symbol)["result"]["list"][0]["lastPrice"])

        tp = float(m.get("tp", g.get("default_tp", 0.02)))
        if side == "Buy":
            tp1 = entry * (1 + tp * tp1_part)
            tp2 = entry * (1 + tp * tp2_part)
        else:
            tp1 = entry * (1 - tp * tp1_part)
            tp2 = entry * (1 - tp * tp2_part)

        # Move SL to BE once TP1 passed
        cond_tp1 = (last >= tp1) if side == "Buy" else (last <= tp1)
        if cond_tp1:
            try:
                _retry(http.set_trading_stop, category="linear", symbol=symbol, stopLoss=str(entry))
                log_event({"type": "BE_ACTIVATED", "symbol": symbol, "mode": mode, "side": side, "price": last})
            except Exception as e:
                log.warning(f"BE adjust failed: {e}")

        # Avoid duplicate reduce-only orders
        try:
            openo = _retry(http.get_open_orders, category='linear', symbol=symbol)
            existing = []
            for it in (openo.get('result', {}) or {}).get('list', []) or []:
                if it.get('reduceOnly'):
                    existing.append((float(it.get('price', 0)), float(it.get('qty', 0))))
            def _missing(pv, qv):
                for (ep, eq) in existing:
                    if abs(ep - pv) <= 1e-8 and abs(eq - qv) <= 1e-6:
                        return False
                return True
            q1 = float(size) * tp1_part; q2 = float(size) - q1
            if _missing(tp1, q1):
                _retry(http.place_order, category='linear', symbol=symbol, side=('Sell' if side=='Buy' else 'Buy'),
                       orderType='Limit', price=str(tp1), qty=str(q1), reduceOnly=True, timeInForce='GoodTillCancel')
            if _missing(tp2, q2):
                _retry(http.place_order, category='linear', symbol=symbol, side=('Sell' if side=='Buy' else 'Buy'),
                       orderType='Limit', price=str(tp2), qty=str(q2), reduceOnly=True, timeInForce='GoodTillCancel')
        except Exception as e:
            log.warning(f"partial TP place failed: {e}")
    except Exception as e:
        log.warning(f"manage positions failed: {e}")
