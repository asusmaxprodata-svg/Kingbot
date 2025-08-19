# Docker Deployment for kang_bot

This setup provides two services:
- **bot**: the trading engine with Telegram/WA notifications, scheduler, and auto-tune.
- **ui**: Streamlit dashboard (modern UI, live charts, sockets, filters).

## Quick Start
```bash
# 1) Put these files at the root of the project (same folder as run.py)
# 2) Create .env from example
cp .env.example .env && nano .env

# 3) Build & run
docker compose up -d --build

# 4) Logs
docker compose logs -f bot
docker compose logs -f ui
```

## Volumes
- `config/`, `data/`, `logs/`, `reports/`, `models/` are mounted to persist state and configs between rebuilds.

## Env Notes
- `BYBIT_ENV`: `testnet` or `real`.
- Telegram/Twilio keys are required if you want notifications.
- `TZ` defaults to `Asia/Jakarta` for both containers.

## Healthchecks
- bot: imports `core.ai_signal` to confirm app is ready.
- ui: checks presence of Streamlit entry.

## Common Issues
- **Missing requirements**: ensure `requirements.txt` includes `APScheduler`, `python-telegram-bot`, `twilio`, `xgboost`, `optuna`, `pybit`, `pandas`, `ta`, `openai`, etc.
- **Permissions**: volumes are created on host; ensure they are writable by Docker user.
- **Port conflict**: change `STREAMLIT_SERVER_PORT` in `.env`.

## Stop & Remove
```bash
docker compose down
```

## Update
```bash
git pull  # or unzip new sources
docker compose up -d --build
```
