from prometheus_client import start_http_server, Counter, Gauge
import os, time

START_TS = time.time()
HB_COUNTER = Counter('kingbot_heartbeat_total', 'Heartbeat ticks')
UPTIME_GAUGE = Gauge('kingbot_uptime_seconds', 'Uptime in seconds')

def start_metrics_server():
    port = int(os.getenv('METRICS_PORT', '9100'))
    start_http_server(port)

def tick_heartbeat(heartbeat_path: str = None):
    HB_COUNTER.inc()
    UPTIME_GAUGE.set(time.time() - START_TS)
    if heartbeat_path:
        try:
            with open(heartbeat_path, 'w', encoding='utf-8') as fh:
                fh.write(str(int(time.time())))
        except Exception:
            pass
