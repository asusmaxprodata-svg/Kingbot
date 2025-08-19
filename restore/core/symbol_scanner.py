# -*- coding: utf-8 -*-
"""
Optimized symbol scanner with quantitative scoring + optional LLM re-ranking.

Public API:
    rank_symbols(top_n:int=3, testnet:bool=True) -> list[str]

Scoring (quant):
- Liquidity: 24h turnover (volume * price) relative
- Volatility: |24h % change| (proxy) + ATR if available
- Marketability: spread_bps inverse (if available)
- Optional funding rate penalty (if available)
Final score = w_liq*liq + w_vol*vol + w_mkt*market - w_fund*fund_penalty

Options via config/global.json:
pair_select: { "w_liq":0.35,"w_vol":0.35,"w_mkt":0.20,"w_fund":0.10, "enable_llm":false, "w_quant":0.75,"w_llm":0.25 }
"""
from __future__ import annotations
import os, math
from typing import List, Dict, Any, Tuple

from .logger import get_logger
log = get_logger("symbol_scanner")

def _cfg() -> Dict[str, Any]:
    try:
        from .config_manager import load_config
        cfg = load_config() or {}
        return cfg
    except Exception:
        return {}

def _bybit_tickers(testnet: bool) -> list[dict]:
    from pybit.unified_trading import HTTP
    http = HTTP(testnet=bool(testnet),
                api_key=os.getenv("BYBIT_API_KEY"),
                api_secret=os.getenv("BYBIT_API_SECRET"))
    res = http.get_tickers(category="linear") or {}
    return ((res.get("result") or {}).get("list") or [])

def _normalize(rows: List[Tuple[str, float]]) -> Dict[str, float]:
    # rows: [(symbol, value)]
    vals = [v for _, v in rows]
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 0.0)
    span = (hi - lo) or 1.0
    return {s: (v - lo)/span for s, v in rows}

def _quant_score(rows: list[dict], weights: Dict[str, float]) -> List[Tuple[float, str]]:
    liq_rows, vol_rows, mkt_rows, fund_rows = [], [], [], []
    for r in rows:
        sym = r.get("symbol","")
        if not sym.endswith("USDT"): 
            continue
        try:
            lastp = float(r.get("lastPrice", "0") or 0)
            vol24 = float(r.get("turnover24h", "0") or 0)  # already in quote currency for Bybit
            chg = abs(float(r.get("price24hPcnt", "0") or 0))   # percent
            spread = abs(float(r.get("ask1Price", "0") or 0) - float(r.get("bid1Price", "0") or 0))
            spread_bps = (spread / (lastp+1e-9)) * 10000.0 if lastp > 0 else 10000.0
            funding = abs(float(r.get("fundingRate", "0") or 0))
        except Exception:
            continue
        liq_rows.append((sym, vol24))
        vol_rows.append((sym, chg))
        mkt_rows.append((sym, -spread_bps))  # negative spread => higher is better
        fund_rows.append((sym, funding))

    if not liq_rows:
        return []

    nl, nv, nm, nf = (_normalize(liq_rows), _normalize(vol_rows), _normalize(mkt_rows), _normalize(fund_rows))
    w_liq = float(weights.get("w_liq", 0.35))
    w_vol = float(weights.get("w_vol", 0.35))
    w_mkt = float(weights.get("w_mkt", 0.20))
    w_fund = float(weights.get("w_fund", 0.10))

    scored = []
    for sym, _ in liq_rows:
        score = (w_liq*nl.get(sym,0.0) + w_vol*nv.get(sym,0.0) + w_mkt*nm.get(sym,0.0) - w_fund*nf.get(sym,0.0))
        scored.append((float(score), sym))
    scored.sort(reverse=True)
    return scored

def _llm_rerank(scored: List[Tuple[float,str]], rows: list[dict], weights: Dict[str, float]) -> List[Tuple[float,str]]:
    enable = bool(weights.get("enable_llm", False))
    if not enable:
        return scored
    try:
        from core.ai_signal import llm_pair_score
    except Exception as e:
        log.warning("LLM rerank unavailable: %s", e)
        return scored
    wq = float(weights.get("w_quant", 0.75))
    wl = float(weights.get("w_llm", 0.25))
    top_syms = [s for _, s in scored[:min(len(scored), 20)]]
    merged = []
    for sym in top_syms:
        rec = next((r for r in rows if r.get("symbol")==sym), {})
        snap = {
            "ret24h": abs(float(rec.get("price24hPcnt", 0.0)))/100.0,
            "atr": 0.0, "eff": 0.0,
            "spread_bps": 0.0,
            "funding": float(rec.get("fundingRate", 0.0))
        }
        try:
            l = float(llm_pair_score(sym, snap))
        except Exception as e:
            l = 0.0
        q = next((q for q, s in scored if s==sym), 0.0)
        merged.append((wq*q + wl*l, sym))
    merged.sort(reverse=True)
    return merged

def rank_symbols(top_n:int=3, testnet:bool=True) -> list[str]:
    top_n = max(1, int(top_n or 3))
    # Config weights
    weights = (_cfg().get("pair_select") or {})
    # Try live Bybit
    rows = []
    try:
        rows = _bybit_tickers(testnet)
    except Exception as e:
        log.warning("Bybit tickers failed: %s", e)
    scored = _quant_score(rows, weights) if rows else []
    if not scored:
        # Fallback: from env or defaults
        syms = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
        out = [s.strip().upper() for s in syms if s.strip()]
        return out[:top_n]
    # Optional LLM rerank
    scored = _llm_rerank(scored, rows, weights)
    return [s for _, s in scored[:top_n]]
