
import os
import threading
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
from core.utils import load_json
from core.symbol_scanner import rank_symbols
from core.notifier import telegram_send_direct

_scheduler_ref = None

def _pick_symbols(cfg):
    auto = cfg.get("auto_tune", {})
    if auto.get("use_auto_pairs", True):
        ranked = rank_symbols(cfg)
        top_n = int(auto.get("top_n", 2))
        return [r["symbol"] for r in ranked[:max(1, top_n)]]
    syms = auto.get("symbols") or [cfg.get("symbol", "BTCUSDT")]
    return [s.upper() for s in syms]

def _run_tuner_once_multi(symbols, timeframe, trials, chunk, extra_args=""):
    try:
        telegram_send_direct(f"🧪 Auto-Tune Swing dimulai • {', '.join(symbols)} • {timeframe} • {trials} trials")
    except Exception:
        pass
    for symbol in symbols:
        cmd = [os.environ.get("PYTHON","python"), "tools/tune_with_progress.py",
               "--mode","swing","--symbol",symbol,"--timeframe",timeframe,
               "--trials",str(trials),"--chunk",str(chunk)]
        if extra_args:
            cmd.extend(["--extra_args", extra_args])
        try:
            subprocess.run(cmd, check=True)
            try:
                telegram_send_direct(f"✅ Tuning selesai untuk {symbol}")
            except Exception:
                pass
        except Exception as e:
            try:
                telegram_send_direct(f"⚠️ Auto-Tune gagal untuk {symbol}: {e}")
            except Exception:
                pass
    try:
        telegram_send_direct("✅ Auto-Tune batch selesai.")
    except Exception:
        pass
    return True

def start_scheduler():
    global _scheduler_ref
    cfg = load_json("config/global.json", {})
    auto = cfg.get("auto_tune", {})
    if not auto.get("enabled", False):
        return None
    hour = int(auto.get("hour", 1))
    minute = int(auto.get("minute", 0))
    timeframe = auto.get("timeframe", "1h")
    trials = int(auto.get("trials", 120))
    chunk = int(auto.get("chunk", 12))
    extra = auto.get("extra_args", "")
    symbols = _pick_symbols(cfg)
    scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
    scheduler.add_job(_run_tuner_once_multi, "cron", hour=hour, minute=minute,
                      args=[symbols, timeframe, trials, chunk, extra])
    scheduler.start()
    _scheduler_ref = scheduler
    try:
        telegram_send_direct(f"⏰ Auto-Tune Harian aktif (WIB {hour:02d}:{minute:02d})")
    except Exception:
        pass
    return scheduler

def reschedule_autotune():
    global _scheduler_ref
    cfg = load_json("config/global.json", {})
    auto = cfg.get("auto_tune", {})
    try:
        if _scheduler_ref:
            _scheduler_ref.shutdown(wait=False)
    except Exception:
        pass
    try:
        hour = int(auto.get("hour", 1))
        minute = int(auto.get("minute", 0))
        timeframe = auto.get("timeframe", "1h")
        trials = int(auto.get("trials", 120))
        chunk = int(auto.get("chunk", 12))
        extra = auto.get("extra_args", "")
        symbols = _pick_symbols(cfg)
        scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
        scheduler.add_job(_run_tuner_once_multi, "cron", hour=hour, minute=minute,
                          args=[symbols, timeframe, trials, chunk, extra])
        scheduler.start()
        _scheduler_ref = scheduler
        try:
            telegram_send_direct(f"🕒 Jadwal Auto-Tune diperbarui ke {hour:02d}:{minute:02d} WIB")
        except Exception:
            pass
        return True
    except Exception:
        return False

def trigger_tune_now():
    cfg = load_json("config/global.json", {})
    auto = cfg.get("auto_tune", {})
    symbols = _pick_symbols(cfg)
    timeframe = auto.get("timeframe", "1h")
    trials = int(auto.get("trials", 120))
    chunk = int(auto.get("chunk", 12))
    extra = auto.get("extra_args", "")
    t = threading.Thread(target=_run_tuner_once_multi, args=(symbols, timeframe, trials, chunk, extra), daemon=True)
    t.start()
    return True
