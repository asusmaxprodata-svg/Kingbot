#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
python streamlit_app/ws_server.py --host 0.0.0.0 --port 8765
