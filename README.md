# 🎙️ Sinhronizuj.me
### AI Video Sinhronizacija na Srpski Jezik — Hibridna Arhitektura (VPS + Modal.com)

**Sinhronizuj.me** je napredni "end-to-end" sistem za automatizovanu video sinhronizaciju (dubbing). Koristeći hibridnu cloud arhitekturu, sistem kombinuje stabilnost **Control Plane-a** na Hetzner VPS-u sa serverless GPU snagom na **Modal.com** platformi za izvršavanje zahtevnih AI modela.

---

## 🚀 Ključne Karakteristike

- **Hibridna Arhitektura:** Kontrolna logika, baza podataka, asinhroni Celery radnik i MinIO (S3) lokalno skladište nalaze se na Hetzner VPS-u, dok se teške AI operacije (Whisper STT, Qwen-VL prevod, Lektor i Fish Speech TTS) izvršavaju serverless na **Modal.com** (T4, A10G, H100/L4 GPU-ovi).
- **Direktan Upload:** Korisnik može uploadovati lokalne video fajlove direktno u MinIO Object Storage pomoću Presigned URL-ova.
- **Jednostavan 2-Pass Prevod i Lektura:** 
  1. **Pass 1 (Translator - Qwen2-VL):** Multimodalni model koji na osnovu 10 frejmova iz videa prepoznaje rod govornika, kontekst i prevodi tekst na srpski.
  2. **Pass 2 (Lektor - Qwen 2.5 32B Instruct):** Jezički model na H100 koji pegla gramatiku, srpske padeže, stilske oblike i formatira tekst spreman za TTS sintezu.
- **TTS Normalizacija:** Ugrađena pravila za automatsko ispisivanje brojeva slovima i fonetski prevod engleskih brendova (npr. *„Indeed”* -> *„Indid”*, *„AI”* -> *„Ej-Aj”*).
- **Voice Cloning (Fish Speech v1.5.1):** Sinhronizacija na srpskom jeziku zadržavajući ton i boju glasa originalnog govornika.
- **Studio Interface:** Moderni React frontend sa real-time progresom faza, uporednim prikazom originalnih i prevedenih segmenata i vizuelnim kontekstom frejmova.

---

## 🛠️ Tehnološki Stack

| Sloj | Tehnologije |
|---|---|
| **Frontend** | React (Vite), Framer Motion, Tailwind CSS, Lucide Icons |
| **Control Plane (VPS)** | FastAPI (API server), Celery (Asinhroni radnik), Redis (Message Broker / Cache), PostgreSQL (Baza), MinIO (S3 Object Storage) |
| **Compute Plane (Modal)** | Whisper (STT - T4 GPU), Qwen2-VL-7B (Prevodilac - A10G GPU), Qwen2.5-32B-Instruct (Lektor - H100 GPU), Fish Speech v1.5.1 (TTS - L4 GPU) |

### AI Pipeline (Faze Obrade)

1. **Preuzimanje:** Preuzimanje YouTube videa ili dobijanje direktno sa MinIO S3 skladišta.
2. **Separacija (Demucs):** Izolacija vokalne trake od pozadinske muzike i zvučnih efekata na VPS-u.
3. **Transkripcija (STT):** Whisper transkripcija izolovanog vokala na Modalu (isključen `condition_on_previous_text` radi izbegavanja repetition loop-a).
4. **Prevod & Lektura:** Multimodalni prevod (Qwen2-VL) sa 10 frejmova, nakon čega sledi stilsko peglanje teksta (Qwen 2.5 Lektor).
5. **Sinteza (TTS - Fish Speech):** Generisanje srpskog govora sa kloniranim glasom originalnog zvučnika na osnovu referentnog audia.
6. **Spajanje (FFmpeg):** Miksovanje generisanog srpskog glasa sa originalnom pozadinskom muzikom i spajanje sa slikom bez rekompresije.

---

## 🖥️ Pokretanje (Lokalni Development)

### 1. Pokretanje lokalne infrastrukture (Docker)
```bash
docker compose up -d
```

### 2. Pokretanje Backend API-ja
```bash
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Pokretanje Celery Worker-a
```bash
celery -A backend.worker.celery_app worker --loglevel=info
```

### 4. Pokretanje Frontenda
```bash
cd frontend
npm run dev
```

---

## ⚙️ Konfiguracija (.env)

Kreirajte `.env` fajl u korenu projekta sa sledećim varijablama:

```env
# API Ključevi
GEMINI_API_KEY=tvoj_gemini_api_key

# Modal Serverless Endpoints
MODAL_STT_URL=https://tvoj-username--sm-stt-only-sttworker-task.modal.run
MODAL_TRANSLATOR_URL=https://tvoj-username--sm-translator-serve.modal.run
MODAL_LEKTOR_URL=https://tvoj-username--sinhronizuj-lektor-serve.modal.run
MODAL_TTS_URL=https://tvoj-username--sm-tts-v110-workerv110-task.modal.run

# Infrastruktura (VPS / Local)
REDIS_PASSWORD=tvoja_jaka_redis_lozinka
REDIS_URL=redis://:tvoja_jaka_redis_lozinka@redis:6379/0
MINIO_ENDPOINT=tvoja-vps-ip:9000
MINIO_ACCESS_KEY=sinhronizuj_storage
MINIO_SECRET_KEY=tvoja_s3_lozinka
MINIO_BUCKET=uploads
```

---

## 📁 Struktura Projekta

```
sinhronizuj.me/
├── backend/
│   ├── main.py              # FastAPI server, presigned URL logika
│   ├── core/
│   │   └── config.py        # Centralna konfiguracija i env varijable
│   └── worker/
│       ├── celery_app.py    # Celery konfiguracija
│       ├── tasks.py         # Celery taskovi (glavni pipeline)
│       ├── downloader.py    # Preuzimanje videa (yt-dlp/S3)
│       ├── audio_sep.py     # Separacija vokala pomoću Demucs-a
│       ├── preprocessor.py  # Ekstrakcija vizuelnog konteksta (frejmovi)
│       ├── transcriber.py   # Pozivanje Modal Whisper STT endpoint-a
│       ├── translator.py    # Pozivanje Modal Translator i Lektor API-ja
│       ├── tts_engine.py    # Pozivanje Modal Fish Speech TTS endpoint-a
│       └── merger.py        # Spajanje audio/video zapisa (FFmpeg)
├── frontend/
│   └── src/
│       ├── App.jsx          # React Studio korisnički interfejs
│       └── index.css        # Premium Glassmorphism stilovi
├── modal_workers/           # Serverless radnici na Modal.com
│   ├── stt_worker.py        # Whisper STT radnik (Faster-Whisper na T4)
│   ├── translator_worker.py # Multimodalni Translator radnik (Qwen2-VL)
│   ├── lektor_worker.py     # Jezički lektor radnik (Qwen 2.5 32B Instruct)
│   └── tts.py               # TTS generator (Fish Speech v1.5.1 na L4)
├── docs/                    # Planovi i tehnička dokumentacija
├── docker-compose.yml       # Docker compose za lokalne servise (Postgres, Redis, MinIO)
├── Dockerfile               # API/Worker Docker slika za Hetzner VPS
├── requirements.txt         # Python biblioteke
└── istorija_izrade.md       # Dnevnik razvoja sa hronološkim izmenama
```

---

## 🗺️ Plan Daljeg Razvoja

U narednim fazama razvoja planirane su sledeće stavke:
1. **Fine-tuning Lektora:** Dodatno obučavanje ili fino podešavanje (fine-tuning) Qwen 2.5 lektorskog modela na specifičnom korpusu srpskog jezika kako bi se eliminisali preostali anglicizmi i poboljšao stilski tok rečenica.
2. **Testiranje i podešavanje TTS-a:** Eksperimentisanje sa različitim govornicima, prilagođavanje brzine govora i fino podešavanje emocija/akcentovanja u Fish Speech-u radi što prirodnijeg srpskog izgovora.
3. **Poboljšanje početka Pipeline-a (Asinhroni Upload):** Izmena toka na frontendu i backendu tako da procesuiranje i upload fajla na S3 ne pokreću automatski dubbing pipeline. Korisnik će prvo odabrati fajl, sačekati da se upload na S3 uspešno završi, a tek onda klikom na dugme "Sinhronizuj" svesno pokrenuti prevođenje i obradu.

---

**Sinhronizuj.me** — *Jer tehnologija treba da priča tvojim jezikom.* 🇷🇸
