import os, json, datetime as dt, requests
from pathlib import Path
import utils.env_loader  # auto-load .env

BASE = Path(__file__).resolve().parents[1]

def tg_send(text: str):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_ADMIN_USER_ID")
    if not tok or not chat: 
        print("[WARN] Missing TELEGRAM env, printing instead:\n"+text)
        return
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat, "text": text, "parse_mode": "Markdown"})
    print("Telegram status:", resp.status_code, resp.text[:120])

def main():
    prof = json.loads((BASE/"data/profit.json").read_text(encoding="utf-8"))
    hist = prof.get("history", [])
    today = dt.datetime.utcnow().date()
    day_trades = [h for h in hist if h.get("closed_at","")[:10] == str(today)]
    pnl = sum(h.get("pnl",0.0) for h in day_trades)
    wins = sum(1 for h in day_trades if h.get("pnl",0)>0)
    total = len(day_trades)
    wr = (wins/max(1,total))*100
    st = json.loads((BASE/"data/state.json").read_text(encoding="utf-8"))
    mode = st.get("mode","hybrid")
    env = "REAL" if not st.get("testnet", True) else "TESTNET"
    sim = "ON" if st.get("simulation_mode", False) else "OFF"
    text = (
        f"*kang_bot — Daily Summary*\n"
        f"Date (UTC): {today}\n"
        f"Env: *{env}* | Sim: *{sim}* | Mode: *{mode}*\n"
        f"Trades: *{total}* | Wins: *{wins}* | Winrate: *{wr:.1f}%*\n"
        f"PnL (sum): *{pnl:+.4f}*\n"
    )
    tg_send(text)

if __name__ == "__main__":
    main()
