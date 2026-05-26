# 🎙️ Sinhronizuj.me
### AI Video Sinhronizacija na Srpski Jezik — Hibridna Arhitektura (VPS + Modal.com)

**Sinhronizuj.me** je napredni "end-to-end" sistem za automatizovanu video sinhronizaciju (dubbing). Koristeći hibridnu cloud arhitekturu, sistem kombinuje stabilnost **Control Plane-a** na Hetzner VPS-u sa serverless GPU snagom na **Modal.com** platformi za izvršavanje zahtevnih AI modela.

---

## 🚀 Ključne Karakteristike

- **Hibridna Arhitektura:** Kontrolna logika, baza podataka, asinhroni Celery radnik i MinIO (S3) lokalno skladište nalaze se na Hetzner VPS-u, dok se teške AI operacije (Demucs, Whisper, SenseVoice, Qwen-VL prevod, Lektor, Piper TTS i Wav2Lip) izvršavaju serverless na **Modal.com** (T4, A10G, H100/L4 GPU-ovi).
- **Direktan Upload:** Korisnik može uploadovati lokalne video fajlove direktno u MinIO Object Storage pomoću Presigned URL-ova.
- **Ensemble ASR & LLM Arbitraža:** Paralelno prepoznavanje govora pomoću modela **Whisper** (sa reč-po-reč tajminzima) i **SenseVoice-Small** na Modalu. Lektor (Qwen 32B) automatski arbitruje između njih i ispravlja greške u sluhu/pravopisu pre prevođenja, bez narušavanja vremenskih oznaka.
- **Normalizacija Audia i VAD Optimizacije:** Integrisana RMS normalizacija vokalnog signala na `-20.0 dBFS` pre transkripcije, uz upotrebu `speech_pad_ms=400` kako bi se sprečilo sečenje krajeva reči u tišini.
- **Jednostavan 2-Pass Prevod i Lektura:** 
  1. **Pass 1 (Translator - Qwen2-VL):** Multimodalni model koji na osnovu 10 frejmova iz videa prepoznaje rod govornika, kontekst i prevodi tekst na srpski.
  2. **Pass 2 (Lektor - Qwen 2.5 32B Instruct):** Jezički model na H100 koji pegla gramatiku, srpske padeže, stilske oblike i formatira tekst spreman za TTS sintezu.
- **TTS Normalizacija:** Ugrađena pravila za automatsko ispisivanje brojeva slovima i fonetski prevod engleskih brendova (npr. *„Indeed”* -> *„Indid”*, *„AI”* -> *„Ej Aj”*).
- **Dinamički Time Stretching (Video & Audio):** Dinamičko ubrzavanje ili usporavanje videa i pozadinske muzike (do 1.15x) kada je srpski izgovor duži od originalnog engleskog govora, kombinovano sa preciznim lektorskim ograničenjem broja reči (`trajanje * 3`) i laganim ubrzavanjem audia.
- **Sinhronizacija Usana (Wav2Lip):** Pokretanje serverless Wav2Lip modela za fotorealistično prilagođavanje pokreta usana govornika srpskom audio zapisu.
- **Studio Interface:** Moderni React frontend sa real-time progresom faza, uporednim prikazom originalnih i prevedenih segmenata i vizuelnim kontekstom frejmova.

---

## 🛠️ Tehnološki Stack

| Sloj | Tehnologije |
|---|---|
| **Frontend** | React (Vite), Framer Motion, Tailwind CSS, Lucide Icons |
| **Control Plane (VPS)** | FastAPI (API server), Celery (Asinhroni radnik), Redis (Message Broker / Cache), PostgreSQL (Baza), MinIO (S3 Object Storage) |
| **Compute Plane (Modal)** | Demucs (Separacija vokala - T4 GPU), Whisper (STT - T4 GPU), SenseVoice-Small (Sekundarni ASR - T4 GPU), Qwen2-VL-7B (Prevodilac - A10G GPU), Qwen2.5-32B-Instruct (Lektor - H100 GPU), Fish Speech v1.5.1 (TTS - L4 GPU), Wav2Lip (LipSync - A10G GPU) |

### AI Pipeline (Faze Obrade)

1. **Preuzimanje:** Preuzimanje YouTube videa ili dobijanje direktno sa MinIO S3 skladišta.
2. **Separacija (Demucs):** Izolacija vokalne trake od pozadinske muzike i zvučnih efekata na Modalu (prebačeno sa VPS-a na GPU za bolje performanse i oslobađanje resursa).
3. **Transkripcija (Ensemble ASR):** Paralelno prepoznavanje pomoću Whisper-a (sa reč-po-reč tajminzima) i SenseVoice-Small na Modalu, praćeno LLM arbitražom za automatsku ispravku grešaka i normalizacijom zvuka na -20.0 dBFS.
4. **Prevod & Lektura:** Multimodalni prevod (Qwen2-VL) sa 10 frejmova, nakon čega sledi stilsko peglanje teksta i vremensko sažimanje (Qwen 2.5 Lektor).
5. **Sinteza (TTS - Piper):** Generisanje srpskog govora (muški glas 'sr_Marko') uz zadržavanje prirodnog tempa izgovora (bez nasilnog ubrzavanja na nivou TTS-a).
6. **Dinamičko Rastezanje & Spajanje:** Primena dynamic time stretching-a na video i muziku (do 1.15x) i FFmpeg aresample spajanje.
7. **Sinhronizacija Usana (Wav2Lip):** Prilagođavanje usana govornika generisanom srpskom audiju pomoću Wav2Lip modela.

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
│       ├── audio_sep.py     # Separacija vokala pomoću Demucs-a na Modalu
│       ├── preprocessor.py  # Ekstrakcija vizuelnog konteksta (frejmovi)
│       ├── transcriber.py   # Pozivanje Modal Whisper & SenseVoice STT sa LLM arbitražom
│       ├── translator.py    # Pozivanje Modal Translator i Lektor API-ja
│       ├── tts_engine.py    # Pozivanje Piper TTS modela na Modalu
│       └── merger.py        # Dynamic Time Stretching i spajanje audio/video zapisa (FFmpeg)
├── frontend/
│   └── src/
│       ├── App.jsx          # React Studio korisnički interfejs
│       └── index.css        # Premium Glassmorphism stilovi
├── modal_workers/           # Serverless radnici na Modal.com
│   ├── demucs_worker.py     # Demucs radnik na Modalu (separacija vokala)
│   ├── stt_worker.py        # Whisper STT radnik (Faster-Whisper na T4)
│   ├── sensevoice_worker.py # SenseVoice ASR radnik za sekundarnu transkripciju
│   ├── translator_worker.py # Multimodalni Translator radnik (Qwen2-VL)
│   ├── lektor_worker.py     # Jezički lektor radnik (Qwen 2.5 32B Instruct)
│   ├── tts.py               # Generički TTS generator (Fish Speech v1.5.1 na L4)
│   └── tts_openvoice.py     # Piper + OpenVoice TTS generator (Marko sr_Marko_medium na L4)
├── docker-compose.yml       # Docker compose za lokalne servise (Postgres, Redis, MinIO)
├── Dockerfile               # API/Worker Docker slika za Hetzner VPS
├── requirements.txt         # Python biblioteke
└── istorija_izrade.md       # Dnevnik razvoja sa hronološkim izmenama
```

---

## 🗺️ Plan Daljeg Razvoja

U narednim fazama razvoja planirane su sledeće strateške stavke iz brainstorm planova:
1. **Prepoznavanje Govornika (Diarization) & Multi-Voice Cloning:** Integracija `PyAnnote.audio` modela na Modalu za automatsko označavanje i isecanje referentnih audio isečaka za svakog govornika u videu, te slanje na individualnu sintezu glasa (idealno za intervjue i podcaste).
2. **HD Face Restoration za LipSync:** Propuštanje Wav2Lip izlaza kroz modele za restauraciju i izoštravanje lica (GFPGAN ili CodeFormer) kako bi se postigla HD rezolucija i izbeglo zamućenje predela oko usana na 1080p/4K videima.
3. **Interaktivni Studio Editor (v2):** Izgradnja naprednog table-editora na frontendu koji pauzira pipeline nakon prevođenja, omogućavajući korisniku da ručno promeni prevod, spoji segmente ili vizuelno poravna audio blokove na zvučnom talasu (`wavesurfer.js`) pre sinteze i spajanja.
4. **Pametan Prevodilac - Korisnički Rečnik (Glossary):** Mogućnost unosa prilagođenih rečnika direktno na frontendu koji se šalju sistemskom promptu Qwen Lektora kako bi se osigurao konzistentan prevod specifičnih tehničkih termina.

---

**Sinhronizuj.me** — *Jer tehnologija treba da priča tvojim jezikom.* 🇷🇸
