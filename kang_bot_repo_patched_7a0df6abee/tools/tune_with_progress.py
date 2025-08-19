
import argparse, time, subprocess, sys, os, json
from pathlib import Path

# Wrapper untuk menjalankan tune_xgb_optuna.py per-chunk dan kirim progress ke Telegram
def tg_send(msg: str):
    try:
        from core.notifier import telegram_send
        return telegram_send(msg, parse_mode="HTML", disable_web_page_preview=True, timeout_sec=15)
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["scalping","swing","hybrid","adaptif"])
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--timeframe", required=True)
    ap.add_argument("--trials", type=int, default=100)
    ap.add_argument("--chunk", type=int, default=10, help="Jumlah trial per iterasi progress.")
    ap.add_argument("--extra_args", type=str, default="", help="Argumen tambahan untuk tuner asli.")
    args = ap.parse_args()

    left = args.trials
    done = 0
    tg_send(f"🧪 Mulai Tuning <b>{args.mode}</b> • {args.symbol} • {args.timeframe} • total {args.trials} trials")

    while left > 0:
        step = min(args.chunk, left)
        cmd = f"{sys.executable} tools/tune_xgb_optuna.py --mode {args.mode} --symbol {args.symbol} --timeframe {args.timeframe} --trials {step} {args.extra_args}"
        t0 = time.time()
        try:
            proc = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=60*60)
            ok = (proc.returncode == 0)
        except subprocess.TimeoutExpired:
            ok = False
            proc = type("obj",(object,),{"stdout":"", "stderr":"TIMEOUT"})

        done += step
        left -= step
        dur = time.time()-t0

        # Ambil best value jika tuner menyimpan state (opsional)
        best_txt = ""
        try:
            state = Path("reports/optuna_state.json")
            if state.exists():
                j = json.loads(state.read_text())
                best = j.get("best_value", None)
                if best is not None:
                    best_txt = f" • best={best:.4f}"
        except Exception:
            pass

        if ok:
            tg_send(f"🧪 Progress Tuning: {done}/{args.trials}{best_txt} • durasi {dur/60:.1f}m")
        else:
            tg_send(f"⚠️ Tuning chunk error • {done}/{args.trials}\n<code>{proc.stderr[-400:] if proc.stderr else 'no stderr'}</code>")

    tg_send(f"✅ Tuning selesai: {done}/{args.trials}. Cek config/<mode>_best.json dan logs.")
if __name__ == "__main__":
    main()
