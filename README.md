# 🎙️ Sinhronizuj.me
### AI Video Sinhronizacija na Srpski Jezik — Hibridna Arhitektura V2

**Sinhronizuj.me** je napredni "end-to-end" sistem za automatizovanu video sinhronizaciju (dubbing). Koristeći hibridnu cloud arhitekturu, sistem kombinuje stabilnost **Cloud Control Plane-a** sa sirovom GPU snagom **Serverless GPU** radnika.

---

## 🚀 Ključne Karakteristike

- **Hibridna Arhitektura:** Kontrolna logika, skladištenje i orkestracija na VPS-u; teška GPU obrada (Whisper, Qwen, Fish TTS) na Serverless GPU instancama.
- **Direktan Upload:** Korisnik može uploadovati lokalne video fajlove direktno u Object Storage putem Presigned URL-ova (bez opterećivanja glavnog backend-a).
- **TOON Format:** Token-Oriented Object Notation — kompaktni format za komunikaciju sa LLM-om koji štedi do 40% tokena u odnosu na JSON.
- **Multimodalni Kontekst:** Sistem ekstrahuje vizuelne frejmove videa (sprite-sheets) koje AI model „gleda" radi preciznijeg prevoda (rodovi, kontekst, ton).
- **Voice Cloning:** Postiže se visoka sličnost sa originalnim govornikom kroz naprednu AI sintezu.
- **Studio Interface:** Moderni React frontend sa real-time progresom, uporednim prikazom originala i prevoda, i vizuelnim kontekstom.

---

## 🛠️ Tehnološki Stack

| Sloj | Tehnologije |
|---|---|
| **Frontend** | React (Vite), Framer Motion, Lucide Icons |
| **Control Plane (VPS)** | API Server, Asinhroni Worker, Message Broker, Relaciona Baza, Object Storage |
| **Compute Plane** | Serverless GPU (RTX 3090 / 4090 / A6000) |

### AI Pipeline (Faze Obrade)

| Faza | Opis |
|---|---|
| 1. Preuzimanje | YouTube link ili direktan upload lokalnog fajla u Storage |
| 2. Separacija | Izolacija vokala od pozadinske muzike |
| 3. Transkripcija | Prepoznavanje govora iz izolovanog vokala (GPU) |
| 4. Prevod | Kontekstualno prevođenje sa vizuelnim kontekstom (LLM) |
| 5. Sinteza | Generisanje srpskog glasa sa kloniranim tembrom |
| 6. Spajanje | Finalno spajanje slike, pozadine i novog glasa bez rekompresije videa |
| 7. Lip Sync | Sinhronizacija usana kao izolovana Serverless komponenta |

---

## 📦 Infrastruktura

### VPS (Control Plane)
- **Model:** Preporučeno 4 vCPU, 8 GB RAM
- **Servisi:** Message Broker, Object Storage, Database
- **Orkestracija:** Docker Compose za podizanje svih internih servisa

### Serverless GPU (Compute Plane)
- **Transkripcija:** RTX 3090/4000 Ada (ili slično)
- **Prevod (LLM):** RTX A6000 (ili slično, zavisno od modela)
- **Sinteza (TTS):** RTX 3090/4090 (ili slično)

### Object Storage
- **Pristup:** Presigned URL-ovi za direktan klijent-to-storage upload

---

## 🖥️ Pokretanje (Lokalni Development)

### 1. Backend
```bash
cd /putanja/do/projekta/sinhronizuj.me
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --reload
```

### 2. Asinhroni Worker
```bash
celery -A backend.worker.celery_app worker --loglevel=info
```

### 3. Frontend
```bash
cd frontend
npm run dev
```

### 4. Infrastruktura (VPS)
```bash
ssh user@vps-ip-adresa
cd /opt/sinhronizuj-me
docker compose up -d
```

---

## ⚙️ Konfiguracija (.env)

Za pokretanje je potrebno kreirati `.env` fajl na osnovu templejta:

```env
GPU_API_KEY=your_api_key
WHISPER_ENDPOINT_ID=your_whisper_endpoint_id
TRANSLATOR_ENDPOINT_ID=your_translator_endpoint_id
TTS_ENDPOINT_ID=your_tts_endpoint_id

BROKER_URL=broker://your-vps-ip:port/0
STORAGE_ENDPOINT=your-vps-ip:port
STORAGE_ACCESS_KEY=your_storage_access_key
STORAGE_SECRET_KEY=your_storage_secret_key
STORAGE_BUCKET=your_bucket_name
```

---

## 📁 Struktura Projekta

```
sinhronizuj.me/
├── backend/
│   ├── main.py              # API server + presigned URL logika
│   ├── core/
│   │   └── config.py        # Centralna konfiguracija (env varijable)
│   └── worker/
│       ├── celery_app.py    # Worker konfiguracija
│       ├── tasks.py         # Glavni pipeline (Faze 1-7)
│       ├── downloader.py    # Preuzimanje materijala
│       ├── audio_sep.py     # Separacija vokala
│       ├── preprocessor.py  # Vizuelni kontekst (frejmovi)
│       ├── transcriber.py   # GPU transkripcija
│       ├── translator.py    # LLM prevod (TOON format)
│       ├── tts_engine.py    # AI sinteza glasa
│       ├── merger.py        # Spajanje audio/video fajlova
│       ├── lipsync.py       # Detekcija/sinhronizacija usana
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

## 📝 Dokumentacija

- **`istorija_izrade.md`** — Hronološki dnevnik svih izmena i odluka.
- **`PLAN_ARHITEKTURE_V2.md`** — Detaljan opis hibridnog sistema, optimizacija i pravila.

---

**Sinhronizuj.me** — *Jer tehnologija treba da priča tvojim jezikom.* 🇷🇸
