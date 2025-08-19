import os, json, subprocess, sys, time
from pathlib import Path
import utils.env_loader  # auto-load .env

BASE = Path(__file__).resolve().parents[1]
MODES = ["scalping","swing","hybrid","adaptive"]

def run_mode(mode):
    cmd = [sys.executable, str(BASE/"tools"/"run_walkforward.py"), "--mode", mode, "--testnet"]
    p = subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        return {"mode": mode, "error": (p.stderr or p.stdout)[-400:]}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"mode": mode, "raw": p.stdout[-400:]}

def maybe_tg_send(summary):
    from core.notifier import telegram_send
    lines = ["*Walk-Forward Summary*"]
    for m, s in summary.items():
        if "error" in s:
            lines.append(f"• {m}: _error_")
        else:
            wr = s.get("winrate",0)*100
            trades = s.get("trades",0); eq = s.get("equity_final",1.0)
            lines.append(f"• {m}: trades={trades}, wr={wr:.1f}%, equity={eq:.3f}")
    text = "\n".join(lines)
    ok = telegram_send(text, parse_mode="Markdown", timeout_sec=15)
    if not ok:
        print("[WARN] Telegram send failed (maybe_tg_send)")

def main():
    res = {}
    for mode in MODES:
        res[mode] = run_mode(mode)
        time.sleep(1)
    maybe_tg_send(res)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
