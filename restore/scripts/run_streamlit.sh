#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
exec streamlit run streamlit_app/app.py --server.port 8501 --server.address 0.0.0.0
