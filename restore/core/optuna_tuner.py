# -*- coding: utf-8 -*-
"""
Optimized Optuna tuner for KANG_BOT.

Public API:
    tune_and_train(mode: str, *, n_trials:int=50, timeframe:str|None=None, symbol:str|None=None, testnet:bool|None=None) -> dict

Highlights:
- Deterministic TPE sampler (seed=42) + MedianPruner
- Walk-forward evaluation (train/valid split) on recent klines
- Objective = risk-adjusted return (return * sharpe_like) with penalties for maxDD & overtrading
- Transaction cost modeled via fee_bps
- Safe bounds & relational constraints (ema_fast < ema_slow, rsi_buy < rsi_sell)
- Persist best params to config/{mode}_best.json (merged with existing)

Dependencies:
- Relies on core.data_pipeline.fetch_klines, add_indicators
- Does not place orders; pure backtest scoring
"""
from __future__ import annotations
import os, math, json, time
from typing import Dict, Any, Tuple, List
import numpy as np
import pandas as pd

try:
    import optuna
except Exception as e:
    raise RuntimeError("Optuna not installed. Please `pip install optuna`.") from e

from .logger import get_logger
from .utils import load_json, save_json, now_ts

try:
    from .symbol_scanner import rank_symbols
except Exception:
    def rank_symbols(top_n:int=1, testnet:bool=True): return ["BTCUSDT"]

from .data_pipeline import fetch_klines, add_indicators

log = get_logger("optuna_tuner")

# ------------------------ Helpers ------------------------

def _env_bool(name:str, default:bool) -> bool:
    v = os.getenv(name, str(default)).strip().lower()
    return v in ("1","true","yes","y","on")

def _select_symbol(mode:str, testnet:bool) -> str:
    # Prefer explicit SYMBOL env, else rank_symbols(1)
    sym = os.getenv("SYMBOL") or os.getenv("DEFAULT_SYMBOL")
    if sym: return sym.strip().upper()
    try:
        ranked = rank_symbols(top_n=1, testnet=testnet)
        if ranked: return ranked[0]
    except Exception as e:
        log.warning("rank_symbols failed: %s", e)
    return "BTCUSDT"

def _train_valid_split(df: pd.DataFrame, valid_frac: float = 0.3) -> Tuple[pd.DataFrame, pd.DataFrame]:
    n = len(df)
    cut = max(50, int((1.0 - valid_frac) * n))
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()

def _apply_strategy(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """Generate signals and simulate PnL with TP/SL and simple fee model."""
    ema_f, ema_s = int(params["ema_fast"]), int(params["ema_slow"])
    rsi_p, rsi_b, rsi_s = int(params["rsi_period"]), int(params["rsi_buy"]), int(params["rsi_sell"])
    tp, sl = float(params["tp"]), float(params["sl"])
    fee_bps = float(params.get("fee_bps", 3.0))  # 0.03% each side default
    # price/ohlc columns expected: open, high, low, close, volume, ts
    df = df.copy()
    # Indicators
    df["ema_f"] = df["close"].ewm(span=ema_f, adjust=False).mean()
    df["ema_s"] = df["close"].ewm(span=ema_s, adjust=False).mean()
    # RSI
    delta = df["close"].diff()
    up, down = delta.clip(lower=0), -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1/rsi_p, adjust=False).mean()
    roll_down = down.ewm(alpha=1/rsi_p, adjust=False).mean().replace(0, 1e-9)
    rs = roll_up / roll_down
    df["rsi"] = 100 - (100 / (1 + rs))

    # Entry rule: EMA cross up & RSI > rsi_buy (long-only for safety here)
    df["long_signal"] = (df["ema_f"] > df["ema_s"]) & (df["rsi"] > rsi_b)
    # Exit rule: take-profit/stop-loss or EMA cross down / RSI < rsi_sell
    df["exit_signal"] = (df["ema_f"] < df["ema_s"]) | (df["rsi"] < rsi_s)

    # Simulate sequential trades
    pos_entry = None
    entries, exits, pnl_list = [], [], []
    fee = fee_bps/10000.0
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        price = float(row["close"])
        if pos_entry is None:
            if row["long_signal"] and not prev["long_signal"]:
                pos_entry = price * (1 + fee)  # buy with fee
                entries.append((row.get("ts", i), pos_entry))
        else:
            take = pos_entry * (1 + tp)
            stop = pos_entry * (1 - sl)
            hi, lo = float(row["high"]), float(row["low"])
            exit_price = None
            if lo <= stop:
                exit_price = stop * (1 - fee)
            elif hi >= take:
                exit_price = take * (1 - fee)
            elif row["exit_signal"]:
                exit_price = price * (1 - fee)
            if exit_price is not None:
                pnl = (exit_price - pos_entry)/pos_entry
                exits.append((row.get("ts", i), exit_price))
                pnl_list.append(pnl)
                pos_entry = None

    # Close at last bar if open
    if pos_entry is not None:
        last = float(df.iloc[-1]["close"])*(1 - fee)
        pnl_list.append((last - pos_entry)/pos_entry)

    df.attrs["pnl_list"] = pnl_list
    return df

def _score_pnl(pnls: List[float]) -> Dict[str, float]:
    if not pnls:
        return dict(ret=0.0, trades=0, avg=0.0, std=0.0, sharpe=0.0, mdd=0.0, score=-1e6)
    arr = np.array(pnls, dtype=float)
    ret = float(arr.sum())
    avg = float(arr.mean())
    std = float(arr.std(ddof=1) if len(arr) > 1 else 0.0)
    sharpe_like = (avg / (std + 1e-9)) * math.sqrt(max(1, len(arr))) if std > 0 else avg * 10.0
    # approximate equity curve for DD
    eq = 1.0 + np.cumsum(arr)
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    mdd = float(np.max(dd)) if len(dd) else 0.0
    trades = int(len(arr))
    # Composite score
    score = (ret * (1.0 + sharpe_like)) - (mdd * 2.0) - max(0, trades-100)*0.001
    return dict(ret=ret, trades=trades, avg=avg, std=std, sharpe=sharpe_like, mdd=mdd, score=score)

# ------------------------ Optuna Objective ------------------------

def _objective(trial: "optuna.Trial", mode: str, symbol: str, timeframe: str, testnet: bool) -> float:
    # Search space
    ema_fast = trial.suggest_int("ema_fast", 5, 20)
    ema_slow = trial.suggest_int("ema_slow", max(ema_fast+5, 25), 100)
    rsi_period = trial.suggest_int("rsi_period", 8, 21)
    rsi_buy = trial.suggest_int("rsi_buy", 30, 55)
    rsi_sell = trial.suggest_int("rsi_sell", max(rsi_buy+5, 45), 80)
    tp = trial.suggest_float("tp", 0.008, 0.040)     # 0.8% - 4%
    sl = trial.suggest_float("sl", 0.004, 0.025)     # 0.4% - 2.5%
    fee_bps = trial.suggest_float("fee_bps", 2.0, 8.0)
    params = dict(ema_fast=ema_fast, ema_slow=ema_slow, rsi_period=rsi_period,
                  rsi_buy=rsi_buy, rsi_sell=rsi_sell, tp=tp, sl=sl, fee_bps=fee_bps)

    # Data
    try:
        df = fetch_klines(symbol=symbol, timeframe=timeframe, limit=2000, testnet=testnet)
    except Exception as e:
        raise optuna.TrialPruned(f"Failed to fetch klines: {e}")
    if df is None or len(df) < 300:
        raise optuna.TrialPruned("Not enough data")

    # Indicators and split
    df = add_indicators(df) if hasattr(df, "pipe") else df
    train, valid = _train_valid_split(df, valid_frac=0.3)
    # Train-only warmup
    _ = _apply_strategy(train, params)

    # Valid evaluation
    valid = _apply_strategy(valid, params)
    metrics = _score_pnl(valid.attrs.get("pnl_list", []))

    # Pruning if too poor
    trial.report(metrics["score"], step=len(valid))
    if trial.should_prune():
        raise optuna.TrialPruned("MedianPruner")

    return float(metrics["score"])

# ------------------------ Public API ------------------------

def tune_and_train(mode: str, *, n_trials:int=50, timeframe:str|None=None, symbol:str|None=None, testnet:bool|None=None) -> Dict[str, Any]:
    mode = (mode or "hybrid").strip().lower()
    g = load_json("config/global.json", {})
    st = g.get("settings", {})
    timeframe = timeframe or st.get("timeframe", "15m")
    testnet = bool(testnet) if testnet is not None else _env_bool("BYBIT_TESTNET", True)
    symbol = (symbol or _select_symbol(mode, testnet)).upper()

    log.info("Start tuning mode=%s symbol=%s tf=%s testnet=%s", mode, symbol, timeframe, testnet)

    sampler = optuna.samplers.TPESampler(seed=42)
    pruner = optuna.pruners.MedianPruner(n_warmup_steps=10)
    study = optuna.create_study(direction="maximize", sampler=sampler, pruner=pruner, study_name=f"tune_{mode}_{symbol}_{timeframe}")
    study.optimize(lambda tr: _objective(tr, mode, symbol, timeframe, testnet), n_trials=int(n_trials), n_jobs=1, show_progress_bar=False)

    best = study.best_trial
    params = dict(best.params)

    # Merge & persist
    mode_cfg = load_json(f"config/{mode}.json", {})
    merged = {
        **mode_cfg,
        "tp": float(params.get("tp", mode_cfg.get("tp", 0.02))),
        "sl": float(params.get("sl", mode_cfg.get("sl", 0.01))),
        "confidence_threshold": float(mode_cfg.get("confidence_threshold", 0.80)),
        "min_edge_bps": float(mode_cfg.get("min_edge_bps", 5.0)),
        "indicators": {**mode_cfg.get("indicators", {}),
                       **{k:v for k,v in params.items() if k not in ("tp","sl")}},
        "symbol": symbol,
        "timeframe": timeframe,
        "tuned_at": now_ts(),
    }
    os.makedirs("config", exist_ok=True)
    save_json(f"config/{mode}_best.json", merged)

    log.info("Best score=%.6f params=%s", float(best.value), params)
    return {"mode": mode, "best_score": float(best.value), "best_params": params, "symbol": symbol, "timeframe": timeframe}
