# Optuna Tuner (built-in)
Cara cepat:
1) Upload CSV OHLCV ke folder `data/` (5m untuk scalping, 15m untuk hybrid, 1h untuk swing).
2) Install dep: `pip install optuna xgboost scikit-learn joblib pandas ta`.
3) Jalankan contoh:
   ```
   python tools/tune_xgb_optuna.py --mode scalping --csv data/BTCUSDT_5m.csv --timeframe 5m --trials 200 --confidence_target 0.75
   ```
Output:
- models/xgb_<mode>.joblib
- config/<mode>_best.json
- reports/tuning_<mode>.json
- optuna_studies/<mode>_study.db
