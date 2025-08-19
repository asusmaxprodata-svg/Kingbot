#!/usr/bin/env bash
set -euo pipefail
python -m compileall .
python scripts/smoke_test.py
