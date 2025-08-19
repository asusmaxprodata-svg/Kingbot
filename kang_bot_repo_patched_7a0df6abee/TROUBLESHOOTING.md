# Troubleshooting (Kang Bot)
1) **Pemasangan paket gagal (No matching distribution)** → artinya ada modul internal di `requirements.txt`. Sudah dibersihkan pada paket ini.
2) **ModuleNotFoundError untuk modul internal (components/core/utils/dll)** → sudah diatasi dengan `PYTHONPATH=/app` (Dockerfile & compose).
3) **Port bentrok** → ganti `PORT` di `.env` lalu `docker compose up -d --build`.
4) **Unhealthy** → cek `docker logs -n 200 kang_bot` untuk error asli; healthcheck akan auto-restart setelah diperbaiki.
