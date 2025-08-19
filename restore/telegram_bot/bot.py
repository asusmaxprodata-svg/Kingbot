import os, asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

from core.logger import get_logger
from core.config_manager import get_mode, set_mode, get_leverage, set_leverage, set_testnet, set_symbol, get_symbol, add_watchlist, remove_watchlist, get_watchlist, set_auto_pairs, get_auto_pairs, get_pair_update_interval_min, set_pair_update_interval_min, clamp_leverage, get_leverage_cap_for_mode, set_running
from core.symbol_scanner import rank_symbols
from core.portfolio import equity

from core.utils import load_json, save_json
import utils.env_loader  # auto-load .env

def build_mode_summary(mode: str) -> str:
    g = load_json("config/global.json", {})
    m = load_json(f"config/{mode}.json", {})
    best = load_json(f"config/{mode}_best.json", {})
    st = load_json("data/state.json", {})
    # effective cfg: base m + best override
    eff = dict(m)
    for k,v in best.items():
        eff[k] = v if v not in (None, "") else eff.get(k)
    timeframe = eff.get("timeframe", m.get("timeframe","15m"))
    tp = eff.get("tp", g.get("default_tp", 0.02))
    sl = eff.get("sl", g.get("default_sl", 0.01))
    lev_cap = (g.get("leverage_cap") or {}).get(mode, "-")
    tp_split = eff.get("tp_split", {"tp1":0.5,"tp2":0.5,"breakeven_trigger":0.5})
    vol_gates = (eff.get("vol_gates") or {}).get(mode, None)
    notify = st.get("notify_level","detailed")
    auto_pairs = g.get("auto_pairs", True)
    topn = g.get("top_n", 3)
    symbols = g.get("symbols", [])
    env = "TESTNET ✅" if st.get("testnet", True) else "REAL ⚠️"
    lines = [
        f"🧭 Mode: {mode}",
        f"🛡️ Confidence: {g.get('confidence_threshold',0.80):.0%}",
        f"📊 Max Open Pos: {g.get('max_open_positions',3)}",
        f"⛔ Daily Max Loss: {g.get('daily_max_loss_fraction',0.10):.0%}",
        f"🌐 Env: {env}",
        f"⏱️ Timeframe: {timeframe}",
        f"🎯 TP/SL: {tp:.2%} / {sl:.2%}",
        f"📐 Leverage cap: {lev_cap}x",
        f"🪙 Pairs: {'Auto TopN' if auto_pairs else 'Manual'} (TopN={topn})",
        f"📜 Candidate: {', '.join(symbols)[:70]}{'...' if len(', '.join(symbols))>70 else ''}",
        f"🔔 Notif: {notify.capitalize()}",
    ]
    if tp_split:
        lines.append(f"✂️ TP split: TP1={tp_split.get('tp1',0.5):.0%} / TP2={tp_split.get('tp2',0.5):.0%} | BE@{tp_split.get('breakeven_trigger',0.5):.0%}")
    if vol_gates:
        try:
            lo, hi = vol_gates
            lines.append(f"📶 Vol gate: {lo:.2%}–{hi:.2%}")
        except Exception:
            pass
    return "\n".join(lines)


log = get_logger("telegram_bot")

def build_main_kb_full():
    mode = get_mode()
    lev = str(get_leverage())
    state = load_json("data/state.json", {})
    testnet = state.get("testnet", True)
    topn = load_json('config/global.json', {}).get('top_n', 3)
    auto_pairs = load_json('config/global.json', {}).get('auto_pairs', True)
    notify_level = load_json('data/state.json', {}).get('notify_level','detailed')
    buttons = [
        [InlineKeyboardButton("Scalping (5m)", callback_data="mode_scalping"),
         InlineKeyboardButton("Swing (1h)", callback_data="mode_swing")],
        [InlineKeyboardButton("Hybrid (15m)", callback_data="mode_hybrid"),
         InlineKeyboardButton("Adaptif", callback_data="mode_adaptive")],
        [InlineKeyboardButton("Lev 5x", callback_data="lev_5"),
         InlineKeyboardButton("10x", callback_data="lev_10"),
         InlineKeyboardButton("20x", callback_data="lev_20"),
         InlineKeyboardButton("50x", callback_data="lev_50"),
         InlineKeyboardButton("100x", callback_data="lev_100"),
         InlineKeyboardButton("Auto AI", callback_data="lev_auto")],
        [InlineKeyboardButton("Pairs: Auto TopN" if auto_pairs else "Pairs: Manual", callback_data="toggle_pairs"),
         InlineKeyboardButton(f"TopN={topn}", callback_data="topn_n")],
        [InlineKeyboardButton(f"🔔 Notif: {notify_level.capitalize()}", callback_data="toggle_notify"),
         InlineKeyboardButton("💰 Saldo", callback_data="menu_saldo"),
         InlineKeyboardButton("📈 Statistik", callback_data="menu_stats"),
         InlineKeyboardButton("📜 Riwayat", callback_data="menu_history"),
         InlineKeyboardButton("⚙️ Setting", callback_data="menu_setting")],
        [InlineKeyboardButton("Mode: TESTNET ✅" if testnet else "Mode: REAL 🚨", callback_data="toggle_env")]
    ]
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo, ini kang_bot. Gunakan tombol di bawah untuk kontrol.", reply_markup=build_main_kb_full()
    )

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pilih mode:", reply_markup=build_main_kb_full())

async def cmd_set_leverage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pilih leverage:", reply_markup=build_main_kb_full())


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "toggle_sim":
        st = load_json('data/state.json', {})
        cur = bool(st.get('simulation_mode', False))
        st['simulation_mode'] = not cur
        save_json('data/state.json', st)
        await q.edit_message_text(f"Simulation: {'On' if st['simulation_mode'] else 'Off'}", reply_markup=build_main_kb_full())
        return
    admin_id = int(os.getenv("TELEGRAM_ADMIN_USER_ID","0"))
    if data.startswith("mode_"):
        m = data.split("_",1)[1]
        set_mode(m)
        summary = build_mode_summary(m)
        await q.edit_message_text(summary, reply_markup=build_main_kb_full())
        return
    if data.startswith("lev_"):
        val = data.split("_",1)[1]
        set_leverage("auto" if val=="auto" else int(val))
        await q.edit_message_text(f"Leverage set ke: {val}", reply_markup=build_main_kb_full())
        return
    if data == "toggle_env":
        state = load_json("data/state.json", {})
        if state.get("testnet", True):
            await q.edit_message_text("Masukkan PIN untuk aktifkan REAL trading (balas dengan: PIN 1234)", reply_markup=build_main_kb_full())
        else:
            set_testnet(True)
            await q.edit_message_text("Berpindah ke TESTNET ✅", reply_markup=build_main_kb_full())
        return
    if data == "toggle_pairs":
        cfg = load_json("config/global.json", {})
        cfg["auto_pairs"] = not cfg.get("auto_pairs", True)
        save_json("config/global.json", cfg)
        await q.edit_message_text("Pairs mode diubah.", reply_markup=build_main_kb_full())
        return
    
        if data == "run_bot":
            # Safe: hanya izinkan RUN dari Telegram jika testnet True
            g = load_json("config/global.json", {})
            if g.get("testnet", True):
                set_running(True)
                await query.answer("Bot RUN (testnet).")
            else:
                await query.answer("RUN REAL hanya via Streamlit + PIN.", show_alert=True)
            await query.edit_message_reply_markup(reply_markup=build_main_kb_full())
            return
        if data == "pause_bot":
            set_running(False)
            await query.answer("Bot di-pause.")
            await query.edit_message_reply_markup(reply_markup=build_main_kb_full())
            return
        
        if data == "risk_close_all_yes":
            g = load_json("config/global.json", {})
            # CLOSE ALL allowed only in testnet via Telegram for safety
            if g.get("testnet", True):
                try:
                    # use a simple notifier; actual close logic assumed in trade_manager via a task flag
                    g["close_all_flag"] = True
                    save_json("config/global.json", g)
                    await query.answer("Close All dipicu (TESTNET).")
                except Exception:
                    await query.answer("Gagal set Close All.", show_alert=True)
            else:
                await query.answer("Close All REAL hanya dari Streamlit (PIN).", show_alert=True)
            await query.edit_message_reply_markup(reply_markup=build_main_kb_full())
            return
        if data == "ai_apply_best_yes":
            # set a flag for run loop to apply best config (safer than doing heavy I/O in callback)
            try:
                g = load_json("config/global.json", {})
                g["apply_best_flag"] = True
                save_json("config/global.json", g)
                await query.answer("Apply Best dipicu. Run loop akan mengeksekusi.", show_alert=False)
            except Exception:
                await query.answer("Gagal set apply flag.", show_alert=True)
            await query.edit_message_reply_markup(reply_markup=build_main_kb_full())
            return

        if data == "lev_5":
            val = int("lev_5".split("_")[1])
            val = clamp_leverage(get_mode(), val)
            set_leverage(val)
            await query.edit_message_reply_markup(reply_markup=build_leverage_kb())
            return
        if data == "lev_10":
            val = int("lev_10".split("_")[1])
            val = clamp_leverage(get_mode(), val)
            set_leverage(val)
            await query.edit_message_reply_markup(reply_markup=build_leverage_kb())
            return
        if data == "lev_20":
            val = int("lev_20".split("_")[1])
            val = clamp_leverage(get_mode(), val)
            set_leverage(val)
            await query.edit_message_reply_markup(reply_markup=build_leverage_kb())
            return
        if data == "lev_50":
            val = int("lev_50".split("_")[1])
            val = clamp_leverage(get_mode(), val)
            set_leverage(val)
            await query.edit_message_reply_markup(reply_markup=build_leverage_kb())
            return
        if data == "lev_100":
            val = int("lev_100".split("_")[1])
            val = clamp_leverage(get_mode(), val)
            set_leverage(val)
            await query.edit_message_reply_markup(reply_markup=build_leverage_kb())
            return
        if data == "lev_auto":
            set_leverage("auto")
            await query.edit_message_reply_markup(reply_markup=build_leverage_kb())
            return
        if data == "topn_n":
            cfg = load_json("config/global.json", {})
            n = int(cfg.get("top_n", 3))
            n = 1 if n >= 5 else n + 1
            cfg["top_n"] = n
            save_json("config/global.json", cfg)
            await query.answer(f"TopN diubah ke {n}.")
            await query.edit_message_reply_markup(reply_markup=build_main_kb_full())
            return

    if data == "menu_saldo":
        state = load_json("data/state.json", {})
        testnet = state.get("testnet", True)
        try:
            from pybit.unified_trading import HTTP
            http = HTTP(testnet=testnet, api_key=os.getenv("BYBIT_API_KEY"), api_secret=os.getenv("BYBIT_API_SECRET"))
            wb = http.get_wallet_balance(accountType="UNIFIED")
            total = wb.get("result",{}).get("list",[{}])[0].get("totalEquity","-")
            await q.edit_message_text(f"Total Equity (Bybit): {total}", reply_markup=build_main_kb_full())
        except Exception as e:
            await q.edit_message_text(f"Gagal ambil saldo: {e}", reply_markup=build_main_kb_full())
        return
    if data == "menu_stats":
        d = load_json("data/profit.json", {})
        eq = d.get("equity", 0.0)
        hist = d.get("history", [])
        wins = sum(1 for h in hist if h.get("pnl",0)>0)
        loss = sum(1 for h in hist if h.get("pnl",0)<0)
        winrate = (wins/(wins+loss)) if (wins+loss)>0 else 0.0
        tot_profit = sum(h.get("pnl",0.0) for h in hist)
        msg = f"Equity: {eq}\nTrades: {len(hist)}\nWinrate: {winrate:.2%}\nTotal Profit: {tot_profit:.4f}"
        await q.edit_message_text(msg, reply_markup=build_main_kb_full())
        return
    if data == "menu_history":
        d = load_json("data/profit.json", {})
        hist = d.get("history", [])[-10:]
        lines = []
        for h in hist:
            lines.append(f"{h.get('ts','')} | {h.get('symbol','')} | {h.get('side','')} | pnl={h.get('pnl',0)}")
        msg = "Riwayat (10 terakhir):\n" + ("\n".join(lines) if lines else "Kosong")
        await q.edit_message_text(msg, reply_markup=build_main_kb_full())
        return
    # default
    await q.edit_message_text(f"Menu {data}", reply_markup=build_main_kb_full())

    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "toggle_sim":
        st = load_json('data/state.json', {})
        cur = bool(st.get('simulation_mode', False))
        st['simulation_mode'] = not cur
        save_json('data/state.json', st)
        await q.edit_message_text(f"Simulation: {'On' if st['simulation_mode'] else 'Off'}", reply_markup=build_main_kb_full())
        return
    admin_id = int(os.getenv("TELEGRAM_ADMIN_USER_ID","0"))
    pin_required = data == "toggle_env" and q.from_user.id == admin_id
    if data.startswith("mode_"):
        m = data.split("_",1)[1]
        set_mode(m)
        summary = build_mode_summary(m)
        await q.edit_message_text(summary, reply_markup=build_main_kb_full())
    elif data.startswith("lev_"):
        val = data.split("_",1)[1]
        set_leverage("auto" if val=="auto" else int(val))
        await q.edit_message_text(f"Leverage set ke: {val}", reply_markup=build_main_kb_full())
    elif data == "toggle_env":
        # PIN gate for REAL
        state = load_json("data/state.json", {})
        if state.get("testnet", True):
            await q.edit_message_text("Masukkan PIN untuk aktifkan REAL trading (balas dengan: PIN 1234)", reply_markup=build_main_kb_full())
        else:
            # switch back to testnet freely
            set_testnet(True)
            await q.edit_message_text("Berpindah ke TESTNET ✅", reply_markup=build_main_kb_full())
    elif data.startswith("menu_"):
        await q.edit_message_text(f"Menu {data}", reply_markup=build_main_kb_full())

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle PIN
    text = (update.message.text or "").strip()
    if text.upper().startswith("PIN"):
        parts = text.split()
        if len(parts) >= 2:
            pin = parts[1]
            if pin == os.getenv("TELEGRAM_REAL_TRADE_PIN","0000") and str(update.effective_user.id) == os.getenv("TELEGRAM_ADMIN_USER_ID",""):
                set_testnet(False)
                await update.message.reply_text("REAL trading AKTIF 🚨", reply_markup=build_main_kb_full())
            else:
                await update.message.reply_text("PIN salah atau bukan admin.", reply_markup=build_main_kb_full())



async def cmd_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /pair BTCUSDT
    try:
        sym = context.args[0].upper()
    except Exception:
        await update.message.reply_text("Format: /pair BTCUSDT")
        return
    set_symbol(sym)
    # ensure in watchlist
    add_watchlist(sym)
    await update.message.reply_text(f"Pair aktif diset ke {sym}", reply_markup=build_main_kb_full())

async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /watchlist add SOLUSDT  or  /watchlist remove SOLUSDT
    if not context.args:
        wl = get_watchlist()
        await update.message.reply_text("Watchlist: " + ", ".join(wl), reply_markup=build_main_kb_full())
        return
    action = context.args[0].lower()
    if action == "add" and len(context.args)>=2:
        add_watchlist(context.args[1].upper())
        await update.message.reply_text("Ditambahkan.", reply_markup=build_main_kb_full())
    elif action == "remove" and len(context.args)>=2:
        remove_watchlist(context.args[1].upper())
        await update.message.reply_text("Dihapus.", reply_markup=build_main_kb_full())
    else:
        await update.message.reply_text("Format: /watchlist add|remove SYMBOL")

async def cmd_auto_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /auto_pair on|off
    if not context.args:
        await update.message.reply_text(f"Auto Pair saat ini: {'ON' if get_auto_pairs() else 'OFF'}")
        return
    flag = context.args[0].lower() in ["on","true","1","yes","ya"]
    set_auto_pairs(flag)
    await update.message.reply_text(f"Auto Pair {'ON' if flag else 'OFF'}", reply_markup=build_main_kb_full())


async def cmd_pair_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /pair_update 15
    if not context.args:
        cur = get_pair_update_interval_min()
        await update.message.reply_text(f"Interval update pair saat ini: {cur} menit", reply_markup=build_main_kb_full())
        return
    try:
        m = int(context.args[0])
    except Exception:
        await update.message.reply_text("Format: /pair_update <menit> (1-180)", reply_markup=build_main_kb_full())
        return
    set_pair_update_interval_min(m)
    cur = get_pair_update_interval_min()
    await update.message.reply_text(f"Interval update pair diset ke {cur} menit ✅", reply_markup=build_main_kb_full())


def build_leverage_kb():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    cur = get_leverage()
    mode = get_mode()
    cap = get_leverage_cap_for_mode(mode)
    label_cur = f"Leverage: {cur}x (Cap {cap}x)" if isinstance(cur, (int, float)) else f"Leverage: {cur} (Cap {cap}x)"
    rows = [
        [InlineKeyboardButton(text=label_cur, callback_data="noop")],
        [
            InlineKeyboardButton(text="5x",  callback_data="lev_5"),
            InlineKeyboardButton(text="10x", callback_data="lev_10"),
            InlineKeyboardButton(text="20x", callback_data="lev_20")
        ],
        [
            InlineKeyboardButton(text="50x",  callback_data="lev_50"),
            InlineKeyboardButton(text="100x", callback_data="lev_100"),
            InlineKeyboardButton(text="Auto AI", callback_data="lev_auto")
        ],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(rows)


async def cmd_leverage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /leverage <angka|auto>
    if not context.args:
        cur = get_leverage()
        await update.message.reply_text(f"Leverage saat ini: {cur}", reply_markup=build_leverage_kb())
        return
    val = context.args[0].lower()
    if val in ["auto","ai","autoai"]:
        set_leverage("auto")
        await update.message.reply_text("Leverage diset ke Auto AI ✅", reply_markup=build_leverage_kb())
        return
    try:
        x = int(val)
        if x not in [1,2,3,5,10,20,50,100]:
            await update.message.reply_text("Pilih leverage 1/2/3/5/10/20/50/100 atau 'auto'", reply_markup=build_leverage_kb())
            return
        set_leverage(x)
        await update.message.reply_text(f"Leverage diset ke {x}x ✅", reply_markup=build_leverage_kb())
    except Exception:
        await update.message.reply_text("Format: /leverage <angka|auto>", reply_markup=build_leverage_kb())


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = load_json("config/global.json", {})
    if g.get("testnet", True):
        set_running(True)
        await update.message.reply_text("Bot RUN (testnet).")
    else:
        await update.message.reply_text("RUN REAL hanya via Streamlit (PIN).")

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_running(False)
    await update.message.reply_text("Bot di-pause.")



async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /alerts on|off
    g = load_json("config/global.json", {})
    a = g.get("alerts", {})
    if not context.args:
        state = "ON" if a.get("enabled", True) else "OFF"
        await update.message.reply_text(f"Alerts: {state}")
        return
    flag = context.args[0].lower() in ["on","true","1","yes","ya"]
    a["enabled"] = flag
    g["alerts"] = a
    save_json("config/global.json", g)
    await update.message.reply_text(f"Alerts {'ON' if flag else 'OFF'} ✅")

async def cmd_imbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /imbalance 20
    g = load_json("config/global.json", {})
    a = g.get("alerts", {})
    try:
        val = float(context.args[0])
        a["imbalance_pct"] = max(5.0, min(80.0, val))
        g["alerts"] = a
        save_json("config/global.json", g)
        await update.message.reply_text(f"Imbalance threshold di-set {a['imbalance_pct']}% ✅")
    except Exception:
        await update.message.reply_text("Format: /imbalance <persen>, contoh: /imbalance 25")

async def cmd_spread(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /spread 6
    g = load_json("config/global.json", {})
    a = g.get("alerts", {})
    try:
        val = float(context.args[0])
        a["spread_bps"] = max(1.0, min(50.0, val))
        g["alerts"] = a
        save_json("config/global.json", g)
        await update.message.reply_text(f"Spread threshold di-set {a['spread_bps']} bps ✅")
    except Exception:
        await update.message.reply_text("Format: /spread <bps>, contoh: /spread 6")



def build_notify_kb():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    g = load_json("config/global.json", {})
    rows = [
        [InlineKeyboardButton(text=f"Preview: {'ON' if g.get('preview_enabled', True) else 'OFF'}", callback_data="toggle_preview")],
        [InlineKeyboardButton(text=f"Heartbeat: {'ON' if g.get('heartbeat_enabled', True) else 'OFF'}", callback_data="toggle_heartbeat")],
        [InlineKeyboardButton(text=f"Hourly Recap: {'ON' if g.get('hourly_recap_enabled', True) else 'OFF'}", callback_data="toggle_hourly")],
        [InlineKeyboardButton(text=f"Daily Recap: {'ON' if g.get('daily_recap_enabled', True) else 'OFF'}", callback_data="toggle_daily")],
        [InlineKeyboardButton(text=f"Alerts: {'ON' if g.get('alerts',{}).get('enabled', True) else 'OFF'}", callback_data="alerts_toggle")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(rows)

def build_alerts_kb():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    g = load_json("config/global.json", {})
    a = g.get("alerts", {})
    enabled = a.get("enabled", True)
    imb = a.get("imbalance_pct", 20.0)
    spr = a.get("spread_bps", 6.0)
    rows = [
        [InlineKeyboardButton(text=f"Alerts: {'ON' if enabled else 'OFF'}", callback_data="alerts_toggle")],
        [InlineKeyboardButton(text=f"Imbalance: {imb:.1f}%", callback_data="noop")],
        [
            InlineKeyboardButton(text="−5%", callback_data="alerts_imb_dec"),
            InlineKeyboardButton(text="+5%", callback_data="alerts_imb_inc")
        ],
        [InlineKeyboardButton(text=f"Spread: {spr:.1f} bps", callback_data="noop")],
        [
            InlineKeyboardButton(text="−1 bps", callback_data="alerts_spr_dec"),
            InlineKeyboardButton(text="+1 bps", callback_data="alerts_spr_inc")
        ],
        [InlineKeyboardButton(text="🔄 Reset", callback_data="alerts_reset")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(rows)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = build_main_kb_full()
    await update.message.reply_text("Kang Bot — Control Panel", reply_markup=kb)



async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    g = load_json("config/global.json", {})
    at = g.get("auto_tune", {})
    if at.get("await_symbols_input"):
        raw = update.message.text.strip()
        syms = [s.strip().upper() for s in raw.replace(";", ",").split(",") if s.strip()]
        if syms:
            at["symbols"] = syms
            at["await_symbols_input"] = False
            g["auto_tune"] = at
            save_json("config/global.json", g)
            await update.message.reply_text(f"✅ Symbols manual di-set: {', '.join(syms)}")
        else:
            await update.message.reply_text("Format tidak dikenali. Contoh: BTCUSDT,ETHUSDT,SOLUSDT")


async def set_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message:
            return
        args = context.args if hasattr(context, "args") else []
        if not args or len(args) != 1 or ":" not in args[0]:
            await update.message.reply_text("Gunakan format: /set_time HH:MM (WIB)")
            return
        hhmm = args[0].strip()
        try:
            hour_str, minute_str = hhmm.split(":")
            hour = int(hour_str)
            minute = int(minute_str)
        except Exception:
            await update.message.reply_text("Format tidak valid. Contoh: /set_time 01:30")
            return
        if not (0 <= hour < 24 and 0 <= minute < 60):
            await update.message.reply_text("Jam/menit di luar rentang (0-23 / 0-59).")
            return

        g = load_json("config/global.json", {})
        at = g.get("auto_tune", {})
        at["hour"] = hour
        at["minute"] = minute
        g["auto_tune"] = at
        save_json("config/global.json", g)

        ok = False
        try:
            ok = reschedule_autotune()
        except Exception:
            ok = False

        if ok:
            await update.message.reply_text(f"✅ Jadwal auto-tune diubah ke {hour:02d}:{minute:02d} WIB dan dijadwalkan ulang.")
        else:
            await update.message.reply_text("⚠️ Jadwal disimpan, tapi gagal menjadwalkan ulang. Coba restart bot.")
    except Exception as e:
        try:
            await update.message.reply_text(f"Error: {e}")
        except Exception:
            pass

def build_app(
):
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("set_leverage", cmd_set_leverage))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("settings", start))
    app.add_handler(CommandHandler("saldo", start))
    app.add_handler(CommandHandler("statistik", start))
    app.add_handler(CommandHandler("riwayat", start))
    app.add_handler(CommandHandler("setting", start))
    app.add_handler(CommandHandler("mode_testnet", start))
    app.add_handler(CommandHandler("mode_real", start))
    app.add_handler(CommandHandler("set_leverage", cmd_set_leverage))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pair", cmd_pair))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("auto_pair", cmd_auto_pair))
    app.add_handler(CommandHandler("pair_update", cmd_pair_update))
    app.add_handler(CommandHandler("leverage", cmd_leverage))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("imbalance", cmd_imbalance))
    app.add_handler(CommandHandler("spread", cmd_spread))
    # text messages for PIN
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app

if __name__ == "__main__":
    app = build_app()
    app.run_polling()


from telegram.ext import CommandHandler

async def on_env(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = (context.args or [])
    if not args:
        st = load_json('data/state.json', {})
        cur = 'REAL' if not st.get('testnet', True) else 'TESTNET'
        await update.message.reply_text(f"Env saat ini: {cur}. Gunakan /env testnet atau /env real")
        return
    val = args[0].lower()
    st = load_json('data/state.json', {})
    if val in ('real','live'):
        st['testnet'] = False
    elif val in ('testnet','paper'):
        st['testnet'] = True
    else:
        await update.message.reply_text("Argumen tidak dikenal. Gunakan: /env testnet | /env real")
        return
    save_json('data/state.json', st)
    await update.message.reply_text(f"Env di-set ke: {'REAL' if not st['testnet'] else 'TESTNET'}")

# register handler (append to app builder if exists)
try:
    application.add_handler(CommandHandler("env", on_env))
except Exception:
    pass


from telegram.ext import CommandHandler
import subprocess, sys, os, pathlib

async def on_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong — bot online.")

async def on_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ver = pathlib.Path("VERSION").read_text().strip()
    except Exception:
        ver = "(unknown)"
    await update.message.reply_text(f"Version: {ver}")

async def on_diag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Menjalankan self-test... (±5s)")
    try:
        proc = subprocess.run([sys.executable, "tools/self_test.py"], capture_output=True, text=True, timeout=20)
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        lines = [l for l in out.splitlines() if l.strip()]
        tail = "\n".join(lines[-40:]) if lines else "(no output)"
        status = "✅ PASSED" if "SELF-TEST PASSED" in out and proc.returncode == 0 else "❌ FAILED"
        await update.message.reply_text(f"[Self-Test] {status}\n```\n{tail}\n```", parse_mode="Markdown")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Self-test timeout.")
    except Exception as e:
        await update.message.reply_text(f"❌ Self-test error: {e}")

try:
    application.add_handler(CommandHandler("ping", on_ping))
    application.add_handler(CommandHandler("version", on_version))
    application.add_handler(CommandHandler("diag", on_diag))
except Exception:
    pass


from telegram.ext import CommandHandler

async def on_sim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = (context.args or [])
    st = load_json('data/state.json', {})
    if not args:
        await update.message.reply_text(f"Simulation mode: {'On' if st.get('simulation_mode', False) else 'Off'}\nGunakan: /sim on | /sim off")
        return
    val = args[0].lower()
    if val in ('on','true','1'):
        st['simulation_mode'] = True
    elif val in ('off','false','0'):
        st['simulation_mode'] = False
    else:
        await update.message.reply_text("Argumen tidak dikenal. Gunakan: /sim on | /sim off")
        return
    save_json('data/state.json', st)
    await update.message.reply_text(f"Simulation mode di-set: {'On' if st['simulation_mode'] else 'Off'}")

try:
    application.add_handler(CommandHandler("sim", on_sim))
except Exception:
    pass


import hashlib
from telegram.ext import CommandHandler

def _sha(txt: str) -> str: 
    return hashlib.sha256(txt.encode()).hexdigest()

async def on_set_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /set_pin 123456
    if not context.args:
        await update.message.reply_text("Gunakan: /set_pin <kode_pin>")
        return
    pin = context.args[0]
    st = load_json('data/state.json', {})
    st['pin_hash'] = _sha(pin)
    st['pin_verified'] = False
    save_json('data/state.json', st)
    await update.message.reply_text("PIN disimpan. Verifikasi dengan: /pin <kode_pin>")

async def on_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /pin 123456
    if not context.args:
        await update.message.reply_text("Gunakan: /pin <kode_pin>")
        return
    pin = context.args[0]
    st = load_json('data/state.json', {})
    ok = (st.get('pin_hash') == _sha(pin))
    st['pin_verified'] = bool(ok)
    save_json('data/state.json', st)
    await update.message.reply_text("PIN benar. Akses REAL dibuka." if ok else "PIN salah.")

# Override /env handler to enforce PIN when switching to REAL
async def on_env(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = (context.args or [])
    st = load_json('data/state.json', {})
    if not args:
        cur = 'REAL' if not st.get('testnet', True) else 'TESTNET'
        await update.message.reply_text(f"Env saat ini: {cur}. Gunakan /env testnet atau /env real")
        return
    val = args[0].lower()
    if val in ('real','live'):
        if not st.get('pin_verified', False) or not st.get('pin_hash'):
            await update.message.reply_text("REAL mode memerlukan PIN. Set PIN dengan /set_pin <kode>, lalu /pin <kode> dan ulangi /env real.")
            return
        st['testnet'] = False
    elif val in ('testnet','paper'):
        st['testnet'] = True
    else:
        await update.message.reply_text("Argumen tidak dikenal. Gunakan: /env testnet | /env real")
        return
    save_json('data/state.json', st)
    await update.message.reply_text(f"Env di-set ke: {'REAL' if not st['testnet'] else 'TESTNET'}")

try:
    application.add_handler(CommandHandler("set_pin", on_set_pin))
    application.add_handler(CommandHandler("pin", on_pin))
except Exception:
    pass

def build_autotune_pairs_kb():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    g = load_json("config/global.json", {})
    auto = g.get("auto_tune", {})
    use_auto = auto.get("use_auto_pairs", True)
    top_n = int(auto.get("top_n", 2))
    syms = ", ".join(auto.get("symbols", [])) or "-"
    rows = [
        [InlineKeyboardButton(text=f"Source: {'AUTO (scanner)' if use_auto else 'MANUAL'}", callback_data="auto_src_toggle")],
        [InlineKeyboardButton(text=f"Top-N: {top_n}", callback_data="noop"),
         InlineKeyboardButton(text="➖", callback_data="auto_top_dec"),
         InlineKeyboardButton(text="➕", callback_data="auto_top_inc")],
        [InlineKeyboardButton(text=f"Symbols (manual): {syms}", callback_data="auto_syms_edit")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_ai_menu")]
    ]
    rows.append([InlineKeyboardButton("🕒 Set Time (WIB)", callback_data="menu_set_time")])
    return InlineKeyboardMarkup(rows)



def build_set_time_kb():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    g = load_json("config/global.json", {})
    at = g.get("auto_tune", {})
    hour = int(at.get("hour", 1))
    minute = int(at.get("minute", 0))

    rows = [
        [InlineKeyboardButton(text=f"Hour: {hour:02d}", callback_data="noop"),
         InlineKeyboardButton(text="➖", callback_data="time_hour_dec"),
         InlineKeyboardButton(text="➕", callback_data="time_hour_inc")],
        [InlineKeyboardButton(text=f"Minute: {minute:02d}", callback_data="noop"),
         InlineKeyboardButton(text="➖", callback_data="time_min_dec"),
         InlineKeyboardButton(text="➕", callback_data="time_min_inc")],
        [InlineKeyboardButton(text="✅ Save (WIB)", callback_data="time_save"),
         InlineKeyboardButton(text="⬅️ Back", callback_data="menu_autotune_pairs")]
    ]
    return InlineKeyboardMarkup(rows)