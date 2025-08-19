#!/usr/bin/env bash
# Simple watchdog: restart container if unhealthy
set -euo pipefail
SERVICE=${1:-kang_bot}
STATUS=$(docker inspect --format='{{json .State.Health.Status}}' "$SERVICE" 2>/dev/null || echo '"unknown"')
echo "[watchdog] $SERVICE health: $STATUS"
if [[ "$STATUS" != ""healthy"" ]]; then
  echo "[watchdog] restarting $SERVICE..."
  docker restart "$SERVICE" || true
fi
