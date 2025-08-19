import sys
from .optuna_tuner import tune_and_train
modes = ["scalping","swing","hybrid","adaptive"]
def main():
    results = {}
    for m in modes:
        print(f"=== Retrain {m} ===")
        results[m] = tune_and_train(m)
        print(results[m])
    return results
if __name__ == "__main__":
    main()
