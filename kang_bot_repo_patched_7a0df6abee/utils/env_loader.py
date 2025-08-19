# utils/env_loader.py
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
except Exception:
    # allow missing dependency; fail softly
    def load_dotenv(*args, **kwargs):
        return False

def load_env():
    base_path = Path(__file__).resolve().parents[1]
    env_path = base_path / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(f"[WARN] .env file not found at {env_path}")

# Load automatically when imported
load_env()
