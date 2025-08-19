import os, json, numpy as np, pandas as pd, optuna
from typing import Tuple, Dict, Any
from .logger import get_logger
from .data_pipeline import fetch_klines, add_indicators
from .utils import load_json
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
import joblib, datetime

log = get_logger("train_xgb")

def _best_or_base_cfg(mode: str) -> dict:
    best = load_json(f"config/{mode}_best.json", None)
    base = load_json(f"config/{mode}.json", {})
    return (best or base or {}).copy()

def _label_tpsl_aware(df: pd.DataFrame, tp_frac: float, sl_frac: float, horizon: int = 12) -> pd.Series:
    close = df['close'].values
    high = df['high'].values
    low  = df['low'].values
    n = len(df)
    y = np.zeros(n, dtype=int)
    for i in range(n - horizon - 1):
        entry = close[i]
        tp = entry * (1 + tp_frac)
        sl = entry * (1 - sl_frac)
        hit_tp = False
        hit_sl = False
        for j in range(1, horizon+1):
            if high[i+j] >= tp:
                hit_tp = True
                break
            if low[i+j] <= sl:
                hit_sl = True
                break
        y[i] = 1 if (hit_tp and not hit_sl) else 0
    return pd.Series(y, index=df.index)

def _time_decay_weights(n: int, half_life_bars: int = 500) -> np.ndarray:
    ages = np.arange(n, 0, -1) - 1
    hl = max(1, int(half_life_bars))
    w = np.power(0.5, ages / hl)
    return w * (n / w.sum())

def build_dataset(mode: str, symbol: str, timeframe: str, testnet: bool):
    from .data_pipeline import add_indicators
    df = fetch_klines(symbol, timeframe, limit=2400, testnet=testnet)
    cfg = _best_or_base_cfg(mode)
    df = add_indicators(df, mode, cfg)
    tp = float(cfg.get("tp", 0.02))
    sl = float(cfg.get("sl", 0.01))
    horizon = 12 if timeframe in ("5m","15m") else 6
    y = _label_tpsl_aware(df, tp, sl, horizon=horizon)
    valid = y.index[y.index.isin(df.index)]
    X = df.loc[valid].select_dtypes(include="number").copy().replace([np.inf,-np.inf], np.nan).fillna(0.0)
    y = y.loc[valid]
    tail_drop = horizon + 1
    if len(X) > tail_drop:
        X = X.iloc[:-tail_drop, :]
        y = y.iloc[:-tail_drop]
    w = _time_decay_weights(len(y), half_life_bars=600 if timeframe in ("5m","15m") else 300)
    return X, y, w, cfg

def tune_train(mode: str) -> Dict[str, Any]:
    g = load_json("config/global.json", {})
    symbol = g.get("symbol","BTCUSDT")
    timeframe = load_json(f"config/{mode}.json",{}).get("timeframe","15m")
    testnet = os.getenv("BYBIT_TESTNET","true").lower()=="true"
    X, y, w, cfg = build_dataset(mode, symbol, timeframe, testnet)
    tscv = TimeSeriesSplit(n_splits=4)
    def objective(trial: optuna.Trial):
        params = dict(
            max_depth=trial.suggest_int("max_depth", 3, 8),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            min_child_weight=trial.suggest_float("min_child_weight", 1.0, 15.0),
            subsample=trial.suggest_float("subsample", 0.5, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
            n_estimators=trial.suggest_int("n_estimators", 150, 600),
            tree_method="hist",
            objective="binary:logistic",
            eval_metric="auc",
            random_state=42,
            n_jobs=1,
        )
        aucs = []
        for tr_idx, te_idx in tscv.split(X):
            Xtr, Xte = X.iloc[tr_idx], X.iloc[te_idx]
            ytr, yte = y.iloc[tr_idx], y.iloc[te_idx]
            wtr = np.array(w)[tr_idx]
            model = XGBClassifier(**params)
            model.fit(Xtr, ytr, sample_weight=wtr, verbose=False)
            pr = model.predict_proba(Xte)[:,1]
            aucs.append(roc_auc_score(yte, pr))
        return float(np.mean(aucs))
    study = optuna.create_study(direction="maximize", study_name=f"xgb_tscv_{mode}")
    study.optimize(objective, n_trials=40, n_jobs=1, show_progress_bar=False)
    best_params = study.best_trial.params
    base = XGBClassifier(**{**best_params, "tree_method":"hist", "objective":"binary:logistic", "eval_metric":"auc", "random_state":42, "n_jobs":1})
    # Calibrate with Isotonic using TSCV
    calib = CalibratedClassifierCV(base_estimator=base, cv=TimeSeriesSplit(n_splits=4), method="isotonic")
    calib.fit(X, y, sample_weight=w)
    # Save joblib
    out_dir = pathlib.Path(__file__).resolve().parents[1] / "models"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"xgb_{mode}.joblib"
    joblib.dump({"model": calib, "features": list(X.columns), "params": best_params, "ts": datetime.datetime.utcnow().isoformat()+"Z"}, path)
    # Report
    from pathlib import Path
    report = {
        "mode": mode, "symbol": symbol, "timeframe": timeframe,
        "best_params": best_params, "auc_cv": float(study.best_value),
        "timestamp": datetime.datetime.utcnow().isoformat()+"Z"
    }
    (Path(__file__).resolve().parents[1] / "reports" / f"xgb_{mode}_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"mode": mode, "best_params": best_params, "model_path": str(path), "auc_cv": float(study.best_value)}
