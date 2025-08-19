#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"/..
python -m core.optuna_tuner scalping
python -m core.optuna_tuner swing
python -m core.optuna_tuner hybrid
python -m core.optuna_tuner adaptive
