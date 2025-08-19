import json, os, time
from pathlib import Path
import utils.env_loader  # auto-load .env

BASE = Path(__file__).resolve().parents[1]

def ok(m): print("[OK]", m)
def warn(m): print("[WARN]", m)
def fail(m): print("[FAIL]", m)

def main():
    # ENV checks
    required = ["TELEGRAM_BOT_TOKEN","TELEGRAM_ADMIN_USER_ID"]
    missing = [k for k in required if not os.getenv(k)]
    if missing: warn("ENV missing: " + ", ".join(missing))
    else: ok("ENV minimal OK")
    # heartbeat/state
    stp = BASE/"data/state.json"
    if not stp.exists():
        fail("data/state.json missing"); return 1
    st = json.loads(stp.read_text(encoding="utf-8"))
    ts = st.get("heartbeat_ts")
    if not ts: warn("heartbeat_ts missing")
    else:
        age = time.time() - float(ts)
        if age < 180:
            ok(f"Heartbeat recent ({age:.1f}s ago)")
        else:
            warn(f"Heartbeat stale ({age:.1f}s)")
    # daily loss guard
    md = st.get("daily_loss_pct", 0)
    paused = st.get("auto_paused", False)
    if paused: ok(f"Auto-pause engaged (daily_loss={md}%)")
    else: ok("Auto-pause not active")
    print("HEALTHCHECK DONE ✅")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
