import os, pandas as pd, numpy as np
from typing import Literal
from pybit.unified_trading import HTTP
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from .logger import get_logger

log = get_logger("data_pipeline")

def _http_client(testnet: bool):
    return HTTP(
        testnet=testnet,
        api_key=os.getenv("BYBIT_API_KEY"),
        api_secret=os.getenv("BYBIT_API_SECRET")
    )

def fetch_klines(symbol: str, interval: str, limit: int = 300, testnet: bool = True) -> pd.DataFrame:
    http = _http_client(testnet)
    # Bybit expects intervals like "5" "15" "60" minutes for linear perp
    mapping = {"5m": "5", "15m": "15", "60m": "60", "1h":"60"}
    iv = mapping.get(interval, interval)
    res = http.get_kline(category="linear", symbol=symbol, interval=iv, limit=limit)
    k = res.get("result", {}).get("list", [])
    if not k:
        log.warning("Empty klines from Bybit; returning dummy")
        return pd.DataFrame()
    cols = ["start","open","high","low","close","volume","turnover"]
    df = pd.DataFrame(k, columns=cols)
    for c in ["open","high","low","close","volume","turnover"]:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df["start"] = pd.to_datetime(df["start"].astype(np.int64), unit="ms", utc=True)
    df = df.sort_values("start").reset_index(drop=True)
    return df

def add_indicators(df: pd.DataFrame, mode: str, cfg: dict) -> pd.DataFrame:
    if df.empty:
        return df
    close = df["close"]
    high = df["high"]; low = df["low"]
    if mode in ("scalping","hybrid","swing"):
        ema_fast = EMAIndicator(close=close, window=cfg.get("indicators",{}).get("ema_fast", 9)) if cfg.get("indicators",{}).get("ema_fast") else None
        ema_slow_w = cfg.get("indicators",{}).get("ema_slow", None) or cfg.get("indicators",{}).get("ema", None) or 50
        ema_slow = EMAIndicator(close=close, window=ema_slow_w)
        df["ema_fast"] = ema_fast.ema_indicator() if ema_fast else np.nan
        df["ema_slow"] = ema_slow.ema_indicator()
        rsi_w = cfg.get("indicators",{}).get("rsi", 14)
        df["rsi"] = RSIIndicator(close=close, window=rsi_w).rsi()
        if mode in ("swing","hybrid"):
            fast = cfg.get("indicators",{}).get("macd_fast", 12)
            slow = cfg.get("indicators",{}).get("macd_slow", 26)
            sig = cfg.get("indicators",{}).get("macd_signal", 9)
            macd = MACD(close=close, window_slow=slow, window_fast=fast, window_sign=sig)
            df["macd"] = macd.macd()
            df["macd_signal"] = macd.macd_signal()
            df["macd_hist"] = macd.macd_diff()
    # ATR (normalized)
    atr_w = int(cfg.get('indicators', {}).get('atr', 14))
    atr = AverageTrueRange(high=high, low=low, close=close, window=atr_w)
    df['atr'] = atr.average_true_range()
    df['atr_frac'] = df['atr'] / close

    # basic volatility features
    df["ret"] = close.pct_change()
    df["vol"] = df["ret"].rolling(20).std()
    df["mom"] = close.pct_change(10)
    df.dropna(inplace=True)
    return df


def add_mtf_features(df: pd.DataFrame, symbol: str, cfg: dict, testnet: bool):
    mtf = cfg.get("mtf", {})
    tf = mtf.get("confirm_tf")
    if not tf:
        return df
    try:
        from .logger import get_logger
        log = get_logger("data_pipeline")
        d2 = fetch_klines(symbol=symbol, interval=tf, limit=300, testnet=testnet)
        if d2.empty:
            return df
        d2 = add_indicators(d2, "swing", {"indicators":{"ema":50,"rsi":14,"macd_fast":12,"macd_slow":26,"macd_signal":9}})
        # forward-fill to align last higher-TF snapshot onto low-TF timeline
        snap = d2.iloc[-1:][["ema_slow","rsi","macd_hist"]].rename(columns={
            "ema_slow":"ema_slow_HTF","rsi":"rsi_HTF","macd_hist":"macd_hist_HTF"
        })
        for k,v in snap.iloc[0].items():
            df[k] = float(v)
    except Exception:
        pass
    return df
