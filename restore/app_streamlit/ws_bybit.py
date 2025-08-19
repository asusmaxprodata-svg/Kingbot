
import json, threading, time
from dataclasses import dataclass
from typing import Callable, Optional
from websocket import WebSocketApp

WS_MAIN = "wss://stream.bybit.com/v5/public/linear"
WS_TEST = "wss://stream-testnet.bybit.com/v5/public/linear"

@dataclass
class WSConfig:
    symbol: str
    timeframe: str  # '1','3','5','15','30','60','120','240','360','720','D','W','M'
    testnet: bool = True

class BybitWS:
    def __init__(self, cfg: WSConfig, on_kline: Callable[[dict], None], on_ticker: Optional[Callable[[dict], None]]=None, on_orderbook: Optional[Callable[[dict], None]]=None):
        self.cfg = cfg
        self.on_kline = on_kline
        self.on_ticker = on_ticker
        self.on_orderbook = on_orderbook
        self._app = None
        self._thread = None
        self._stop = False

    def _url(self):
        return WS_TEST if self.cfg.testnet else WS_MAIN

    def _on_open(self, ws):
        # Subscribe to kline + tickers
        topics = [
            f"kline.{self.cfg.timeframe}.{self.cfg.symbol}",
            f"tickers.{self.cfg.symbol}",
            f"orderbook.50.{self.cfg.symbol}"
        ]
        sub = {"op":"subscribe","args":topics}
        ws.send(json.dumps(sub))

    def _on_message(self, ws, msg):
        try:
            j = json.loads(msg)
        except Exception:
            return
        topic = j.get("topic")
        data = j.get("data")
        if not topic or data is None:
            return
        if topic.startswith("kline."):
            # data is a list of dicts or a dict; handle both
            rows = data if isinstance(data, list) else [data]
            for r in rows:
                self.on_kline(r)
        elif topic.startswith("tickers.") and self.on_ticker:
            self.on_ticker(data if isinstance(data, dict) else (data[0] if data else {}))
        elif topic.startswith("orderbook.") and self.on_orderbook:
            self.on_orderbook(data if isinstance(data, dict) else (data[0] if data else {}))

    def _on_error(self, ws, err):
        # Silently ignore; streamlit UI can show last error if needed
        pass

    def _on_close(self, ws, a, b):
        # Try to reconnect unless stop requested
        if not self._stop:
            time.sleep(1.0)
            self.start()

    def start(self):
        self._stop = False
        self._app = WebSocketApp(self._url(), on_open=self._on_open, on_message=self._on_message, on_error=self._on_error, on_close=self._on_close)
        self._thread = threading.Thread(target=self._app.run_forever, kwargs={"ping_interval": 20}, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        try:
            self._app.close()
        except Exception:
            pass
