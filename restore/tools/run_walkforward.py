import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from core.backtest_walkforward import walkforward
from core.utils import load_json
import utils.env_loader  # auto-load .env

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["scalping","swing","hybrid","adaptive"], required=True)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--timeframe", default=None)
    ap.add_argument("--source", choices=["api","csv"], default="api")
    ap.add_argument("--csv", dest="csv_path", default="")
    ap.add_argument("--train", type=int, default=2000)
    ap.add_argument("--test", type=int, default=300)
    ap.add_argument("--step", type=int, default=300)
    ap.add_argument("--horizon", type=int, default=96)
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()

    g = load_json("config/global.json", {})
    symbol = args.symbol or g.get("symbol","BTCUSDT")
    timeframe = args.timeframe or g.get("default_timeframe","15m")
    m = walkforward(
        mode=args.mode, symbol=symbol, timeframe=timeframe, train_bars=args.train, test_bars=args.test,
        step_bars=args.step, horizon_bars=args.horizon, source=args.source, csv_path=args.csv_path, testnet=args.testnet
    )
    print(json.dumps(m, indent=2))

if __name__ == "__main__":
    main()
