from __future__ import annotations
from typing import Any, Dict, List

class BybitAPIManager:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

    def _get_klines_operation(self, symbol: str, interval: str, limit: int = 200) -> List[Dict[str, Any]]:
        raise NotImplementedError("BybitAPIManager._get_klines_operation must be implemented")

    def _place_order_operation(self, symbol: str, side: str, qty: float, price: float | None = None, type_: str = "Market") -> Dict[str, Any]:
        raise NotImplementedError("BybitAPIManager._place_order_operation must be implemented")

    # Safe wrappers: disable live call when not implemented
    def get_klines(self, *args, **kwargs):
        return self._get_klines_operation(*args, **kwargs)

    def place_order(self, *args, **kwargs):
        # Prevent live calls if stub not implemented
        return self._place_order_operation(*args, **kwargs)
