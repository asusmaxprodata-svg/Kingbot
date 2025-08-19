
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="Strategy Sim Lab", layout="wide")
st.title("🧪 Strategy Sim Lab")

DATA_ROOT = Path("data")
CFG_ROOT = Path("config")

def load_csv(symbol: str, tf: str):
    p = DATA_ROOT / f"{symbol}_{tf}.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
        if "start" in df.columns:
            if np.issubdtype(df["start"].dtype, np.number):
                df["start"] = pd.to_datetime(df["start"], unit="ms", utc=True).dt.tz_localize(None)
            else:
                df["start"] = pd.to_datetime(df["start"], errors="coerce")
        return df.dropna()
    except Exception as e:
        st.error(f"Gagal baca CSV: {e}")
        return None

def indicators(df):
    d = df.copy()
    d["ema_fast"] = d["close"].ewm(span=10, adjust=False).mean()
    d["ema_slow"] = d["close"].ewm(span=30, adjust=False).mean()
    ema12 = d["close"].ewm(span=12, adjust=False).mean()
    ema26 = d["close"].ewm(span=26, adjust=False).mean()
    d["macd"] = ema12 - ema26
    d["macd_sig"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_sig"]
    delta = d["close"].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -delta.clip(upper=0).rolling(14).mean()
    rs = up/(down+1e-9)
    d["rsi"] = 100 - (100/(1+rs))
    tr = np.maximum(d["high"]-d["low"], np.maximum((d["high"]-d["close"].shift()).abs(), (d["low"]-d["close"].shift()).abs()))
    d["atr"] = tr.rolling(14).mean().fillna(method="bfill")
    d["ret"] = d["close"].pct_change().fillna(0)
    d["vol"] = d["ret"].rolling(30).std().fillna(method="bfill")
    return d

def gpt_score(row):
    trend = np.tanh((row["ema_fast"] - row["ema_slow"]) / (row["ema_slow"]+1e-9))
    mom = np.tanh(row["macd_hist"] / (row["close"]*1e-3 + 1e-9))
    vol = np.tanh(row["vol"]*1000)
    return 0.6*trend + 0.3*mom + 0.1*vol

def xgb_prob(row, gpt_out):
    z = 2.0*gpt_out + 0.8*np.tanh((row["rsi"]-50)/20) + 0.6*np.tanh(row["macd"]/ (row["close"]*1e-3 + 1e-9))
    p = 1/(1+np.exp(-z))
    return p

def simulate(df, tp_pct, sl_pct, conf_thr=0.75, lev=10, trailing=True, max_open=1):
    pos = []
    trades = []
    for i in range(60, len(df)):  # warmup
        row = df.iloc[i]
        g = gpt_score(row)
        p_buy = xgb_prob(row, g)
        # action
        if p_buy >= conf_thr:
            action = "BUY"
        elif (1-p_buy) >= conf_thr:
            action = "SELL"
        else:
            action = "SKIP"
        # open
        if action in ["BUY","SELL"] and len(pos) < max_open:
            entry = row["close"]
            direction = 1 if action=="BUY" else -1
            tp = entry * (1 + direction*tp_pct/100)
            sl = entry * (1 - direction*sl_pct/100)
            trades.append({"ts": row["start"], "side": action, "entry": float(entry), "tp": float(tp), "sl": float(sl), "lev": lev})
            pos.append({"side": direction, "entry": entry, "tp": tp, "sl": sl, "trail": None})
        # manage
        new_pos = []
        for p in pos:
            hi = row["high"]; lo = row["low"]
            closed = False
            if trailing:
                if p["trail"] is None: p["trail"] = p["sl"]
                if p["side"]==1:
                    p["trail"] = max(p["trail"], row["close"]*(1 - sl_pct/100))
                    p["sl"] = max(p["sl"], p["trail"])
                else:
                    p["trail"] = min(p["trail"], row["close"]*(1 + sl_pct/100))
                    p["sl"] = min(p["sl"], p["trail"])
            # exits
            if p["side"]==1:
                if lo <= p["sl"]:
                    pnl = (p["sl"] - p["entry"])/p["entry"] * lev * 100
                    trades[-1]["exit"] = float(p["sl"]); trades[-1]["pnl_pct"] = float(pnl); closed=True
                elif hi >= p["tp"]:
                    pnl = (p["tp"] - p["entry"])/p["entry"] * lev * 100
                    trades[-1]["exit"] = float(p["tp"]); trades[-1]["pnl_pct"] = float(pnl); closed=True
            else:
                if hi >= p["sl"]:
                    pnl = (p["entry"] - p["sl"])/p["entry"] * lev * 100
                    trades[-1]["exit"] = float(p["sl"]); trades[-1]["pnl_pct"] = float(pnl); closed=True
                elif lo <= p["tp"]:
                    pnl = (p["entry"] - p["tp"])/p["entry"] * lev * 100
                    trades[-1]["exit"] = float(p["tp"]); trades[-1]["pnl_pct"] = float(pnl); closed=True
            if not closed: new_pos.append(p)
        pos = new_pos
    return pd.DataFrame(trades)

# ========== SIDEBAR ==========
st.sidebar.write("**Data Source**")
symbol = st.sidebar.text_input("Symbol", value="BTCUSDT")
tf = st.sidebar.selectbox("Timeframe", ["5m","15m","1h"], index=0)
use_file = st.sidebar.toggle("Gunakan CSV di data/", value=True, help="Jika OFF, gunakan data sintetis")

# default params per mode
defaults = {
    "scalping": {"tp":2.0,"sl":1.0,"conf":0.75},
    "hybrid": {"tp":3.0,"sl":1.5,"conf":0.75},
    "swing": {"tp":5.0,"sl":2.0,"conf":0.75},
    "adaptif": {"tp":3.0,"sl":1.5,"conf":0.78},
}

# Pick single-mode or compare
mode_tab = st.sidebar.radio("Mode", ["Single","Compare (multi)"], index=0)

def get_df():
    if use_file:
        df0 = load_csv(symbol, tf)
        if df0 is None:
            st.warning(f"CSV data/{symbol}_{tf}.csv tidak ditemukan. Matikan toggle untuk pakai data sintetis.")
            return None
        return indicators(df0)
    else:
        n = 1500 if tf!="1h" else 800
        start_price = 30000 if symbol.upper()=="BTCUSDT" else (2000 if symbol.upper()=="ETHUSDT" else 150)
        rng = np.random.default_rng(123)
        prices = [start_price]; trend = 0.0
        for i in range(1, n+1):
            if i % 200 == 0: trend = rng.normal(0, 0.5)
            vol = 0.001 if (i//150)%2==0 else 0.003
            ret = rng.normal(trend*1e-3, vol)
            prices.append(prices[-1]*(1+ret))
        prices = np.array(prices[1:])
        df0 = pd.DataFrame({"start": pd.date_range(datetime.utcnow()-timedelta(minutes=(5 if tf=='5m' else 15 if tf=='15m' else 60)*n), periods=n, freq=tf),
                            "open": prices})
        drift = rng.normal(0,0.0007,n); close = df0["open"].values*(1+drift)
        high = np.maximum(df0["open"].values, close) * (1 + np.abs(rng.normal(0,0.0009,n)))
        low  = np.minimum(df0["open"].values, close) * (1 - np.abs(rng.normal(0,0.0009,n)))
        volu = rng.integers(100,2000,n)
        df0["high"], df0["low"], df0["close"], df0["volume"] = high, low, close, volu
        return indicators(df0)

df = get_df()
if df is None:
    st.stop()

# ========== SINGLE MODE ==========
if mode_tab == "Single":
    mode = st.sidebar.selectbox("Pilih Mode", list(defaults.keys()), index=0)
    tp = st.sidebar.number_input("TP (%)", min_value=0.2, max_value=15.0, value=defaults[mode]["tp"], step=0.1)
    sl = st.sidebar.number_input("SL (%)", min_value=0.2, max_value=10.0, value=defaults[mode]["sl"], step=0.1)
    lev = st.sidebar.select_slider("Leverage", options=[1,2,3,5,10,20,50,100], value=10)
    conf = st.sidebar.slider("Confidence Threshold", 0.5, 0.95, float(defaults[mode]["conf"]), 0.01)
    trailing = st.sidebar.toggle("Trailing Dinamis", value=True)

    run = st.sidebar.button("▶️ Run Backtest")
    apply = st.sidebar.button("✅ Apply ke Config")

    if run:
        tr = simulate(df, tp, sl, conf_thr=conf, lev=lev, trailing=trailing)
        if tr.empty:
            st.info("Tidak ada trade yang memenuhi threshold.")
        else:
            wr = (tr["pnl_pct"]>0).mean()*100
            avg = tr["pnl_pct"].mean()
            st.subheader(f"Hasil — {symbol} • {tf} • {mode.upper()}")
            c1,c2,c3 = st.columns(3)
            c1.metric("Trades", f"{len(tr)}")
            c2.metric("Winrate", f"{wr:.1f}%")
            c3.metric("Avg PnL / trade", f"{avg:+.2f}%")

            tr_sorted = tr.sort_values("ts")
            eq = (1 + tr_sorted["pnl_pct"]/100).cumprod()
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=tr_sorted["ts"], y=eq, mode="lines", name="Equity"))
            fig.update_layout(height=360, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)

            fig2 = go.Figure()
            fig2.add_trace(go.Histogram(x=tr["pnl_pct"], nbinsx=40, name="PnL %"))
            fig2.update_layout(height=260, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig2, use_container_width=True)

            st.dataframe(tr.tail(200))
            st.download_button("💾 Download Trades CSV", data=tr.to_csv(index=False).encode("utf-8"), file_name=f"sim_{symbol}_{tf}_{mode}.csv", mime="text/csv")

    if apply:
        # Write to config/<mode>.json
        try:
            cfgp = CFG_ROOT / f"{mode}.json"
            cfg = json.loads(cfgp.read_text()) if cfgp.exists() else {}
            cfg["symbol"] = symbol.upper()
            cfg["timeframe"] = tf
            cfg["tp_pct"] = float(tp)
            cfg["sl_pct"] = float(sl)
            cfg["confidence_threshold"] = float(conf)
            cfg["leverage"] = int(lev)
            cfg["trailing"] = bool(trailing)
            cfgp.write_text(json.dumps(cfg, indent=2))
            st.success(f"Config {cfgp.name} diperbarui.")
        except Exception as e:
            st.error(f"Gagal update config: {e}")

# ========== MULTI COMPARE ==========
else:
    st.subheader("Perbandingan Multi-Mode")
    modes_pick = st.multiselect("Pilih Mode", list(defaults.keys()), default=["scalping","hybrid","swing"])
    cols = st.columns(4)
    tp_in = {}; sl_in = {}; cf_in = {}; lv_in = {}; tr_in = {}
    for i, m in enumerate(modes_pick):
        with cols[i % 4]:
            st.caption(m.upper())
            tp_in[m] = st.number_input(f"TP% ({m})", min_value=0.2, max_value=15.0, value=float(defaults[m]["tp"]), step=0.1, key=f"tp_{m}")
            sl_in[m] = st.number_input(f"SL% ({m})", min_value=0.2, max_value=10.0, value=float(defaults[m]["sl"]), step=0.1, key=f"sl_{m}")
            lv_in[m] = st.select_slider(f"Lev ({m})", options=[1,2,3,5,10,20,50,100], value=10, key=f"lev_{m}")
            cf_in[m] = st.slider(f"Conf ({m})", 0.5, 0.95, float(defaults[m]["conf"]), 0.01, key=f"cf_{m}")
            tr_in[m] = st.toggle(f"Trail ({m})", value=True, key=f"trail_{m}")

    runc = st.button("▶️ Run Compare")
    apply_best = st.button("✅ Apply Mode Terbaik → Config")
    res_rows = []

    if runc and modes_pick:
        for m in modes_pick:
            tr = simulate(df, tp_in[m], sl_in[m], conf_thr=cf_in[m], lev=lv_in[m], trailing=tr_in[m])
            if tr.empty:
                res_rows.append({"mode": m, "trades": 0, "winrate": 0.0, "avg_pnl": 0.0})
                continue
            wr = (tr["pnl_pct"]>0).mean()*100
            avg = tr["pnl_pct"].mean()
            res_rows.append({"mode": m, "trades": len(tr), "winrate": wr, "avg_pnl": avg})
        dfres = pd.DataFrame(res_rows).sort_values(["winrate","avg_pnl","trades"], ascending=[False, False, False])
        st.dataframe(dfres.reset_index(drop=True))
        # plot bar
        if len(dfres):
            fig = go.Figure()
            fig.add_trace(go.Bar(x=dfres["mode"], y=dfres["winrate"], name="Winrate %"))
            fig.add_trace(go.Bar(x=dfres["mode"], y=dfres["avg_pnl"], name="Avg PnL %"))
            fig.update_layout(barmode="group", height=360, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)
        st.session_state["_sim_compare_last"] = {"rows": res_rows, "params": {"tp":tp_in, "sl":sl_in, "lev":lv_in, "conf":cf_in, "trail":tr_in}}

    if apply_best:
        last = st.session_state.get("_sim_compare_last")
        if not last or not last.get("rows"):
            st.warning("Jalankan Compare terlebih dahulu.")
        else:
            # pilih terbaik by winrate, lalu avg_pnl, lalu trades
            rows = sorted(last["rows"], key=lambda r: (r["winrate"], r["avg_pnl"], r["trades"]), reverse=True)
            best = rows[0]
            m = best["mode"]
            params = last["params"]
            try:
                cfgp = CFG_ROOT / f"{m}.json"
                cfg = json.loads(cfgp.read_text()) if cfgp.exists() else {}
                cfg["symbol"] = symbol.upper()
                cfg["timeframe"] = tf
                cfg["tp_pct"] = float(params["tp"][m])
                cfg["sl_pct"] = float(params["sl"][m])
                cfg["confidence_threshold"] = float(params["conf"][m])
                cfg["leverage"] = int(params["lev"][m])
                cfg["trailing"] = bool(params["trail"][m])
                cfgp.write_text(json.dumps(cfg, indent=2))
                st.success(f"Mode terbaik: {m.upper()} → {cfgp.name} diperbarui.")
            except Exception as e:
                st.error(f"Gagal update config: {e}")
