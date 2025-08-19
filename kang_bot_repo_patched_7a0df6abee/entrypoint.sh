#!/usr/bin/env bash
set -e

# Load .env if exists (docker-compose already injects env_file, but this helps local runs)
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs) || true
fi

echo "[entrypoint] Starting kang_bot…"
exec "$@"
