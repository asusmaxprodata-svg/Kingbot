import os, sys, time, argparse, json
from core.logger import get_logger
from core.utils import load_json, save_json
from kingbot.metrics import start_metrics_server, tick_heartbeat

log = get_logger("kingbot")

def load_env_and_config(mode: str | None = None) -> dict:
    try:
        import utils.env_loader  # auto-load .env if present
    except Exception:
        pass
    g = load_json("config/global.json", {}) or {}
    if mode:
        m = load_json(f"config/{mode}.json", {}) or {}
        g.update(m)
    return g

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=os.getenv("MODE", "hybrid"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--duration", type=int, default=0, help="Seconds to run before exit (0=infinite)")
    args = ap.parse_args()

    cfg = load_env_and_config(args.mode)
    testnet = str(cfg.get("testnet", True)).lower() in ("1","true","yes","y","on")
    log.info(f"Starting kingbot mode={args.mode} testnet={testnet} dry_run={args.dry_run}")

    # Start metrics server
    start_metrics_server()
    heartbeat_path = os.getenv("HEARTBEAT_PATH", "logs/heartbeat.txt")

    # Minimal main loop: ticker heartbeat + placeholder trading loop
    t0 = time.time()
    try:
        while True:
            # placeholder for real trading/simulator step
            tick_heartbeat(heartbeat_path)
            time.sleep(5)
            if args.duration and (time.time() - t0) >= args.duration:
                break
    except KeyboardInterrupt:
        log.info("Shutdown requested by user")
    except Exception as e:
        log.exception(f"Fatal error: {e}")
        try:
            from core.notifier import telegram_send
            telegram_send(f"[kingbot] Fatal error: {e}")
        except Exception:
            pass
        sys.exit(1)
    log.info("kingbot exited cleanly")

if __name__ == "__main__":
    main()
