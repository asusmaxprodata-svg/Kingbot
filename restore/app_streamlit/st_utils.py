
import json, time
from pathlib import Path

CFG_ROOT = Path(__file__).resolve().parents[1] / "config"
REPORTS_ROOT = Path(__file__).resolve().parents[1] / "reports"
LOGS_ROOT = Path(__file__).resolve().parents[1] / "logs"
DATA_ROOT = Path(__file__).resolve().parents[1] / "data"

def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return {} if default is None else default

def save_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2))

def global_cfg():
    return load_json(CFG_ROOT / "global.json", {})

def set_global_key(k, v):
    g = global_cfg()
    g[k] = v
    save_json(CFG_ROOT / "global.json", g)

def mode_cfg(mode: str, symbol: str = None):
    from glob import glob
    if symbol:
        p = CFG_ROOT / f"{mode}__{symbol}_best.json"
        if p.exists(): return load_json(p, {})
    p = CFG_ROOT / f"{mode}_best.json"
    if p.exists(): return load_json(p, {})
    return load_json(CFG_ROOT / f"{mode}.json", {})

def tail_log(n=4000):
    p = LOGS_ROOT / "bot.log"
    try:
        t = p.read_text()
        return t[-n:]
    except Exception:
        return "(log belum tersedia)"
