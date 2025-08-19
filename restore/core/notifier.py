import os
import json
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str) -> bool:
    """Send a Telegram message using Bot API.
    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in environment.
    Returns True on success, False otherwise.
    """
    token = TELEGRAM_BOT_TOKEN or os.getenv("BOT_TOKEN")  # fallback
    chat_id = TELEGRAM_CHAT_ID or os.getenv("CHAT_ID")
    if not token or not chat_id:
        # Graceful: don't crash the app, just signal failure
        print("[notifier] Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": str(text)}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return True
        print("[notifier] Telegram API error:", r.status_code, r.text[:200])
        return False
    except Exception as e:
        print("[notifier] Exception:", e)
        return False

def _bot_creds():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")
    return token, chat_id

def telegram_send_direct(text: str) -> bool:
    """Alias helper used across the project to send plain text to Telegram."""
    token, chat_id = _bot_creds()
    if not token or not chat_id:
        print("[notifier] Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": str(text)},
            timeout=10
        )
        ok = r.status_code == 200
        if not ok: print("[notifier] telegram_send_direct error:", r.status_code, r.text[:200])
        return ok
    except Exception as e:
        print("[notifier] telegram_send_direct exception:", e)
        return False

def telegram_send_photo_direct(photo: str, caption: str | None = None) -> bool:
    """Send a photo to Telegram (photo can be a URL or local file path)."""
    token, chat_id = _bot_creds()
    if not token or not chat_id:
        print("[notifier] Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        if os.path.exists(photo):
            with open(photo, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": chat_id}
                if caption: data["caption"] = caption
                r = requests.post(url, data=data, files=files, timeout=20)
        else:
            payload = {"chat_id": chat_id, "photo": photo}
            if caption: payload["caption"] = caption
            r = requests.post(url, json=payload, timeout=20)
        ok = r.status_code == 200
        if not ok: print("[notifier] telegram_send_photo_direct error:", r.status_code, r.text[:200])
        return ok
    except Exception as e:
        print("[notifier] telegram_send_photo_direct exception:", e)
        return False
