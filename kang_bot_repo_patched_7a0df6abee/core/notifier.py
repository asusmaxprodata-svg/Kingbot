import os
import json
import time
import requests
try:
    from core.utils import load_json
except Exception:
    load_json = None

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

def _get_defaults():
    cfg = {}
    try:
        if load_json:
            g = load_json("config/global.json", {}) or {}
            cfg = (g.get("notifier") or g.get("telegram") or {}) if isinstance(g, dict) else {}
    except Exception:
        cfg = {}
    # Defaults
    timeout = int(cfg.get("timeout_sec", 15))
    retries = int(cfg.get("retries", 2))
    backoff_ms = int(cfg.get("backoff_ms", 500))
    return {"timeout": timeout, "retries": retries, "backoff_ms": backoff_ms}

def telegram_send(text: str, parse_mode: str | None = None, disable_web_page_preview: bool | None = None, timeout_sec: int = 15) -> bool:
    """Kirim pesan Telegram dengan opsi format.
    - parse_mode: "Markdown" | "HTML" | None
    - disable_web_page_preview: bool untuk menyembunyikan preview link
    - timeout_sec: timeout request HTTP dalam detik (override default dari config)
    """
    token, chat_id = _bot_creds()
    if not token or not chat_id:
        print("[notifier] Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (or ADMIN_USER_ID)")
        return False
    defaults = _get_defaults()
    effective_timeout = int(timeout_sec or defaults["timeout"]) if timeout_sec is not None else int(defaults["timeout"]) 
    retries = int(defaults["retries"])  # number of retries after the first attempt
    backoff_ms = int(defaults["backoff_ms"]) 
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": str(text)}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if disable_web_page_preview is not None:
        payload["disable_web_page_preview"] = bool(disable_web_page_preview)
    attempts = retries + 1
    for attempt in range(attempts):
        try:
            r = requests.post(url, json=payload, timeout=effective_timeout)
            if r.status_code == 200:
                return True
            # Retry on transient/server errors or rate limit
            if r.status_code in (429,) or 500 <= r.status_code < 600:
                print(f"[notifier] telegram_send transient error (attempt {attempt+1}/{attempts}):", r.status_code, r.text[:200])
            else:
                print("[notifier] telegram_send error:", r.status_code, r.text[:200])
                return False
        except Exception as e:
            print(f"[notifier] telegram_send exception (attempt {attempt+1}/{attempts}):", e)
        # Backoff before next retry if there is another attempt
        if attempt < attempts - 1:
            sleep_s = (backoff_ms / 1000.0) * (2 ** attempt)
            time.sleep(min(sleep_s, 5.0))
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
