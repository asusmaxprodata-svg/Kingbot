import os
import json
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str) -> bool:
    """Deprecated: use telegram_send(). Kept for backward compatibility."""
    return telegram_send(text)

def _bot_creds():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    chat_id = (
        os.getenv("TELEGRAM_CHAT_ID")
        or os.getenv("CHAT_ID")
        or os.getenv("TELEGRAM_ADMIN_USER_ID")
    )
    return token, chat_id

def telegram_send(text: str, parse_mode: str | None = None, disable_web_page_preview: bool | None = None, timeout_sec: int = 15) -> bool:
    """Kirim pesan Telegram dengan opsi format.
    - parse_mode: "Markdown" | "HTML" | None
    - disable_web_page_preview: bool untuk menyembunyikan preview link
    - timeout_sec: timeout request HTTP dalam detik
    """
    token, chat_id = _bot_creds()
    if not token or not chat_id:
        print("[notifier] Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (or ADMIN_USER_ID)")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": str(text)}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if disable_web_page_preview is not None:
        payload["disable_web_page_preview"] = bool(disable_web_page_preview)
    try:
        r = requests.post(url, json=payload, timeout=timeout_sec)
        ok = r.status_code == 200
        if not ok:
            print("[notifier] telegram_send error:", r.status_code, r.text[:200])
        return ok
    except Exception as e:
        print("[notifier] telegram_send exception:", e)
        return False

def telegram_send_direct(text: str) -> bool:
    """Alias helper plain text."""
    return telegram_send(text)

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
