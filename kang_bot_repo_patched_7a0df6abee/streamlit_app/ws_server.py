import asyncio, json, time, os
from pathlib import Path
import websockets

ROOT = Path(__file__).resolve().parents[1]

def snapshot():
    def j(path, default=None):
        p = ROOT / path
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default if default is not None else {}
    prof = j("data/profit.json", {"starting_capital":30.0,"equity":30.0,"history":[]})
    state = j("data/state.json", {})
    gcfg  = j("config/global.json", {})
    return {
        "ts": time.time(),
        "equity": prof.get("equity"),
        "starting_capital": prof.get("starting_capital", 30.0),
        "history": prof.get("history", [])[-200:],  # last 200
        "state": state,
        "global": gcfg
    }

async def producer(ws, path):
    while True:
        try:
            await ws.send(json.dumps(snapshot()))
        except Exception:
            break
        await asyncio.sleep(2.0)

async def handler(websocket, path):
    await producer(websocket, path)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    print(f"WS server running on ws://{args.host}:{args.port}")
    start_server = websockets.serve(handler, args.host, args.port)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
