import os, socket, sys
port = int(os.environ.get("PORT", "8501"))
s = socket.socket()
s.settimeout(5)
try:
    s.connect(("127.0.0.1", port))
    s.close()
    print("OK")
    sys.exit(0)
except Exception as e:
    print("FAIL:", e)
    sys.exit(1)
