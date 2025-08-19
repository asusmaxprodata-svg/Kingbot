# kang_bot — AI Trading Bot for Bybit Futures (Testnet & Real)

> Auto 24/7 • GPT‑4o + XGBoost • Optuna daily tuning • Telegram control • WhatsApp fallback

**Created:** 2025-08-09 18:36:33 UTC

## Highlights
- Modes: **Scalping (5m)**, **Swing (1h)**, **Hybrid (15m)**, **Adaptive (auto-pick)**
- Decision engine: GPT‑4o reads context (trend/vol/volume/momentum) → XGBoost classifies signal
- Safety: TP/SL defaults (2%/1%), AI dynamic trailing, max 3 open positions, daily max loss 10% → auto-pause
- Capital: start **$30**, compounding via `data/profit.json`
- Control: Telegram inline keyboard (mode, leverage 5/10/20/50/100/Auto, testnet/real), PIN required for **real**
- Reporting: Daily WhatsApp report via Twilio; fallback if Telegram fails
- Tuning: **Optuna** per mode → saves `config/<mode>_best.json`

## Quick start
1) Python 3.10+ recommended
2) `python -m venv .venv && source .venv/bin/activate` (Linux/Mac) or `.venv\Scripts\activate` (Windows)
3) `pip install -r requirements.txt`
4) Copy `.env.example` → `.env` and fill your keys
5) Default is **TESTNET + DRY_RUN**, safe to run:
   ```bash
   python run.py
   ```
6) Start Telegram bot: message your bot `/start` and use the buttons.
7) (Optional) Daily tuning (cron): see `cron/crontab.txt`

## Environment (.env)
See `.env.example` for all vars. **Never commit real keys.**

## Disclaimer
This is a reference implementation. Use **testnet first**. Markets carry risk.


## New in this build
- **Telegram menus** now show Saldo, Statistik, dan Riwayat (10 terakhir)
- **Auto-pick Top N pairs** by volume+volatility, configurable in `config/global.json` (`auto_pairs`, `symbols`, `top_n`)
- **XGBoost trainer with Optuna** (`core/train_xgb.py`) — trains and saves `models/xgb_<mode>.json`
- **Combined tuning+training**: `python -m core.optuna_tuner <mode>` now also trains XGB and saves the model

### Daily automation (cron)
Add to crontab to tune + train:
```
15 1 * * * /usr/bin/env bash -lc 'cd ~/kang_bot && . .venv/bin/activate && python -m core.optuna_tuner scalping >> logs/tune.log 2>&1'
25 1 * * * /usr/bin/env bash -lc 'cd ~/kang_bot && . .venv/bin/activate && python -m core.optuna_tuner swing >> logs/tune.log 2>&1'
35 1 * * * /usr/bin/env bash -lc 'cd ~/kang_bot && . .venv/bin/activate && python -m core.optuna_tuner hybrid >> logs/tune.log 2>&1'
45 1 * * * /usr/bin/env bash -lc 'cd ~/kang_bot && . .venv/bin/activate && python -m core.optuna_tuner adaptive >> logs/tune.log 2>&1'
```


## Risk Protections (enabled)
- **Daily max loss** 10% (auto-pause)
- **Loss streak pause**: if ≥3 losses beruntun ⇒ cooldown 15 menit
- **Cooldown after loss**: otomatis via streak gate
- **Equity floor**: jika REAL dan equity < $25 ⇒ auto-switch ke TESTNET
- **Leverage cap per mode**: scalping≤20×, hybrid≤15×, swing≤10×, adaptive≤25×
- **Sizing buffer**: -5% pengaman terhadap fee/slippage

> Per permintaan: **tanpa batas** jumlah trade harian (no max trades/day).


### Precision & Notifications
- **Auto rounding**: qty & TP/SL dibulatkan ke **qtyStep / minOrderQty** dan **tickSize** Bybit.
- **Cooldown notif**: bot kirim pesan saat **cooldown mulai** dan **berakhir**.
- **Equity floor notif**: saat equity < floor di mode REAL, bot memberi tahu dan **switch ke TESTNET** otomatis.


### Model & Tuning (lanjutan)
- **Label TP/SL-aware:** long=1 jika dalam horizon bar berikut TP tercapai lebih dulu dari SL (pakai OHLC masa depan terdekat). Lebih selaras dengan eksekusi riil.
- **Time-decay weighting:** sampel terbaru berbobot lebih besar (half-life berbasis timeframe).
- **Feature importance report:** tersimpan di `reports/xgb_<mode>_report.json` (top fitur by gain, AUC CV, params).
- **Telegram summary:** setelah `python -m core.optuna_tuner <mode>` bot mengirim ringkasan skor & top fitur ke admin Telegram.


### Mode trading — tambahan
- **ATR-aware TP/SL**: setiap mode menyesuaikan TP/SL terhadap `atr_frac` (ATR/Close) agar proporsional volatilitas.
- **Gating volatilitas**: 
  - Scalping aktif jika vol di kisaran menengah–tinggi (default 0.20%–2.5%). 
  - Swing aktif bila vol relatif rendah (≤2.0%). 
  - Hybrid di tengah.
  (Bisa disetel via `config/<mode>.json` → `vol_gates` atau adaptif yang pakai `vol_low/vol_high`)
- **Hybrid consensus**: butuh konfirmasi **EMA fast>slow** searah dengan **MACD histogram** agar bias BUY dikuatkan (atau SELL jika sebaliknya).
- **Spread gate (scalping)**: skip entry jika spread > **2 bps** dari mid.
- **Adaptive selector**: pilih mode berdasar **volatilitas saat ini** + `best_score` hasil Optuna (jika tersedia) per mode.


### Notifikasi entry & dashboard
- Bot mengirim **Entry** ke admin dengan alasan: mode_final, vol, spread_ok, consensus, xgb_prob, gpt_conf, conf.
- **Daily dashboard**: ringkasan per-mode (trades, winrate, PnL, ~Sharpe) + **equity chart PNG** via Telegram.
- **Per-mode vol gates** sekarang ada di `config/<mode>.json` dan **ikut dituning** oleh Optuna (`vol_lo`, `vol_hi`).

> Catatan: untuk equity chart/daily job, pastikan `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_ADMIN_USER_ID` sudah terisi di `.env`.


### Realistic tuning & live execution (baru)
- **Backtest nyata (Optuna):** simulasi fee (~0.06% RT), slippage (0.03/side), **partial TP (50/50)**, dan **breakeven** setelah TP1.
- **Multi-timeframe (MTF) features:** tambahkan konfirmasi TF lebih tinggi (`mtf.confirm_tf`, default 60m untuk Hybrid/Adaptive).
- **Live manager:** pantau posisi → jika TP1 tercapai, **SL digeser ke breakeven**; sekaligus pasang **dua TP reduce-only** (50%/50%).

> Catatan: API Bybit kadang membatasi penempatan order reduce-only bersamaan; fungsi `manage_open_positions` sifatnya **best effort** dan dipanggil di loop.


### Per-mode TP split & Breakeven
- Masing-masing mode punya `tp_split`:
  ```json
  { "tp_split": { "tp1": 0.6, "tp2": 0.4, "breakeven_trigger": 0.4 } }
  ```
- Manager posisi akan:
  - Menempatkan TP1/TP2 reduce-only sesuai rasio,
  - Menggeser SL ke **breakeven** setelah TP1 terlewati,
  - Mencatat event `TP1_TOUCH`, `TP2_TOUCH`, `BE_ACTIVATED` ke `profit.json` (bagian `history`).

### Min Notional
- Validasi **min notional** dilakukan sebelum order (jika info tersedia dari Bybit), selain step/qty minimum.

> Catatan: Event TP1/TP2 dicatat berbasis heuristik (price touch), bukan fill resmi API. Untuk akurasi penuh, kita bisa tambah polling `get_execution_list` khusus order reduce-only dan rekonsiliasi orderId.


### Konfirmasi visual saat ganti mode
- Saat kamu mengganti mode (via tombol atau `/mode <nama>`), bot menampilkan ringkasan:
  - Env (TESTNET/REAL), Timeframe, TP/SL, Leverage cap,
  - Pairs (Auto TopN/Manual) + TopN + daftar kandidat,
  - Notif level (Detailed/Brief),
  - TP split & Breakeven trigger,
  - Volatility gate rentang aktif.


**Ringkasan mode (Telegram) kini juga menampilkan:**
- Confidence threshold eksekusi sinyal
- Max open positions
- Daily max loss (auto-pause)


## Streamlit Dashboard
Dashboard web modern untuk monitoring & kontrol ringan.

### Jalankan secara lokal/VPS
```bash
# (opsional) aktifkan venv yang sama
pip install -r requirements.txt
streamlit run streamlit_app/app.py --server.port 8501 --server.address 0.0.0.0
```
Lalu buka di browser: `http://<IP-VPS>:8501`

### Fitur
- **Header cards**: Equity, 24h Winrate, Mode, Env
- **Charts**: Equity curve, PnL & Winrate per mode, Candle + trade markers
- **Controls** (sidebar):
  - Toggle REAL/TESTNET, Pause
  - Ganti Mode
  - Confidence threshold, Max Open Positions, Daily Max Loss (Save Risk Settings)
  - Auto pairs + TopN (Save Pairs Settings)
  - Notify level: Detailed/Brief
- **Tables**: 50 trade terakhir
- Menggunakan file yang sama dengan bot (`data/state.json`, `config/*.json`, `data/profit.json`) sehingga perubahan langsung terbaca oleh bot.


### Live Socket + Multi-symbol + Date Filter
- Jalankan server WS lokal:
  ```bash
  python streamlit_app/ws_server.py --host 0.0.0.0 --port 8765
  ```
- Di dashboard, aktifkan **Enable Live WS** dan isi URL (default `ws://localhost:8765`).
- Pilih **multi-symbol** untuk chart candle di tab terpisah.
- Gunakan **date filter** untuk membatasi data riwayat pada range tanggal tertentu.


## 24/7 Ops (E2E)

### Systemd setup (VPS)
```bash
# as your user (with kang_bot extracted at ~/kang_bot)
sudo cp -a systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kangbot.service kangbot-ws.service kangbot-streamlit.service
sudo systemctl start  kangbot.service kangbot-ws.service kangbot-streamlit.service

# status
systemctl status kangbot.service
journalctl -u kangbot.service -f
```

### Healthcheck (cron)
Jalankan setiap 5 menit; exit code non-zero menandakan masalah (bisa dipakai alerting).
```bash
*/5 * * * * /usr/bin/env bash -lc 'cd ~/kang_bot && . .venv/bin/activate && python tools/health_check.py >> logs/health.log 2>&1'
```

### Log rotation
Semua modul pakai **RotatingFileHandler** (2MB x 5 berkas) di folder `logs/`.

### Heartbeat
`run.py` menulis `state.json.heartbeat_ts` setiap loop; healthcheck memvalidasi staleness (>5 menit).

### Crash guard
`run.py` punya global try/except; jika terjadi error fatal, proses keluar bersih dan **systemd** akan **restart** otomatis.



## Docker (Compose)
Jalankan seluruh stack (bot + websocket + dashboard) dalam container:
```bash
cp .env.example .env  # isi dengan kredensialmu
docker compose up -d --build
docker compose logs -f bot
```

- Layanan:
  - **bot**: loop trading (port tidak dipublikasikan)
  - **ws**: WebSocket snapshot (port **8765**)
  - **dashboard**: Streamlit (port **8501**)

### Update / deploy ulang
```bash
git pull  # atau sync file terbaru
docker compose build
docker compose up -d
```

## Alert Telegram (Healthcheck)
File `tools/health_check.py` sekarang mengirim pesan ke **Telegram admin** jika:
- Heartbeat **stale** (>5 menit),
- `profit.json` tidak valid (mis. `equity` hilang).

Integrasikan via cron (contoh setiap 5 menit):
```bash
*/5 * * * * /usr/bin/env bash -lc 'cd ~/kang_bot && docker compose exec -T bot python tools/health_check.py >> logs/health.log 2>&1'
```
Pastikan **TELEGRAM_BOT_TOKEN** dan **TELEGRAM_ADMIN_USER_ID** sudah benar di `.env`.


### Model improvements (v18)
- **TimeSeriesSplit CV** + **Isotonic calibration** untuk XGBoost → probabilitas lebih terkalibrasi.
- **Per-mode thresholds**: `confidence_threshold`, `min_edge_bps` ditune dan dipakai runtime.
- **Expected-edge gate**: EV = p*TP − (1−p)*SL − fee − slip − spread → SKIP jika di bawah ambang.
- **Idempotent orders**: `clientOrderId` unik + cek order reduce-only agar tidak dobel.
- **Retry/backoff**: wrapper `_retry()` untuk panggilan HTTP Bybit.

### Retrain semua mode
```bash
python -m core.retrain_all
```


## Self-Test (No API calls)
Jalankan uji cepat untuk memastikan modul, config, dan alur sinyal tidak error:
```bash
bash scripts/test_all.sh
# atau
python tools/self_test.py
```
Tes ini:
- Cek import modul utama
- Validasi file config/json
- Bangun **dummy data** dan jalankan `combine_signals()` untuk semua mode
- Pastikan **Streamlit app** bisa di-import

> Catatan: Self-test tidak memanggil API Bybit/Telegram/OpenAI; aman dijalankan di lingkungan manapun.


### Telegram: Testnet/Real Controls
- **Inline button:** `⚡ Env: TESTNET/REAL` untuk toggle cepat.
- **Command:** `/env testnet` atau `/env real` untuk set environment secara eksplisit.
Status tersimpan di `data/state.json:testnet` dan dipakai di runtime.


### Confidence Threshold per Mode (v22)
- **Scalping**: 0.85
- **Swing**: 0.75
- **Hybrid**: 0.75
- **Adaptive**: `auto` — dihitung dari winrate 30 trade terakhir dengan batas [0.75, 0.90].


### Simulation Mode
- **Tujuan**: Uji alur bot tanpa mengirim order ke Bybit.
- **Aktivasi**:
  - Telegram inline button: **🧪 Sim: On/Off**
  - Command: `/sim on` atau `/sim off`
  - Atau set di `config/global.json`: `"simulation_mode": true`
- Saat aktif, semua fungsi eksekusi order akan **disimulasikan** (tidak ada order real/testnet) dan dicatat via `log_event`.



# Walk-Forward Backtest Patch

Tambahkan dua file berikut ke project `kang_bot` kamu:
- `core/backtest_walkforward.py`
- `tools/run_walkforward.py`

## Cara pakai
```bash
# API (testnet; fallback ke data sintetis jika fetch gagal)
python tools/run_walkforward.py --mode hybrid --testnet

# CSV lokal (wajib: start,open,high,low,close)
python tools/run_walkforward.py --mode swing --source csv --csv data/BTCUSDT_15m.csv
```

Output:
- `reports/walk_<mode>_<ts>.json` → ringkasan (trades, winrate, pnl_sum, equity_final)
- `reports/walk_<mode>_<ts>.csv`  → detail setiap trade.



## PRIORITAS: Stabilitas & Keamanan
- **Healthcheck:** `python tools/health_check.py` (cek heartbeat, env, auto-pause)
- **Daily Report Telegram:** `python tools/daily_report_to_telegram.py`
- **Walk-Forward Harian:** `python tools/daily_walkforward.py` (ringkasan ke Telegram)

### PIN Proteksi REAL Mode (Telegram)
- Set PIN: `/set_pin 123456`
- Verifikasi: `/pin 123456`
- Switch REAL (wajib PIN): `/env real`

### Streamlit Password (opsional)
Set env `STREAMLIT_PASSWORD=...` agar dashboard tidak publik.

### Contoh Cron (07:00 UTC harian)
```
0 7 * * * cd ~/kang_bot && /usr/bin/python3 tools/daily_walkforward.py >> logs/wf.log 2>&1
5 7 * * * cd ~/kang_bot && /usr/bin/python3 tools/daily_report_to_telegram.py >> logs/daily.log 2>&1
*/10 * * * * cd ~/kang_bot && /usr/bin/python3 tools/health_check.py >> logs/health.log 2>&1
```
