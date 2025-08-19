# Deploy Guide – KANG_BOT (build 7a0df6abee)

## Lokal/VPS (tanpa Docker)
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements_fix_clean_7a0df6abee.txt

cp ../kang_bot_repo_scan/template_7a0df6abee.env .env  # atau isi manual
bash scripts/smoke_test.sh                          # cek struktur
python run.py --mode dry-run --log-level INFO
python run.py --mode live --confirm
```

## Docker Compose
```bash
docker compose build
docker compose up -d
# UI: http://<host>:8501
```

## systemd (opsional)
- Salin repo ke `/opt/kang_bot`
- Buat venv & install deps seperti di atas
- Salin `.env` ke `/opt/kang_bot/.env`
- Salin service file:
```
sudo cp deploy/systemd/kang_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kang_bot
sudo systemctl status kang_bot
```
