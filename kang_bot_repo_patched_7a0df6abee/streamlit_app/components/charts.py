import pandas as pd
import plotly.graph_objects as go

def equity_curve(df_hist: pd.DataFrame, starting_capital: float):
    if df_hist is None or df_hist.empty:
        fig = go.Figure()
        fig.update_layout(height=260, margin=dict(l=10,r=10,t=40,b=10), title="Equity")
        return fig
    pnl = df_hist['pnl'].fillna(0).astype(float)
    t = pd.to_datetime(df_hist.get('ts', pd.to_datetime(df_hist['ts_epoch'], unit='s')), errors='coerce')
    eq = starting_capital + pnl.cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=eq, mode="lines", name="Equity"))
    fig.update_layout(height=260, margin=dict(l=10,r=10,t=40,b=10), title="Equity Curve")
    return fig

def winrate_bar(stats: dict):
    import plotly.express as px
    if not stats: 
        return go.Figure()
    modes = list(stats.keys())
    wr = [round(stats[m]["winrate"]*100,2) for m in modes]
    df = pd.DataFrame({"mode": modes, "winrate_%": wr})
    fig = px.bar(df, x="mode", y="winrate_%", text="winrate_%")
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(height=260, margin=dict(l=10,r=10,t=40,b=10), title="Winrate per Mode", yaxis_title="%")
    return fig

def pnl_bar(stats: dict):
    import plotly.express as px
    if not stats: 
        return go.Figure()
    modes = list(stats.keys())
    pnls = [round(stats[m]["pnl"],4) for m in modes]
    df = pd.DataFrame({"mode": modes, "PnL": pnls})
    fig = px.bar(df, x="mode", y="PnL", text="PnL")
    fig.update_traces(texttemplate='%{text:.4f}', textposition='outside')
    fig.update_layout(height=260, margin=dict(l=10,r=10,t=40,b=10), title="PnL per Mode", yaxis_title="USDT")
    return fig

def candles_with_trades(df_candles: pd.DataFrame, df_hist: pd.DataFrame, symbol: str):
    fig = go.Figure()
    if df_candles is not None and not df_candles.empty:
        t = pd.to_datetime(df_candles['start'])
        fig.add_trace(go.Candlestick(x=t, open=df_candles['open'], high=df_candles['high'], low=df_candles['low'], close=df_candles['close'], name=symbol))
    # overlay trades
    if df_hist is not None and not df_hist.empty:
        d = df_hist.copy()
        d['ts_dt'] = pd.to_datetime(d.get('ts', pd.to_datetime(d['ts_epoch'], unit='s')), errors='coerce')
        buys = d[d['side'].isin(['BUY','Buy'])]
        sells = d[d['side'].isin(['SELL','Sell'])]
        fig.add_trace(go.Scatter(x=buys['ts_dt'], y=buys.get('price', None), mode='markers', marker_symbol='triangle-up', marker_size=10, name='BUY'))
        fig.add_trace(go.Scatter(x=sells['ts_dt'], y=sells.get('price', None), mode='markers', marker_symbol='triangle-down', marker_size=10, name='SELL'))
    fig.update_layout(height=420, margin=dict(l=10,r=10,t=40,b=10), title=f"{symbol} Candles + Trades")
    return fig
