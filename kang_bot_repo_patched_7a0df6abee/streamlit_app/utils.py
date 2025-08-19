import json, time, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def jload(path, default=None):
    p = ROOT / path
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}

def jsave(path, data):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")

def timestamp():
    import datetime, pytz
    return datetime.datetime.now(tz=pytz.UTC).isoformat()

def set_state_key(key, value):
    st = jload("data/state.json", {})
    st[key] = value
    jsave("data/state.json", st)
    return st

def update_global_config(updates: dict):
    g = jload("config/global.json", {})
    g.update(updates or {})
    jsave("config/global.json", g)
    return g
