import os, socket, sys, time
import requests

def check_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def check_metrics(url: str, timeout: float = 2.0) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code == 200 and "# HELP" in r.text
    except Exception:
        return False

def check_heartbeat(path: str, max_age_sec: int = 120) -> bool:
    try:
        st = os.stat(path)
        return (time.time() - st.st_mtime) <= max_age_sec
    except Exception:
        return False

def main():
    metrics_port = int(os.environ.get("METRICS_PORT", "9100"))
    hb_path = os.environ.get("HEARTBEAT_PATH", "/app/logs/heartbeat.txt")
    ok_tcp = check_tcp("127.0.0.1", metrics_port, 2.0)
    ok_http = check_metrics(f"http://127.0.0.1:{metrics_port}/metrics", 2.0)
    ok_hb = check_heartbeat(hb_path, 180)
    if ok_tcp and ok_http and ok_hb:
        print("OK")
        sys.exit(0)
    print("FAIL:", {"tcp": ok_tcp, "http": ok_http, "hb": ok_hb})
    sys.exit(1)

if __name__ == "__main__":
    main()
