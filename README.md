# 🎙️ Sinhronizuj.me
### AI Video Sinhronizacija na Srpski Jezik — Hibridna Arhitektura V2

**Sinhronizuj.me** je napredni "end-to-end" sistem za automatizovanu video sinhronizaciju (dubbing). Koristeći hibridnu cloud arhitekturu, sistem kombinuje stabilnost **Hetzner VPS Control Plane-a** sa sirovom GPU snagom **RunPod Serverless** radnika.

---

## 🚀 Ključne Karakteristike

- **Hibridna Arhitektura:** Kontrolna logika, storage i orkestracija na Hetzner VPS-u; teška GPU obrada (Whisper, Qwen, Fish TTS) na RunPod Serverless instancama.
- **Direktan Upload:** Korisnik može uploadovati lokalne video fajlove direktno u MinIO S3 storage putem Presigned URL-ova (bez prolaska kroz backend).
- **TOON Format:** Token-Oriented Object Notation — kompaktni format za komunikaciju sa LLM-om koji štedi do 40% tokena u odnosu na JSON.
- **Multimodalni Kontekst:** Sistem ekstrahuje vizuelne frejmove videa (sprite-sheets) koje AI model „gleda" radi preciznijeg prevoda (rodovi, kontekst, ton).
- **Voice Cloning:** Korišćenjem *Fish Speech 1.5*, postiže se visoka sličnost sa originalnim govornikom.
- **Studio Interface:** Moderni React frontend sa real-time progresom, uporednim prikazom originala i prevoda, i vizuelnim kontekstom.

---

## 🛠️ Tehnološki Stack

| Sloj | Tehnologije |
|---|---|
| **Frontend** | React (Vite), Framer Motion, Lucide Icons |
| **Control Plane (Hetzner VPS)** | FastAPI, Celery, Redis, PostgreSQL, MinIO (S3) |
| **Compute Plane (RunPod)** | RunPod Serverless (RTX 3090 / 4090 / A6000) |

### AI Pipeline (Faze Obrade)

| Faza | Alat | Opis |
|---|---|---|
| 1. Preuzimanje | `yt-dlp` / S3 Upload | YouTube link ili direktan upload lokalnog fajla |
| 2. Separacija | `Demucs v4 (htdemucs)` | Izolacija vokala od pozadinske muzike |
| 3. Transkripcija | `Faster-Whisper` (RunPod) | Prepoznavanje govora iz izolovanog vokala |
| 4. Prevod | `Qwen 32B/35B` via vLLM (TOON) | Kontekstualno prevođenje sa vizuelnim kontekstom |
| 5. Sinteza | `Fish Speech 1.5` (RunPod) | Generisanje srpskog glasa sa kloniranim tembrom |
| 6. Spajanje | `FFmpeg` (`-c:v copy`) | Finalno spajanje slike, pozadine i novog glasa |
| 7. Lip Sync | `Wav2Lip` (opciono) | Sinhronizacija usana — preskače se za videa bez lica |

---

## 📦 Infrastruktura

### Hetzner VPS (Control Plane)
- **Model:** CPX32 — 4 vCPU (AMD), 8 GB RAM, 160 GB NVMe SSD
- **IP:** `178.104.214.78`
- **Servisi:** Redis (port 6379), MinIO S3 (port 9000), PostgreSQL
- **Docker Compose** za orkestraciju svih servisa

### RunPod Serverless (Compute Plane)
- **Whisper Endpoint:** `3wqmtjpb3z2z18` — RTX 3090/4000 Ada
- **Translator Endpoint:** `ehsr5yiypxz4ap` — RTX A6000 (48GB VRAM)
- **TTS Endpoint:** `9zx2al4sof2ian` — RTX 3090/4090

### MinIO S3 Storage
- **Bucket:** `uploads`
- **Pristup:** Presigned URL-ovi za direktan klijent-to-storage upload

---

## 🖥️ Pokretanje (Lokalni Development)

### 1. Backend
```bash
cd /home/gruya/Projektri/sinhronizuj.me
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Celery Worker
```bash
celery -A backend.worker.celery_app worker --loglevel=info
```

### 3. Frontend
```bash
cd frontend
npm run dev
```

### 4. Infrastruktura (Hetzner VPS)
```bash
ssh root@178.104.214.78
cd /opt/sinhronizuj-me
docker compose up -d
```

---

## ⚙️ Konfiguracija (.env)

```env
RUNPOD_API_KEY=rpa_...
RUNPOD_WHISPER_ID=3wqmtjpb3z2z18
RUNPOD_TRANSLATOR_ID=ehsr5yiypxz4ap
RUNPOD_TTS_ID=9zx2al4sof2ian
REDIS_URL=redis://178.104.214.78:6379/0
MINIO_ENDPOINT=178.104.214.78:9000
MINIO_ACCESS_KEY=sinhronizuj_storage
MINIO_SECRET_KEY=***
MINIO_BUCKET=uploads
```

---

## 📁 Struktura Projekta

```
sinhronizuj.me/
├── backend/
│   ├── main.py              # FastAPI server (API + presigned URL)
│   ├── core/
│   │   └── config.py        # Centralna konfiguracija (env varijable)
│   └── worker/
│       ├── celery_app.py    # Celery konfiguracija
│       ├── tasks.py         # Glavni pipeline (Faze 1-7)
│       ├── downloader.py    # YouTube/S3 preuzimanje
│       ├── audio_sep.py     # Demucs separacija vokala
│       ├── preprocessor.py  # Vizuelni kontekst (frejmovi)
│       ├── transcriber.py   # RunPod Whisper transkripcija
│       ├── translator.py    # RunPod vLLM prevod (TOON format)
│       ├── tts_engine.py    # RunPod Fish Speech sinteza
│       ├── merger.py        # FFmpeg spajanje
│       ├── lipsync.py       # Wav2Lip detekcija/sinhronizacija
│       └── hw_monitor.py    # Hardverski monitoring
├── frontend/
│   └── src/
│       ├── App.jsx          # React studio interfejs
│       └── index.css        # Glassmorphism stilovi
├── infra/                   # Docker/VPS konfiguracija
├── docker-compose.yml       # Lokalni Docker compose
├── Dockerfile               # Backend kontejner
├── requirements.txt         # Python zavisnosti
├── PLAN_ARHITEKTURE_V2.md   # Detaljan plan arhitekture
└── istorija_izrade.md       # Hronološki dnevnik razvoja
```

---

## 🐛 Poznati Problemi (In Progress)

| Problem | Status | Opis |
|---|---|---|
| RunPod 401 Unauthorized | 🔴 Aktivan | Celery worker dobija 401 pri pozivu RunPod Whisper endpointa, iako isti API ključ radi iz standalone Python skripte. Istraga u toku — moguć problem sa učitavanjem env varijabli u Celery fork procesima. |
| CORS za MinIO PUT | 🟡 Potencijalan | Browser može blokirati direktan PUT ka MinIO ako CORS nije eksplicitno konfigurisan na serveru. |
| Demucs shebang putanje | ✅ Rešen | Skripte u venv-u su imale zastarele putanje od starog naziva projekta (daca_dub). Popravljeno. |
| torchcodec zavisnost | ✅ Rešen | Instaliran `torchcodec` paket koji je nova zavisnost za `torchaudio`. |

---

## 📝 Dokumentacija

- **`istorija_izrade.md`** — Hronološki dnevnik svih izmena i odluka.
- **`PLAN_ARHITEKTURE_V2.md`** — Detaljan opis hibridnog sistema, optimizacija i pravila.

---

**Sinhronizuj.me** — *Jer tehnologija treba da priča tvojim jezikom.* 🇷🇸
