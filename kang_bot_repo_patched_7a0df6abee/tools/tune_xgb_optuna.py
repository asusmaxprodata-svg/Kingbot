#!/usr/bin/env python3
import argparse, os, sys, json, time, warnings
from pathlib import Path
from dataclasses import dataclass
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

# TA (fallback jika tidak ada)
try:
    from ta.trend import EMAIndicator, MACD
    from ta.momentum import RSIIndicator
    from ta.volatility import AverageTrueRange
    TA_OK = True
except Exception:
    TA_OK = False

from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier
import joblib
import optuna

def _read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols_l = {c.lower(): c for c in df.columns}
    need = ["open","high","low","close"]
    for n in need:
        if n not in cols_l:
            raise ValueError(f"CSV missing column: {n}")
    # rename start/time column if present
    start = None
    for cand in ["start","time","timestamp","date"]:
        if cand in cols_l: start = cols_l[cand]; break
    if start is None:
        df["start"] = pd.RangeIndex(len(df))
    else:
        df = df.rename(columns={start:"start"})
    # normalize OHLC names to lower
    ren = {}
    for c in df.columns:
        if c.lower() in need+["volume"] and c!=c.lower():
            ren[c] = c.lower()
    if ren: df = df.rename(columns=ren)
    return df

def _ensure_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if TA_OK:
        df["ema_fast"] = EMAIndicator(df["close"], window=10).ema_indicator()
        df["ema_slow"] = EMAIndicator(df["close"], window=30).ema_indicator()
        macd = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd_hist"] = macd.macd_diff()
        df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
        try:
            df["atr"] = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
        except Exception:
            df["atr"] = (df["high"] - df["low"]).rolling(14).mean()
    else:
        df["ema_fast"] = df["close"].ewm(span=10, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=30, adjust=False).mean()
        macd_fast = df["close"].ewm(span=12, adjust=False).mean()
        macd_slow = df["close"].ewm(span=26, adjust=False).mean()
        macd = macd_fast - macd_slow
        df["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
        # RSI approx
        ch = df["close"].diff()
        up = ch.clip(lower=0).rolling(14).mean()
        dn = -ch.clip(upper=0).rolling(14).mean()
        rs = up/(dn+1e-9); df["rsi"] = 100 - (100/(1+rs))
        df["atr"] = (df["high"] - df["low"]).rolling(14).mean()
    df["vol"] = df["close"].pct_change().abs().rolling(20).mean().fillna(0.0005)
    df = df.dropna().reset_index(drop=True)
    return df

def _make_labels(df: pd.DataFrame, horizon=2):
    ret = df["close"].shift(-horizon)/df["close"] - 1.0
    y = (ret>0).astype(int)
    return y[:-horizon], ret[:-horizon]

def _gpt_conf_proxy(row: pd.Series) -> float:
    ema_gap = row["ema_fast"] - row["ema_slow"]
    vol = max(1e-6, float(row.get("vol", 0.001)))
    slope = ema_gap / (abs(row["ema_slow"])+1e-9)
    conf = 0.65 + 0.2*np.tanh( (slope/(0.002+vol)) )
    return float(max(0.60, min(0.90, conf)))

def _simulate_pnl(df: pd.DataFrame, proba: np.ndarray, cfg: dict, conf_target: float):
    tp = float(cfg.get("tp", 0.02))
    sl = float(cfg.get("sl", 0.01))
    fee_rt  = float(cfg.get("fee_rt", 0.0006))
    slip_rt = float(cfg.get("slip_rt", 0.0003))
    pnl = []; wins=0; trades=0; eq=1.0; peak=1.0; dd=0.0
    for i in range(len(df)-1):
        p = float(proba[i]); row = df.iloc[i]
        gptc = _gpt_conf_proxy(row)
        conf = 0.5*(p+gptc)
        bias = "BUY" if p>0.55 else ("SELL" if p<0.45 else None)
        if bias is None or conf < conf_target:
            pnl.append(0.0); peak=max(peak,eq); dd=max(dd, peak-eq); continue
        ret = df["close"].iloc[i+1]/df["close"].iloc[i]-1.0
        r = min(max(ret, -sl), tp) if bias=="BUY" else min(max(-ret, -sl), tp)
        r_net = r - fee_rt - 2*slip_rt
        pnl.append(r_net); trades+=1; wins += (r_net>0)
        eq *= (1.0+r_net); peak=max(peak,eq); dd=max(dd, peak-eq)
    pnl = np.array(pnl, float)
    return {
        "profit": float(np.nansum(pnl)),
        "winrate": float(wins/max(1,trades)),
        "drawdown": float(dd),
        "trades": int(trades)
    }

@dataclass
class TuneConfig:
    mode: str
    timeframe: str
    confidence_target: float
    horizon: int

def build_model(trial):
    return XGBClassifier(
        max_depth=trial.suggest_int("max_depth", 3, 9),
        learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        n_estimators=trial.suggest_int("n_estimators", 300, 1200, step=100),
        subsample=trial.suggest_float("subsample", 0.6, 1.0),
        colsample_bytree=trial.suggest_float("colsample_bytree", 0.6, 1.0),
        reg_lambda=trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
        reg_alpha=trial.suggest_float("reg_alpha", 1e-6, 1.0, log=True),
        min_child_weight=trial.suggest_float("min_child_weight", 1e-3, 10.0, log=True),
        random_state=42, n_jobs=-1, tree_method="hist",
        objective="binary:logistic", eval_metric="logloss"
    )

def objective_factory(df: pd.DataFrame, cfg: TuneConfig, study_cfg: dict):
    feats = _ensure_features(df)
    y, _ = _make_labels(feats, horizon=cfg.horizon)
    feats = feats.iloc[:-cfg.horizon].reset_index(drop=True)
    feature_cols = ["close","ema_fast","ema_slow","macd_hist","rsi","atr","vol"]
    X = feats[feature_cols].values; y = y.values
    tscv = TimeSeriesSplit(n_splits=5)

    def objective(trial):
        tp = trial.suggest_float("tp", 0.006, 0.03)
        sl = trial.suggest_float("sl", 0.003, 0.02)
        pipe = Pipeline([("scaler", StandardScaler()), ("clf", build_model(trial))])

        profits=[]; wrs=[]; dds=[]; trs=[]; aucs=[]
        for tr_idx, va_idx in tscv.split(X):
            X_tr, X_va = X[tr_idx], X[va_idx]
            y_tr, y_va = y[tr_idx], y[va_idx]
            pipe.fit(X_tr, y_tr)
            proba = pipe.predict_proba(X_va)[:,1]
            f_va = feats.iloc[va_idx].reset_index(drop=True).copy()
            sim = _simulate_pnl(f_va, proba, {"tp":tp,"sl":sl}, cfg.confidence_target)
            profits.append(sim["profit"]); wrs.append(sim["winrate"]); dds.append(sim["drawdown"]); trs.append(sim["trades"])
            try: aucs.append(roc_auc_score(y_va, proba))
            except Exception: aucs.append(0.5)

        profit=float(np.mean(profits)); wr=float(np.mean(wrs)); dd=float(np.mean(dds)); tr=float(np.mean(trs)); auc=float(np.mean(aucs))
        penalty = 0.3 if tr < study_cfg.get("min_trades", 30) else 0.0
        score = (profit*100.0) + (wr*10.0) + (auc*5.0) - (dd*2.0) - penalty
        conf_est = 0.5*((np.mean(proba))+0.70)
        if conf_est < cfg.confidence_target:
            score -= (cfg.confidence_target - conf_est)*10.0

        trial.set_user_attr("profit", profit)
        trial.set_user_attr("winrate", wr)
        trial.set_user_attr("drawdown", dd)
        trial.set_user_attr("trades", tr)
        trial.set_user_attr("auc", auc)
        trial.set_user_attr("conf_est", conf_est)
        return score

    return objective, feature_cols

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["scalping","hybrid","swing","adaptive"])
    ap.add_argument("--csv", type=str, required=True, help="OHLCV CSV path")
    ap.add_argument("--timeframe", required=True)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--confidence_target", type=float, default=0.75)
    ap.add_argument("--study_name", type=str, default=None)
    ap.add_argument("--output_dir", type=str, default=".")
    args = ap.parse_args()

    root = Path(args.output_dir).resolve()
    for d in ["models","config","reports","optuna_studies"]:
        (root/d).mkdir(parents=True, exist_ok=True)

    df = _read_csv(Path(args.csv))

    horizon_map = {"scalping":1,"hybrid":2,"swing":3,"adaptive":2}
    cfg = TuneConfig(args.mode, args.timeframe, args.confidence_target, horizon_map.get(args.mode,2))

    storage_path = root/"optuna_studies"/f"{args.mode}_study.db"
    storage = f"sqlite:///{storage_path}"
    study = optuna.create_study(direction="maximize", storage=storage, study_name=args.study_name or f"{args.mode}_{int(time.time())}", load_if_exists=True)

    obj, feat_cols = objective_factory(df, cfg, {"min_trades":30})
    study.optimize(obj, n_trials=args.trials, show_progress_bar=False)

    best = study.best_trial

    # Refit with best params
    feats = _ensure_features(df)
    y, _ = _make_labels(feats, horizon=cfg.horizon)
    feats = feats.iloc[:-cfg.horizon].reset_index(drop=True)
    X = feats[["close","ema_fast","ema_slow","macd_hist","rsi","atr","vol"]].values
    y = y.values
    best_clf = XGBClassifier(
        max_depth=best.params.get("max_depth",5),
        learning_rate=best.params.get("learning_rate",0.05),
        n_estimators=best.params.get("n_estimators",600),
        subsample=best.params.get("subsample",0.8),
        colsample_bytree=best.params.get("colsample_bytree",0.8),
        reg_lambda=best.params.get("reg_lambda",1.0),
        reg_alpha=best.params.get("reg_alpha",0.0),
        min_child_weight=best.params.get("min_child_weight",1.0),
        random_state=42, n_jobs=-1, tree_method="hist",
        objective="binary:logistic", eval_metric="logloss"
    )
    pipe = Pipeline([("scaler", StandardScaler()), ("clf", best_clf)])
    pipe.fit(X, y)

    # Save model & best config
    joblib.dump({"model": pipe, "features": ["close","ema_fast","ema_slow","macd_hist","rsi","atr","vol"]}, root/"models"/f"xgb_{args.mode}.joblib")
    best_cfg = {
        "mode": args.mode,
        "timeframe": args.timeframe,
        "tp": float(best.params.get("tp", 0.02)),
        "sl": float(best.params.get("sl", 0.01)),
        "confidence_threshold": float(args.confidence_target),
        "leverage": "auto",
        "min_edge_bps": 2.0
    }
    (root/"config"/f"{args.mode}_best.json").write_text(json.dumps(best_cfg, indent=2), encoding="utf-8")

    report = {
        "best_value": best.value,
        "best_params": best.params,
        "attrs": {k: best.user_attrs.get(k) for k in ["profit","winrate","drawdown","trades","auc","conf_est"]},
        "study_db": str(storage_path),
        "model_path": str(root/"models"/f"xgb_{args.mode}.joblib"),
        "best_config_path": str(root/"config"/f"{args.mode}_best.json")
    }
    (root/"reports"/f"tuning_{args.mode}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()


# Inject into cfg before backtest
cfg.setdefault("pair_select", {})
cfg["pair_select"]["enable_llm"] = True
cfg["pair_select"]["w_llm"] = float(w_llm)
cfg.setdefault("llm", {})
cfg["llm"]["confirm"] = True
cfg["llm"]["confirm_min_conf"] = float(confirm_min_conf)
