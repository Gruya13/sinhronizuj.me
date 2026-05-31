# 🎙️ Sinhronizuj.me
### AI Video Sinhronizacija na Srpski Jezik — Hibridna Arhitektura (VPS + Modal.com)

**Sinhronizuj.me** je napredni "end-to-end" sistem za automatizovanu video sinhronizaciju (dubbing). Koristeći hibridnu cloud arhitekturu, sistem kombinuje stabilnost **Control Plane-a** na Hetzner VPS-u sa serverless GPU snagom na **Modal.com** platformi za izvršavanje zahtevnih AI modela.

---

## 🚀 Ključne Karakteristike

- **Hibridna Arhitektura:** Kontrolna logika, baza podataka, asinhroni Celery radnik i MinIO (S3) lokalno skladište nalaze se na Hetzner VPS-u, dok se teške AI operacije (Demucs, Whisper, SenseVoice, Qwen-VL prevod, Lektor, Piper/OpenVoice V2 TTS i Wav2Lip) izvršavaju serverless na **Modal.com** (T4, A10G, H100/L4 GPU-ovi).
- **Dvofazni Asinhroni Pipeline:** Ceo proces je podeljen na **Fazu 1: Analizu** i **Fazu 2: Renderovanje**. Faza 1 vrši separaciju, transkripciju i inicijalni prevod koji se perzistira u Redis bazi kao nacrt (draft), dok Faza 2 vrši finalno sklapanje i Wav2Lip.
- **Studio Editor v2 (Interaktivna Vremenska Linija):** Moderni React studio interfejs sa vremenskom linijom koja prikazuje frejmove videa, waveform engleskog govora i waveform sinhronizovanog srpskog TTS-a. Automatski detektuje predugačke segmente (crvena zona i tooltip sa objašnjenjem na hover).
- **AI Lektor na klik (Čarobni štapić - Magic Shorten):** Integrisana ikonica čarobnog štapića koja na klik šalje zahtev Modal Qwen Lektoru da inteligentno skrati srpski prevod na optimalnu dužinu (`duration * 20` karaktera) kako bi stao u originalni vremenski prozor.
- **Fino podešavanje zvuka po segmentu:** Nezavisni slajderi za **jačinu zvuka (Volume)**, **brzinu govora (Tempo)**, **visinu tona (Pitch)** i **prigušenje pozadinske muzike (Ducking)** po segmentu, uz checkbox **"Primeni na sve segmente"** za masovno sinhronizovanje zvuka.
- **Brza proba glasa i Hot-Patching (Splicing):** Korisnik može izabrati muški glas ili **klonirati originalni glas (OpenVoice V2)**. Promene na pojedinačnim segmentima se testiraju u letu pomoću hot-patching splicinga (pomoću `pydub`) koji reže stari glas i ubacuje novi u spojeni miks, sa cache-buster-om za glatku reprodukciju.
- **Realtime Klijentski Mikser:** Dva nezavisna zvučna plejera (srpski vokali + muzika bez vokala) koji se u 50ms intervalu sinhronizuju sa videom i reaguju na promenu položaja slajdera u realnom vremenu bez ikakvog seckanja zvuka.
- **Direktan Upload:** Korisnik može uploadovati lokalne video fajlove direktno u MinIO Object Storage pomoću Presigned URL-ova.
- **Ensemble ASR & LLM Arbitraža:** Paralelno prepoznavanje govora pomoću modela **Whisper** (sa reč-po-reč tajminzima) i **SenseVoice-Small** na Modalu. Lektor (Qwen 32B) automatski arbitruje između njih i ispravlja greške u sluhu/pravopisu pre prevođenja, bez narušavanja vremenskih oznaka.
- **Normalizacija Audia i VAD Optimizacije:** Integrisana RMS normalizacija vokalnog signala na `-20.0 dBFS` pre transkripcije, uz upotrebu `speech_pad_ms=400` kako bi se sprečilo sečenje krajeva reči u tišini.
- **Jednostavan 2-Pass Prevod i Lektura:** 
  1. **Pass 1 (Translator - Qwen2-VL):** Multimodalni model koji na osnovu 10 frejmova iz videa prepoznaje rod govornika, kontekst i prevodi tekst na srpski.
  2. **Pass 2 (Lektor - Qwen 2.5 32B Instruct):** Jezički model na H100 koji pegla gramatiku, srpske padeže, stilske oblike i formatira tekst spreman za TTS sintezu.
- **TTS Normalizacija:** Ugrađena pravila za automatsko ispisivanje brojeva slovima i fonetski prevod engleskih brendova (npr. *„Indeed”* -> *„Indid”*, *„AI”* -> *„Ej Aj”*).
- **Dinamički Time Stretching (Video & Audio):** Dinamičko ubrzavanje ili usporavanje videa i pozadinske muzike (do 1.15x) kada je srpski izgovor duži od originalnog engleskog govora, kombinovano sa preciznim lektorskim ograničenjem broja reči (`trajanje * 3`) i laganim ubrzavanjem audia.
- **Sinhronizacija Usana (Wav2Lip):** Pokretanje serverless Wav2Lip modela za fotorealistično prilagođavanje pokreta usana govornika srpskom audio zapisu.

---

## 🛠️ Tehnološki Stack

| Sloj | Tehnologije |
|---|---|
| **Frontend** | React (Vite), Framer Motion, Tailwind CSS, Lucide Icons |
| **Control Plane (VPS)** | FastAPI (API server), Celery (Asinhroni radnik), Redis (Message Broker / Cache), PostgreSQL (Baza), MinIO (S3 Object Storage) |
| **Compute Plane (Modal)** | Demucs (Separacija vokala - T4 GPU), Whisper (STT - T4 GPU), SenseVoice-Small (Sekundarni ASR - T4 GPU), Qwen2-VL-7B (Prevodilac - A10G GPU), Qwen2.5-32B-Instruct (Lektor - H100/A100 GPU), Piper & OpenVoice V2 (Glasovno kloniranje/TTS - L4 GPU), Wav2Lip (LipSync - A10G GPU) |

### AI Pipeline (Faze Obrade)

#### Faza 1: Asinhrona Analiza (`analyze_video_task`)
1. **Preuzimanje:** Preuzimanje YouTube videa ili dobijanje direktno sa MinIO S3 skladišta.
2. **Separacija (Demucs):** Izolacija vokalne trake od pozadinske muzike i zvučnih efekata na Modalu.
3. **Transkripcija:** Prepoznavanje pomoću Whisper-a (sa reč-po-reč tajminzima) i SenseVoice-Small na Modalu, praćeno LLM arbitražom za automatsku ispravku grešaka i normalizacijom zvuka na -20.0 dBFS.
4. **Prevod & Lektura:** Multimodalni prevod (Qwen2-VL) sa 10 frejmova, nakon čega sledi stilsko peglanje teksta i vremensko sažimanje (Qwen 2.5 Lektor). Rezultat se čuva u Redis bazi kao nacrt (draft).

#### Interaktivna Studio Faza (Korisnički rad u realnom vremenu)
- Korisnik učitava nacrt u Studio Editor i može:
  - Ručno menjati prevod i koristiti **AI Lektora (Čarobni štapić)** za skraćivanje predugih rečenica na preporučeni limit.
  - Podešavati **Volume, Tempo, Pitch i Ducking** (pozadinsku muziku) po segmentu, ili masovno sinhronizovati zvučne parametre ("Primeni na sve").
  - Birati muški ili klonirani glas (OpenVoice V2) po segmentu i preslušavati brzi preview koji se generiše kroz hot-patching splicing.

#### Faza 2: Finalno Renderovanje (`render_video_task`)
1. **Sinteza (TTS):** Batch generisanje srpskog govora na Modalu za sve promenjene segmente.
2. **Zvučni procesor:** Primena FFmpeg rubberband i volume filtera na audio fajlove pojedinačnih segmenata.
3. **Dinamičko Rastezanje & Spajanje:** Primena dynamic time stretching-a na video i muziku (do 1.15x) shodno trajanju govora i spajanje svih delova u `merged_vocals.wav` sa duckingom pozadinske muzike.
4. **LipSync (Wav2Lip):** Sinhronizacija pokreta usana govornika sa generisanim srpskim audio zapisom i spajanje svih komponenti u finalni MP4.

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
├── istorija_izrade.md       # Dnevnik razvoja sa hronološkim izmenama
```

---

## 🗺️ Plan Daljeg Razvoja

U narednim fazama razvoja planirane su sledeće strateške stavke iz brainstorm planova:
1. **Prepoznavanje Govornika (Diarization) & Multi-Voice Cloning:** Integracija `PyAnnote.audio` modela na Modalu za automatsko označavanje i isecanje referentnih audio isečaka za svakog govornika u videu, te slanje na individualnu sintezu glasa (idealno za intervjue i podcaste).
2. **HD Face Restoration za LipSync:** Propuštanje Wav2Lip izlaza kroz modele za restauraciju i izoštravanje lica (GFPGAN ili CodeFormer) kako bi se postigla HD rezolucija i izbeglo zamućenje predela oko usana na 1080p/4K videima.
3. **[ZAVRŠENO] Interaktivni Studio Editor (v2):** Izgradnja interaktivnog timeline editora koji podržava waveforms, realtime delta modifikacije, hot-patching splicing i pametno AI Lektor skraćivanje prevoda. *Naredni korak:* Vizuelno pomeranje i rastezanje/skraćivanje govornih blokova direktno na zvučnom talasu pomoću drag-and-drop-a (`wavesurfer.js`).
4. **Pametan Prevodilac - Korisnički Rečnik (Glossary):** Mogućnost unosa prilagođenih rečnika direktno na frontendu koji se šalju sistemskom promptu Qwen Lektora kako bi se osigurao konzistentan prevod specifičnih tehničkih termina.

---

**Sinhronizuj.me** — *Jer tehnologija treba da priča tvojim jezikom.* 🇷🇸
