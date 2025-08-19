import os, time
import pandas as pd
import streamlit as st
import os
_pwd=os.getenv('STREAMLIT_PASSWORD')
if _pwd:
    _in=st.sidebar.text_input('Password', type='password')
    if _in!=_pwd:
        st.warning('Enter correct password to view dashboard'); st.stop()
from utils import jload, jsave, set_state_key, update_global_config
from components.charts import equity_curve, winrate_bar, pnl_bar, candles_with_trades
from components.panels import stat_card
import utils.env_loader  # auto-load .env

st.set_page_config(page_title="kang_bot Dashboard", page_icon="🤖", layout="wide")

# ---------- THEME ----------
st.markdown("""
<style>
.reportview-container .main {background-color: #0b1020; color: #fff;}
.stButton>button {border-radius: 12px; padding: 8px 14px; font-weight:600}
.block-container {padding-top: 1rem;}
</style>
""", unsafe_allow_html=True)

# ---------- DATA ----------
profit = jload("data/profit.json", {"starting_capital":30.0,"equity":30.0,"history":[]})
state  = jload("data/state.json", {"mode":"hybrid","testnet": True, "notify_level":"detailed"})
gcfg   = jload("config/global.json", {})
mode   = state.get("mode","hybrid")
mcfg   = jload(f"config/{mode}.json", {})
best   = jload(f"config/{mode}_best.json", {})

# Effective config merge
eff = dict(mcfg); eff.update(best or {})

# ---------- SIDEBAR CONTROLS ----------
# ---------- LIVE SOCKET ----------
st.sidebar.divider()
st.sidebar.subheader("Live Socket")
live_on = st.sidebar.toggle("Enable Live WS", value=False, help="Tarik snapshot via WebSocket")
ws_url = st.sidebar.text_input("WS URL", value="ws://localhost:8765", help="Jalankan: python streamlit_app/ws_server.py")
if live_on:
    try:
        from ws_client import fetch_once
        live = fetch_once(ws_url, timeout=1.5)
        if live:
            profit = live and {"starting_capital": live.get("starting_capital",30.0), "equity": live.get("equity",0.0), "history": live.get("history",[])}
            state = live.get("state", state)
            gcfg = live.get("global", gcfg)
            st.sidebar.success("Live ✓")
        else:
            st.sidebar.warning("No live data")
    except Exception as e:
        st.sidebar.error(f"WS error: {e}")

# ---------- DATE FILTER ----------
st.sidebar.divider()
st.sidebar.subheader("Date Filter")
import datetime as _dt
today_dt = _dt.date.today()
start_date = st.sidebar.date_input("Start", value=today_dt - _dt.timedelta(days=7))
end_date   = st.sidebar.date_input("End", value=today_dt)
def _in_range(ts_epoch):
    try:
        d = _dt.datetime.utcfromtimestamp(float(ts_epoch)).date()
        return start_date <= d <= end_date
    except Exception:
        return True

st.sidebar.header("Controls")
colA, colB = st.sidebar.columns(2)
with colA:
    env = st.toggle("REAL Trading", value=not state.get("testnet", True), help="Matikan untuk TESTNET")
    set_state_key("testnet", not env and True or False)  # Streamlit toggles True→REAL
with colB:
    paused = st.toggle("Pause", value=state.get("paused", False), help="Hentikan entry baru")
    set_state_key("paused", paused)

mode_sel = st.sidebar.selectbox("Mode", ["scalping","swing","hybrid","adaptive"], index=["scalping","swing","hybrid","adaptive"].index(mode))
if mode_sel != mode:
    set_state_key("mode", mode_sel)
    mode = mode_sel
    eff = jload(f"config/{mode}.json", {})
    e2  = jload(f"config/{mode}_best.json", {}); eff.update(e2 or {})

conf = st.sidebar.slider("Confidence Threshold", 0.5, 0.99, float(gcfg.get("confidence_threshold", 0.80)), 0.01)
mol  = st.sidebar.number_input("Max Open Positions", 1, 10, int(gcfg.get("max_open_positions",3)), 1)
dml  = st.sidebar.slider("Daily Max Loss", 0.02, 0.30, float(gcfg.get("daily_max_loss_fraction",0.10)), 0.01, help="Auto-pause jika tercapai")
if st.sidebar.button("Save Risk Settings"):
    update_global_config({"confidence_threshold": conf, "max_open_positions": int(mol), "daily_max_loss_fraction": float(dml)})
    st.sidebar.success("Saved")

st.sidebar.divider()
auto_pairs = st.sidebar.toggle("Auto TopN Pairs", value=gcfg.get("auto_pairs", True))
topn = st.sidebar.slider("Top N", 1, 5, int(gcfg.get("top_n",3)))
if st.sidebar.button("Save Pairs Settings"):
    update_global_config({"auto_pairs": bool(auto_pairs), "top_n": int(topn)})
    st.sidebar.success("Saved")

st.sidebar.divider()
notif = st.sidebar.selectbox("Notify Level", ["detailed","brief"], index=["detailed","brief"].index(state.get("notify_level","detailed")))
if st.sidebar.button("Apply Notify Level"):
    set_state_key("notify_level", notif)
    st.sidebar.success("Applied")

# ---------- HEADER SUMMARY ----------
c1,c2,c3,c4 = st.columns(4)
stat_card("Equity", f"{profit.get('equity',0.0):.4f} USDT")
wr_today = 0.0
today = [h for h in profit.get('history',[]) if h.get('status')=='CLOSED' and h.get('ts_epoch',0) >= time.time()-24*3600]
if today:
    wr_today = sum(1 for h in today if h.get('pnl',0)>0) / max(1,len(today))
stat_card("24h Winrate", f"{wr_today*100:.1f}%")
stat_card("Mode", mode.capitalize())
stat_card("Env", "REAL ⚠️" if not state.get("testnet", True) else "TESTNET ✅")

# ---------- MAIN LAYOUT ----------
left, right = st.columns([2,1])

with left:
    # Equity
    import pandas as pd
    hist = pd.DataFrame(profit.get("history", []))
    if not hist.empty and 'ts_epoch' in hist.columns:
        hist = hist[hist['ts_epoch'].apply(_in_range)]
    fig_eq = equity_curve(hist if not hist.empty else pd.DataFrame(), profit.get("starting_capital",30.0))
    st.plotly_chart(fig_eq, use_container_width=True)
    # Candles + Trades (optional fetch if internet disabled, we fallback to empty)
    symbols = gcfg.get("symbols", [gcfg.get("symbol","BTCUSDT")])
    sel = st.multiselect("Symbols", symbols, default=symbols[:2])
    if not sel:
        sel = symbols[:1]
    try:
        from core.data_pipeline import fetch_klines
    except Exception:
        fetch_klines = None
    tabs = st.tabs([s for s in sel])
    for i, sym in enumerate(sel):
        with tabs[i]:
            dfc = pd.DataFrame()
            if fetch_klines:
                try:
                    dfc = fetch_klines(sym, eff.get("timeframe","15m"), limit=300, testnet=state.get("testnet", True))
                except Exception:
                    dfc = pd.DataFrame()
            fig_cd = candles_with_trades(dfc if not dfc.empty else pd.DataFrame(), hist if not hist.empty else pd.DataFrame(), sym)
            st.plotly_chart(fig_cd, use_container_width=True)

with right:
    # Per-mode stats
    from core.reporting import per_mode_stats
    stats = per_mode_stats()
    st.plotly_chart(winrate_bar(stats), use_container_width=True)
    st.plotly_chart(pnl_bar(stats), use_container_width=True)

st.divider()
st.subheader("Recent Trades")
if 'history' in profit and len(profit['history'])>0:
    dfh = pd.DataFrame(profit['history']).fillna("")
    st.dataframe(dfh.tail(50), use_container_width=True, height=320)
else:
    st.info("Belum ada riwayat trade.")

st.caption("kang_bot • Streamlit dashboard — live view dari file config & data bot di VPS")
