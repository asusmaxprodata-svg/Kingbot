from __future__ import annotations
from typing import Any, Dict, List
import time
from pybit.unified_trading import HTTP

class BybitAPIManager:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        # Read-only client; signer only needed for private endpoints
        self._http = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret, recv_window=5000)

    def _get_klines_operation(self, symbol: str, interval: str, limit: int = 200) -> List[Dict[str, Any]]:
        # Basic, read-only implementation using public endpoint
        # category linear for USDT Perp; adjust if needed via cfg
        if limit <= 0:
            limit = 100
        limit = min(limit, 1000)
        # Map common intervals if necessary
        tf_map = {"1m":"1", "3m":"3", "5m":"5", "15m":"15", "30m":"30", "1h":"60", "4h":"240", "1d":"D"}
        tf = tf_map.get(interval, interval)
        retries = 2
        for attempt in range(retries+1):
            try:
                res = self._http.get_kline(category="linear", symbol=symbol, interval=tf, limit=limit)
                if (res or {}).get("retCode") != 0:
                    raise RuntimeError(f"Bybit klines error: {res}")
                rows = (res.get("result") or {}).get("list", [])
                # Return normalized dict list (ts, open, high, low, close, volume)
                out = []
                for r in rows:
                    # Per Bybit v5: [startTime, open, high, low, close, volume, turnover]
                    out.append({
                        "ts": int(r[0]),
                        "open": float(r[1]),
                        "high": float(r[2]),
                        "low": float(r[3]),
                        "close": float(r[4]),
                        "volume": float(r[5]),
                    })
                return list(reversed(out))  # earliest-first
            except Exception as e:
                if attempt >= retries:
                    raise
                time.sleep(0.5 * (2 ** attempt))

    def _place_order_operation(self, symbol: str, side: str, qty: float, price: float | None = None, type_: str = "Market") -> Dict[str, Any]:
        # Safety: block live order by default until explicitly implemented
        raise NotImplementedError("Live order is disabled. Implement explicitly with safety checks.")

    # Safe wrappers: disable live call when not implemented
    def get_klines(self, *args, **kwargs):
        return self._get_klines_operation(*args, **kwargs)

    def place_order(self, *args, **kwargs):
        # Prevent live calls if stub not implemented
        return self._place_order_operation(*args, **kwargs)
