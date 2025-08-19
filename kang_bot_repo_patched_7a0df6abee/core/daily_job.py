import os, datetime
from .reporting import per_mode_stats, save_equity_chart
from .notifier import telegram_send, telegram_send_photo_direct
from .logger import get_logger

log = get_logger("daily_job")

def run():
    stats = per_mode_stats()
    if not stats:
        telegram_send("[kang_bot] Daily stats: belum ada data closed trades.")
        return
    lines = []
    for m, s in stats.items():
        lines.append(f"{m}: trades={s['trades']}, winrate={s['winrate']:.2%}, pnl={s['pnl']:.4f}, sharpe~={s['sharpe_like']:.2f}")
    msg = "[kang_bot] Daily stats\n" + "\n".join(lines)
    telegram_send(msg)
    # Chart
    path = "/mnt/data/equity.png"
    try:
        p = save_equity_chart(path)
        if p:
            telegram_send_photo_direct(p, caption="Equity curve")
    except Exception as e:
        log.warning(f"chart send failed: {e}")

if __name__ == "__main__":
    run()
