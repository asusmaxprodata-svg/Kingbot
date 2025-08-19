import json, time
from websocket import create_connection, WebSocketTimeoutException

def fetch_once(url: str, timeout: float = 1.5):
    try:
        ws = create_connection(url, timeout=timeout)
        msg = ws.recv()
        ws.close()
        return json.loads(msg)
    except Exception:
        return None
