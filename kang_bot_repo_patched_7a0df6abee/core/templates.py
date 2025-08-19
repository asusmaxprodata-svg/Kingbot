
def badge(text, color):
    # color is emoji or text tag; kept simple for Telegram HTML
    return f"<b>{text}</b>"

def card_trade_open(mode, symbol, side, lev, entry, tp, sl, conf):
    return (
        f"📢 {badge(mode.upper(),'') } — <b>{side}</b>\n"
        f"Pair: <b>{symbol}</b> • Lev: <b>{lev}x</b>\n"
        f"Entry: <b>{entry:.4f}</b>\n"
        f"TP / SL: <b>{tp:.4f}</b> / <b>{sl:.4f}</b>\n"
        f"Confidence: <b>{conf:.1f}%</b>"
    )

def card_trade_close(mode, symbol, exit_price, pnl_pct, dur_min):
    color = "🟢" if pnl_pct>=0 else "🔴"
    return (
        f"✅ {badge('CLOSED','')} {color}\n"
        f"Pair: <b>{symbol}</b>\n"
        f"Exit: <b>{exit_price:.4f}</b>\n"
        f"PnL: <b>{pnl_pct:+.2f}%</b> • Durasi: <b>{int(dur_min)}m</b>"
    )

def card_daily_recap(trades, wr, pnl_pct, eq, mode):
    return (
        f"📊 <b>Daily Recap</b>\n"
        f"Mode: <b>{mode}</b>\n"
        f"Trades: <b>{trades}</b> • Winrate: <b>{wr:.1f}%</b>\n"
        f"Total PnL: <b>{pnl_pct:+.2f}%</b>\n"
        f"Equity: <b>${eq:.2f}</b>"
    )

def card_signal_preview(mode, symbol, action, prob, tp, sl, lev):
    return (
        f"🧠 <b>Signal Preview</b>\n"
        f"Mode: <b>{mode}</b> • Pair: <b>{symbol}</b>\n"
        f"Action: <b>{action}</b> • Prob: <b>{prob*100:.1f}%</b>\n"
        f"TP / SL: <b>{tp:.4f}</b> / <b>{sl:.4f}</b> • Lev: <b>{lev}x</b>"
    )
