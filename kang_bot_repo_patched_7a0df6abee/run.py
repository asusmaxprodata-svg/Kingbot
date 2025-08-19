import os, sys, subprocess
from dotenv import load_dotenv
import sys
import pathlib

load_dotenv()

# Ensure project root on sys.path
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("TZ", "Asia/Jakarta")

ENTRY = 'streamlit_app/app.py'
PORT = os.environ.get("PORT", "8501")
ADDR = os.environ.get("HOST", "0.0.0.0")

def die(msg, code=1):
    sys.stderr.write(msg + "\n")
    sys.exit(code)

def run_streamlit(entry):
    if not entry or not os.path.exists(entry):
        die("Streamlit entry not found: " + str(entry))
    cmd = ["streamlit", "run", entry, "--server.port", str(PORT), "--server.address", ADDR]
    print("[run.py] Launching Streamlit:", " ".join(cmd))
    os.execvp(cmd[0], cmd)

def run_python(entry):
    if not entry or not os.path.exists(entry):
        die("Python entry not found: " + str(entry))
    print("[run.py] Launching Python:", entry)
    with open(entry, "rb") as f:
        code = compile(f.read(), entry, "exec")
    glb = {"__name__": "__main__", "__file__": entry}
    exec(code, glb)

if __name__ == "__main__":
    print(f"[run.py] ENTRY={ENTRY} PORT={PORT} ADDR={ADDR}")
    # Heuristic: treat as Streamlit if filename or contents suggest so
    streamlit_hint = False
    if ENTRY:
        if "streamlit" in ENTRY.lower():
            streamlit_hint = True
        else:
            try:
                with open(ENTRY, "r", encoding="utf-8") as fh:
                    src = fh.read(2048)
                if "import streamlit" in src or "from streamlit" in src:
                    streamlit_hint = True
            except Exception:
                pass
    if streamlit_hint:
        run_streamlit(ENTRY)
    else:
        run_python(ENTRY)
