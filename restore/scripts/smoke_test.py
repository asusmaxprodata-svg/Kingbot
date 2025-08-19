"""
Smoke test untuk KANG_BOT (struktur & konfigurasi), tanpa eksekusi order nyata.
- Cek import modul penting
- Cek env vars utama (warning jika kosong)
- Cek entri Streamlit
- Cek modul notifikasi/trading bila ada
"""

import os, sys, json, importlib.util, importlib

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def find_spec(name):
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

def safe_import(name):
    try:
        importlib.import_module(name)
        return True, None
    except Exception as e:
        return False, repr(e)

def main():
    ok = True
    print("=== Smoke Test: START ===")

    # 1) Env check
    env_file = os.path.join(ROOT, "config", "env_required.json")
    if os.path.isfile(env_file):
        required = json.load(open(env_file))["required_env"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            print(f"[WARN] ENV belum terisi: {len(missing)} keys")
            for k in missing[:20]:
                print(" -", k)
        else:
            print("[OK] Semua ENV terisi (berdasarkan template)")
    else:
        print("[INFO] env_required.json tidak ditemukan")

    # 2) Core modules
    for mod in ["run"]:
        present = find_spec(mod)
        print(f"[{'OK' if present else 'MISS'}] Modul {mod}")
        if present:
            ok_imp, err = safe_import(mod)
            print(f"    Import {mod}: {'OK' if ok_imp else 'FAIL'} {'' if ok_imp else err}")
            ok = ok and ok_imp
        else:
            ok = False

    # 3) Streamlit entrypoints
    for mod in ["app_streamlit.Home", "streamlit_app.app"]:
        present = find_spec(mod)
        print(f"[{'OK' if present else 'MISS'}] Streamlit entry {mod}")
        if present:
            ok_imp, err = safe_import(mod)
            print(f"    Import {mod}: {'OK' if ok_imp else 'FAIL'} {'' if ok_imp else err}")
            ok = ok and ok_imp

    # 4) Optional subsystems
    optional_mods = [
        "telegram_bot.bot",
        "components", "st_utils",
        "ws_bybit", "ws_client",
        "ccxt", "binance", "pybit", "okx", "MetaTrader5",
        "openai",
    ]
    for mod in optional_mods:
        present = find_spec(mod)
        print(f"[{'OK' if present else 'MISS'}] Optional {mod}")
        if present:
            ok_imp, err = safe_import(mod)
            print(f"    Import {mod}: {'OK' if ok_imp else 'FAIL'} {'' if ok_imp else err}")

    print("=== Smoke Test: END ===")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
