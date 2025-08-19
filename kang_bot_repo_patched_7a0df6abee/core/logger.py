import logging
import json
import os

def _json_formatter(record: logging.LogRecord) -> str:
    obj = {
        "ts": getattr(record, "created", None),
        "level": record.levelname,
        "logger": record.name,
        "msg": record.getMessage(),
    }
    if record.exc_info:
        obj["exc_info"] = logging.Formatter().formatException(record.exc_info)
    return json.dumps(obj, ensure_ascii=False)

class JsonLogHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = _json_formatter(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

_configured = False

def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        log = logging.getLogger()
        log.handlers.clear()
        log.setLevel(getattr(logging, level, logging.INFO))
        if os.getenv("LOG_JSON", "1").lower() in ("1","true","yes","y","on"):
            log.addHandler(JsonLogHandler())
        else:
            fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
            h = logging.StreamHandler()
            h.setFormatter(fmt)
            log.addHandler(h)
        _configured = True
    return logging.getLogger(name)
