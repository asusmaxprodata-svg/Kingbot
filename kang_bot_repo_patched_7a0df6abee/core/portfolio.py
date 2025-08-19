from .utils import load_json

def equity() -> float:
    data = load_json("data/profit.json", {})
    return float(data.get("equity", data.get("starting_capital", 0.0)))

def position_size(price: float, sl_frac: float, risk_frac: float = None) -> float:
    """Risk-based sizing using SL distance.
    qty = (equity * risk_frac * (1 - size_buffer)) / (price * sl_frac)
    Leverage affects margin, not risk at SL.
    """
    g = load_json('config/global.json', {})
    eq = equity()
    if risk_frac is None:
        risk_frac = float(g.get('risk_per_trade_fraction', 0.01))
    buf = float(g.get('size_buffer_fraction', 0.0))
    denom = max(price * max(sl_frac, 1e-6), 1e-6)
    usd_risk = eq * risk_frac * (1.0 - buf)
    qty = usd_risk / denom
    return max(0.0, round(qty, 10))
