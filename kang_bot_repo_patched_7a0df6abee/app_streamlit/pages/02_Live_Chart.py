
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from time import sleep
import plotly.graph_objects as go
from st_utils import global_cfg, DATA_ROOT
from ws_bybit import BybitWS, WSConfig

st.set_page_config(page_title="Live Chart", layout="wide")
st.markdown('<style>'+open("app_streamlit/styles.css").read()+'</style>', unsafe_allow_html=True)
st.title("📈 Live Chart — Candlestick + EMA/MACD/RSI")

g = global_cfg()
watch = g.get("symbols", ["BTCUSDT","ETHUSDT","SOLUSDT"])

c1, c2, c3 = st.columns([1,1,1])
with c1:
    symbols = st.multiselect("Symbols (maks 4)", options=watch, default=[watch[0]], max_selections=4)
if not symbols:
    symbols = [watch[0]]
# pick primary symbol for controls below
symbol = symbols[0]
with c2:
    tf_opt = {"5m":"5","15m":"15","1h":"60","4h":"240"}
    tf_label = st.selectbox("Timeframe", options=list(tf_opt.keys()), index=0)
    interval = tf_opt[tf_label]
with c3:
    testnet = st.toggle("Testnet", value=g.get("testnet", True))

row_a = st.columns([1,1])
with row_a[0]:
    use_ws = st.toggle("Live via WebSocket", value=True)
with row_a[1]:
    persist_csv = st.toggle("Simpan update ke CSV", value=False)


# Shared state for tickers
if 'depth_bids' not in st.session_state: st.session_state.depth_bids = {}
if 'depth_asks' not in st.session_state: st.session_state.depth_asks = {}
if 'tickers' not in st.session_state: st.session_state.tickers = {}

csv = DATA_ROOT / f"{symbol}_{tf_label}.csv"

# Load initial data
if csv.exists():
    df0 = pd.read_csv(csv)
else:
    df0 = pd.DataFrame(columns=["start","open","high","low","close","volume"])

def compute_indicators(df: pd.DataFrame):
    if not len(df):
        df["ema10"]=[]; df["ema30"]=[]; df["macd"]=[]; df["macd_sig"]=[]; df["macd_hist"]=[]; df["rsi"]=[]
        return df
    d = df.copy().sort_values("start")
    d["ema10"] = d["close"].ewm(span=10, adjust=False).mean()
    d["ema30"] = d["close"].ewm(span=30, adjust=False).mean()
    ema12 = d["close"].ewm(span=12, adjust=False).mean()
    ema26 = d["close"].ewm(span=26, adjust=False).mean()
    d["macd"] = ema12 - ema26
    d["macd_sig"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_sig"]
    # RSI
    delta = d["close"].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -delta.clip(upper=0).rolling(14).mean()
    rs = up/(down+1e-9)
    d["rsi"] = 100 - (100/(1+rs))
    return d


def overlay_markers(fig, dfp: pd.DataFrame, sym: str):
    import json
    p = Path("reports/live_signals.json")
    if not p.exists(): return
    try:
        sig = json.loads(p.read_text())  # expected: list of {symbol, ts, action}
        # filter recent entries for this symbol
        ss = [s for s in sig if s.get("symbol")==sym]
        xs_buy, ys_buy, xs_sell, ys_sell = [], [], [], []
        if len(ss):
            # map ts to nearest candle
            for s in ss:
                ts = int(s.get("ts", 0))
                action = s.get("action","SKIP").upper()
                # find nearest start
                idx = dfp["start"].sub(ts).abs().idxmin() if len(dfp) else None
                if idx is not None and idx in dfp.index:
                    x = dfp.loc[idx, "start"]
                    price = dfp.loc[idx, "close"]
                    if action == "BUY":
                        xs_buy.append(x); ys_buy.append(price)
                    elif action == "SELL":
                        xs_sell.append(x); ys_sell.append(price)
        if xs_buy:
            fig.add_trace(go.Scatter(x=xs_buy, y=ys_buy, mode="markers", name="BUY", marker_symbol="triangle-up", marker_size=10))
        if xs_sell:
            fig.add_trace(go.Scatter(x=xs_sell, y=ys_sell, mode="markers", name="SELL", marker_symbol="triangle-down", marker_size=10))
    except Exception:
        return

def render_plot(df_plot: pd.DataFrame, sym: str=None):
    if not len(df_plot):
        st.info("Belum ada data. Jalankan fetcher atau tunggu live update.")
        return
    d = compute_indicators(df_plot)
    d = d.tail(400)  # limit for speed
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=d["start"], open=d["open"], high=d["high"], low=d["low"], close=d["close"], name="OHLC"))
    fig.add_trace(go.Scatter(x=d["start"], y=d["ema10"], name="EMA10", mode="lines"))
    fig.add_trace(go.Scatter(x=d["start"], y=d["ema30"], name="EMA30", mode="lines"))
    fig.update_layout(height=460, margin=dict(l=20,r=20,t=30,b=20), xaxis_rangeslider_visible=False)
    overlay_markers(fig, d, sym or symbol)
    st.plotly_chart(fig, use_container_width=True)

    c_macd, c_rsi = st.columns(2)
    with c_macd:
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=d["start"], y=d["macd_hist"], name="MACD Hist"))
        fig2.add_trace(go.Scatter(x=d["start"], y=d["macd"], name="MACD", mode="lines"))
        fig2.add_trace(go.Scatter(x=d["start"], y=d["macd_sig"], name="Signal", mode="lines"))
        fig2.update_layout(height=240, margin=dict(l=10,r=10,t=20,b=10))
        st.plotly_chart(fig2, use_container_width=True)
    with c_rsi:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=d["start"], y=d["rsi"], name="RSI", mode="lines"))
        fig3.add_hrect(y0=30, y1=70, line_width=0, fillcolor="lightgray", opacity=0.15)
        fig3.update_layout(height=240, margin=dict(l=10,r=10,t=20,b=10), yaxis=dict(range=[0,100]))
        st.plotly_chart(fig3, use_container_width=True)

placeholder = st.empty()


def start_ws_for(sym):
    # Orderbook handler
    def on_ob(msg: dict):
        try:
            # Bybit v5 orderbook provides 'b' (bids), 'a' (asks) arrays of [price, size]
            bids = msg.get('b', [])
            asks = msg.get('a', [])
            # convert to float and aggregate
            b = [(float(p), float(s)) for p,s in bids if float(s)>0]
            a = [(float(p), float(s)) for p,s in asks if float(s)>0]
            st.session_state.depth_bids[sym] = b
            st.session_state.depth_asks[sym] = a
        except Exception:
            pass

    def on_k(msg: dict):
        try:
            start = int(msg.get("start", msg.get("t", 0)))
            row = {
                "start": start,
                "open": float(msg.get("open", msg.get("o", np.nan))),
                "high": float(msg.get("high", msg.get("h", np.nan))),
                "low": float(msg.get("low", msg.get("l", np.nan))),
                "close": float(msg.get("close", msg.get("c", np.nan))),
                "volume": float(msg.get("volume", msg.get("v", 0.0)))
            }
            key = f"{sym}_{interval}"
            if key not in st.session_state: st.session_state[key] = pd.DataFrame(columns=["start","open","high","low","close","volume"])
            buf = st.session_state[key]
            if len(buf) and start in set(buf["start"]):
                idx = buf.index[buf["start"]==start]
                if len(idx): 
                    for k,v in row.items(): buf.loc[idx, k] = v
            else:
                st.session_state[key] = pd.concat([buf, pd.DataFrame([row])], ignore_index=True)
        except Exception:
            pass

    def on_tk(msg: dict):
        try:
            bid = float(msg.get("bid1Price") or msg.get("bidPrice", 0) or 0)
            ask = float(msg.get("ask1Price") or msg.get("askPrice", 0) or 0)
            last = float(msg.get("lastPrice") or 0)
            if bid>0 and ask>0:
                spread = (ask - bid) / ((ask + bid)/2 + 1e-9) * 1e4  # bps
            else:
                spread = 0.0
            st.session_state.tickers[sym] = {"bid": bid, "ask": ask, "last": last, "spread_bps": spread}
        except Exception:
            pass

    key_ws = f"ws_{sym}_{interval}"
    # Stop previous if exists
    if key_ws in st.session_state and st.session_state[key_ws] is not None:
        st.session_state[key_ws].stop()
        st.session_state[key_ws] = None
    w = BybitWS(WSConfig(symbol=sym, timeframe=interval, testnet=testnet), on_kline=on_k, on_ticker=on_tk, on_orderbook=on_ob)
    st.session_state[key_ws] = w
    w.start()

# Initial render
placeholder.empty()
with placeholder.container():
    render_plot(df0)

if use_ws:
    # Manage WS per session
    if "ws_obj" not in st.session_state:
        st.session_state.ws_obj = None
    if "live_buf" not in st.session_state:
        st.session_state.live_buf = df0.copy()

    def on_kline(msg: dict):
        try:
            start = int(msg.get("start", msg.get("t", 0)))
            row = {
                "start": start,
                "open": float(msg.get("open", msg.get("o", np.nan))),
                "high": float(msg.get("high", msg.get("h", np.nan))),
                "low": float(msg.get("low", msg.get("l", np.nan))),
                "close": float(msg.get("close", msg.get("c", np.nan))),
                "volume": float(msg.get("volume", msg.get("v", 0.0)))
            }
            buf = st.session_state.live_buf
            if "start" in buf and start in set(buf["start"]):
                idx = buf.index[buf["start"] == start]
                if len(idx):
                    for k,v in row.items():
                        buf.loc[idx, k] = v
            else:
                st.session_state.live_buf = pd.concat([buf, pd.DataFrame([row])], ignore_index=True)
        except Exception:
            pass

    # restart ws if different symbol/tf
    if st.session_state.ws_obj is not None:
        st.session_state.ws_obj.stop()
        st.session_state.ws_obj = None

    ws = BybitWS(WSConfig(symbol=symbol, timeframe=interval, testnet=testnet), on_kline=on_kline)
    st.session_state.ws_obj = ws
    ws.start()

    # live loop ~10 minutes (2s refresh)
    for _ in range(300):
        
        # Start WS for selected symbols
        if use_ws:
            for s in symbols:
                start_ws_for(s)
        
        # Render grid charts
        cols_per_row = 2 if len(symbols)>1 else 1
        rows = (len(symbols)+cols_per_row-1)//cols_per_row
        idx = 0
        for r in range(rows):
            cols = st.columns(cols_per_row)
            for c in range(cols_per_row):
                if idx >= len(symbols): break
                s = symbols[idx]
                key = f"{s}_{interval}"
                df_buf = st.session_state.get(key, df0.copy())
                with cols[c]:
                    st.markdown(f"### {s}")
                    render_plot(df_buf, sym=s)
                    # Ticker & Spread small KPIs
                    tk = st.session_state.tickers.get(s, {})
                    bid, ask, last, spread = tk.get("bid",0.0), tk.get("ask",0.0), tk.get("last",0.0), tk.get("spread_bps",0.0)
                    colk1, colk2, colk3 = st.columns(3)
                    colk1.metric("Last", f"{last:.4f}")
                    colk2.metric("Bid/Ask", f"{bid:.4f} / {ask:.4f}")
                    colk3.metric("Spread (bps)", f"{spread:.2f}")
                idx += 1
        buf = st.session_state.live_buf.copy().sort_values("start")
        with placeholder.container():
            render_plot(buf)
        if persist_csv and len(buf):
            try:
                buf.to_csv(csv, index=False)
            except Exception:
                pass
        sleep(2.0)
    st.info("Live session selesai. Tekan Rerun untuk lanjut.")
else:
    st.caption("WS dimatikan. Menampilkan data dari CSV (jika ada).")
