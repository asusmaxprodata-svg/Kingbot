# -*- coding: utf-8 -*-
"""
services/maint.py
Long-running maintenance service using APScheduler.
Schedules weekly job: Mondays 08:00 Asia/Jakarta.
"""
from __future__ import annotations
import os, time, pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import sys
sys.path.append(".")
from core.logger import get_logger
from core.utils import now_ts
from tools.tune_and_select import main as run_maintenance
import subprocess, shlex
from pathlib import Path

log = get_logger("maint_service")


def restart_services():
    """Restart services after maintenance if AUTO_RESTART=true.
    Strategies:
    - If DOCKER is available: `docker compose [ -f files ] restart <services>`
    - Else: run RESTART_CMD if provided
    Env:
      AUTO_RESTART=true|false
      AUTO_RESTART_SERVICES= kang_bot,telegram_bot
      COMPOSE_FILES= docker-compose.yml,docker-compose.maint.yml
      RESTART_CMD= systemctl restart kang_bot.service
    """
    if str(os.getenv("AUTO_RESTART","false")).lower() not in ("1","true","yes","y","on"):
        log.info("AUTO_RESTART disabled")
        return
    services = [s.strip() for s in os.getenv("AUTO_RESTART_SERVICES","kang_bot,telegram_bot").split(",") if s.strip()]
    compose_files = [f.strip() for f in os.getenv("COMPOSE_FILES","docker-compose.yml,docker-compose.maint.yml").split(",") if f.strip()]
    # Try docker compose
    try:
        # Build base command
        cmd = ["docker","compose"]
        for f in compose_files:
            if Path(f).exists():
                cmd += ["-f", f]
        cmd += ["restart"] + services
        log.info("Restarting via docker compose: %s", " ".join(shlex.quote(c) for c in cmd))
        subprocess.run(cmd, check=True)
        log.info("Services restarted via docker compose: %s", ",".join(services))
        return
    except Exception as e:
        log.warning("Docker compose restart failed: %s", e)
    # Fallback to RESTART_CMD
    rc = os.getenv("RESTART_CMD","").strip()
    if rc:
        try:
            log.info("Restarting via RESTART_CMD: %s", rc)
            subprocess.run(shlex.split(rc), check=True)
            log.info("Restart command executed.")
            return
        except Exception as e:
            log.error("RESTART_CMD failed: %s", e)
    log.info("No restart performed.")


def job():
    log.info("Weekly maintenance job started at %s", now_ts())
    try:
        run_maintenance([])  # use defaults
        restart_services()
        log.info("Weekly maintenance job finished.")
    except Exception as e:
        log.exception("Maintenance job failed: %s", e)

def main():
    tz = os.getenv("TZ", "Asia/Jakarta")
    sched = BlockingScheduler(timezone=pytz.timezone(tz))
    # Allow override via CRON env, e.g. "0 8 * * MON"
    cron = os.getenv("AUTO_MAINT_CRON", "0 8 * * MON")
    minute, hour, dom, month, dow = cron.split()
    trigger = CronTrigger(minute=minute, hour=hour, day=dom, month=month, day_of_week=dow)
    sched.add_job(job, trigger, id="weekly_maintenance", replace_existing=True)
    log.info("Maintenance scheduler started with CRON='%s' TZ='%s'", cron, tz)
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Maintenance scheduler stopped.")

if __name__ == "__main__":
    main()
