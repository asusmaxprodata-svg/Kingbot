#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
export PYTHONUNBUFFERED=1
python run.py
