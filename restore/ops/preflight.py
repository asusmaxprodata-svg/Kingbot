import os, sys, re, importlib, socket, pathlib
def log(x): print("[preflight]", x, flush=True)
def warn(x): print("[preflight] WARNING:", x, flush=True)
ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("PYTHONPATH", str(ROOT))
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
# .env
env = ROOT / ".env"
if not env.exists(): warn(".env tidak ditemukan. Copy dari .env.example lalu isi kredensial.")
# quick env key scan
ENV_RE = re.compile(r"os\.environ\[['\"]([A-Z0-9_]+)['\"]\]|os\.getenv\(['\"]([A-Z0-9_]+)['\"]\)")
req=set()
for p in ROOT.rglob("*.py"):
    try:t=p.read_text(encoding="utf-8")
    except:continue
    for m in ENV_RE.finditer(t): req.add(m.group(1) or m.group(2))
missing=[k for k in sorted(req) if not os.getenv(k)]
if missing: warn("ENV belum diisi: "+", ".join(missing))
# port check
port=int(os.getenv("PORT","8501"))
s=socket.socket(); s.settimeout(1.0)
try: s.bind(("0.0.0.0",port)); s.close(); log(f"Port {port} tersedia.")
except Exception as e: print("[preflight] ERROR: Port",port,"tidak bisa dipakai:",e, flush=True)
log("Preflight selesai. Mulai aplikasi...")
