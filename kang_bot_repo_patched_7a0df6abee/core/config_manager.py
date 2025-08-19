from .utils import load_json, save_json

def get_mode() -> str:
    state = load_json("data/state.json", {})
    return state.get("mode", "hybrid")

def set_mode(mode: str):
    state = load_json("data/state.json", {})
    state["mode"] = mode
    save_json("data/state.json", state)

def get_leverage():
    state = load_json("data/state.json", {})
    return state.get("leverage", "auto")

def set_leverage(lev):
    state = load_json("data/state.json", {})
    state["leverage"] = lev
    save_json("data/state.json", state)

def set_testnet(flag: bool):
    state = load_json("data/state.json", {})
    state["testnet"] = bool(flag)
    save_json("data/state.json", state)


def get_symbol():
    g = load_json("config/global.json", {})
    return g.get("symbol", "BTCUSDT")

def set_symbol(sym: str):
    g = load_json("config/global.json", {})
    g["symbol"] = sym.upper()
    save_json("config/global.json", g)

def get_watchlist():
    g = load_json("config/global.json", {})
    wl = g.get("symbols", ["BTCUSDT","ETHUSDT","SOLUSDT"])
    return list(dict.fromkeys([s.upper() for s in wl]))

def add_watchlist(sym: str):
    g = load_json("config/global.json", {})
    wl = g.get("symbols", [])
    if sym.upper() not in wl:
        wl.append(sym.upper())
    g["symbols"] = wl
    save_json("config/global.json", g)

def remove_watchlist(sym: str):
    g = load_json("config/global.json", {})
    wl = [s for s in g.get("symbols", []) if s.upper()!=sym.upper()]
    g["symbols"] = wl
    save_json("config/global.json", g)

def get_auto_pairs():
    g = load_json("config/global.json", {})
    return bool(g.get("auto_pairs", True))

def set_auto_pairs(flag: bool):
    g = load_json("config/global.json", {})
    g["auto_pairs"] = bool(flag)
    save_json("config/global.json", g)

def get_topn():
    g = load_json("config/global.json", {})
    return int(g.get("top_n", 3))

def set_topn(n: int):
    g = load_json("config/global.json", {})
    g["top_n"] = int(max(1, min(5, n)))
    save_json("config/global.json", g)


def get_pair_update_interval_min():
    g = load_json("config/global.json", {})
    return int(g.get("pair_update_interval_min", 15))

def set_pair_update_interval_min(m: int):
    g = load_json("config/global.json", {})
    m = int(max(1, min(180, int(m))))  # clamp to 1..180 minutes
    g["pair_update_interval_min"] = m
    save_json("config/global.json", g)


def get_leverage_caps():
    g = load_json("config/global.json", {})
    return g.get("leverage_caps", {"scalping":50,"hybrid":50,"swing":20,"adaptive":50})

def get_leverage_cap_for_mode(mode: str):
    caps = get_leverage_caps()
    return int(caps.get(mode, 50))

def clamp_leverage(mode: str, lev):
    try:
        cap = get_leverage_cap_for_mode(mode)
    except Exception:
        cap = 50
    if isinstance(lev, (int, float)):
        lev = int(max(1, min(cap, int(lev))))
        return lev
    # string ("auto") passes through; enforcement happens when resolved to number
    return lev


def get_running():
    g = load_json("config/global.json", {})
    return bool(g.get("running", True))

def set_running(flag: bool):
    g = load_json("config/global.json", {})
    g["running"] = bool(flag)
    save_json("config/global.json", g)
