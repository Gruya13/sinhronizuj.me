# 🎙️ Sinhronizuj.me
### AI Video Sinhronizacija na Srpski Jezik — Hibridna Arhitektura (VPS + Modal.com)

**Sinhronizuj.me** je napredni "end-to-end" sistem za automatizovanu video sinhronizaciju (dubbing). Koristeći hibridnu cloud arhitekturu, sistem kombinuje stabilnost **Control Plane-a** na Hetzner VPS-u sa serverless GPU snagom na **Modal.com** platformi za izvršavanje zahtevnih AI modela.

---

## 🚀 Ključne Karakteristike

- **Hibridna Arhitektura:** Kontrolna logika, baza podataka, asinhroni Celery radnik i MinIO (S3) lokalno skladište nalaze se na Hetzner VPS-u, dok se teške AI operacije (Demucs, Whisper, SenseVoice, Qwen-VL prevod, Lektor, Piper/OpenVoice V2 TTS sa Resemble Enhance i Wav2Lip) izvršavaju serverless na **Modal.com** (T4, A10G, L4 GPU-ovi).
- **Dvofazni Asinhroni Pipeline:** Ceo proces je podeljen na **Fazu 1: Analizu** i **Fazu 2: Renderovanje**. Faza 1 vrši separaciju, transkripciju i inicijalni prevod koji se perzistira u Redis bazi kao nacrt (draft), dok Faza 2 vrši finalno sklapanje. Opcioni Wav2Lip je privremeno isključen radi stabilizacije modela.
- **Kompaktni DAW Studio Editor (Full-Screen):** Moderni React studio interfejs koji staje na jedan ekran (no-scroll viewport height), sprečavajući skrolovanje cele stranice. Sadrži interaktivnu vremensku liniju koja prikazuje waveform engleskog govora i srpskog TTS-a. Automatski detektuje predugačke segmente i kolizije (crveni okviri i premium tooltip na hover sa z-index popravkom).
- **Integrisani Audio Mikser u Plejeru:** Dva kompaktna horizontalna slajdera integrisana direktno u video plejer omogućavaju podešavanje jačine pozadinske muzike (bgVolume) i AI glasa (dubVolume) u realnom vremenu.
- **AI Lektor na klik (Čarobni štapić - Magic Shorten):** Integrisana ikonica čarobnog štapića koja na klik šalje zahtev Modal Qwen Lektoru da inteligentno skrati srpski prevod na optimalnu dužinu (`duration * 20` karaktera) kako bi stao u originalni vremenski prozor.
- **Fino podešavanje zvuka po segmentu:** Kružne DAW kontrole (Volume, Tempo, Pitch, Ducking) po segmentu, uz mogućnost globalne primene zvučnih parametara na sve segmente odjednom.
- **Kloniranje Glasa i Resemble Enhance (100% Offline):** Piper TTS generiše bazni srpski govor (sr_Marko_medium), a OpenVoice V2 vrši prenos boje glasa iz originalnog audia (Speaker Embedding izvučen iz čistog originalnog audia umesto oštećenog Demucs vokala). CFM model (Resemble Enhance) uklanja metalni šum (denoise) i diže kvalitet na 44.1kHz (enhance).
- **Brza proba glasa i Hot-Patching (Splicing):** Promene na pojedinačnim segmentima se sintetišu u letu i ulepljuju pomoću `pydub` sečenja/lepljenja bez čekanja na render celog videa, čuvajući ispravne presigned S3 URL potpise na klijentu.
- **Pametno spajanje referentnog glasa:** Automatsko sakupljanje i spajanje više govornih segmenata (8+ sekundi čistog govora) uz 100ms crossfade i 50ms fade-in/out u pydub-u radi eliminisanja pucketanja i dobijanja stabilnog Speaker Embedding-a.
- **Stabilno FFmpeg miksovanje (asplit popravka):** Audio mikser na backendu koristi `asplit` filter kako bi razdvojio vokalni signal pre slanja u kompresor i amix, sprečavajući FFmpeg bag dupliranja strimova koji je mešao engleski vokal u finalni srpski miks.
- **Paralelna ekstrakcija i izolacija zadataka:** Celery radnik paralelno u pozadinskoj niti vrši ekstrakciju frejmova radi uštede vremena. Svaki konkurentni zadatak dobija izolovani radni prostor (`temp_workspace/<task_id>`) koji se po završetku bezbedno briše.
- **Programski Regex Korektor (Post-processor):** Python regex post-processor automatski ispravlja LLM anomalije: vrši pravilnu deklinaciju skraćenice "Ej Aj" po padežima, zamenjuje reč "robotika" u jednini, obezbeđuje doslednu "ti-formu" obraćanja i ispravlja česte gramatičke LLM greške.
- **Ensemble ASR & LLM Arbitraža:** Paralelno prepoznavanje govora pomoću modela **Whisper-large-v3** (sa reč-po-reč tajminzima) i **SenseVoice-Small** na Modalu sa LLM arbitražom za automatsku ispravku grešaka.

---

## 🛠️ Tehnološki Stack

| Sloj | Tehnologije |
|---|---|
| **Frontend**| React (Vite), Framer Motion, Vanilla CSS (Premium Glassmorphism), Lucide Icons, Wavesurfer.js |
| **Control Plane (VPS)** | FastAPI (API server), Celery (Asinhroni radnik), Redis (Message Broker / Cache), PostgreSQL (Baza), MinIO (S3 Object Storage) |
| **Compute Plane (Modal)**| Demucs (T4 GPU), Whisper-large-v3 & SenseVoice-Small (T4 GPU), Qwen2-VL-7B (vLLM server na A10G GPU), Qwen3-32B-AWQ (Lektor - vLLM server na A10G/A100 GPU), Piper & OpenVoice V2 sa Resemble Enhance (TTS/Kloniranje - L4 GPU), Wav2Lip (LipSync - A10G GPU, opciono) |

### AI Pipeline (Faze Obrade)

#### Faza 1: Asinhrona Analiza (`analyze_video_task`)
1. **Preuzimanje:** Preuzimanje videa (yt-dlp) i kreiranje izolovanog radnog prostora.
2. **Separacija (Demucs):** Izolacija vokala od pozadinske muzike na Modalu.
3. **Transkripcija:** Prepoznavanje pomoću Whisper-a i SenseVoice-Small na Modalu sa LLM arbitražom i pre-procesiranjem zvuka. Pozadinska nit istovremeno vrši ekstrakciju frejmova.
4. **Prevod & Lektura:** Multimodalni prevod (Qwen2-VL) uz vizuelni kontekst, nakon čega sledi Lektor (Qwen3) sa sistemskim glosarom i Regex post-procesorom. Rezultat se snima u Redis nacrt (draft).

#### Interaktivna Studio Faza (Korisnički rad u realnom vremenu)
- Korisnik otvara fiksni Full-Screen interfejs, bira audio izvore, ručno koriguje tekst (Magic Shorten), rotira tonske kontrole (Knobs) i preko "hot-patchinga" preslušava probni glas. "Očisti Redis" dugme omogućava brz reset.

#### Faza 2: Finalno Renderovanje (`render_video_task`)
1. **Sinteza (TTS):** Batch generisanje srpskih glasova (Piper Marko + OpenVoice V2 + Resemble Enhance CFM).
2. **Zvučni procesor:** Primena FFmpeg rubberband-a i filter lanca (reverb, compressor, eq) sa `asplit` popravkom.
3. **Dinamičko Rastezanje & Spajanje:** Rastezanje videa i muzike shodno trajanju srpskog govora (do 1.05x) i spajanje u finalni video.
4. **LipSync (Opciono):** Pozivanje Wav2Lip modela za sinhronizaciju pokreta usana i eksport gotovog MP4 na MinIO.

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
celery -A backend.worker.tasks worker --loglevel=info --concurrency=1
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

# Prekidači za audio kvalitet
DISABLE_OPENVOICE=False
DISABLE_ENHANCE=False

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
│   ├── main.py              # FastAPI server, presigned URL logika, Redis flush endpoint
│   ├── core/
│   │   ├── config.py        # Centralna konfiguracija (DISABLE_OPENVOICE, DISABLE_ENHANCE)
│   │   └── models.py        # SQLAlchemy modeli (User, Project, Segment, Glossary)
│   └── worker/
│       ├── tasks.py         # Celery taskovi (workspace izolacija, paralelna ekstrakcija frejmova)
│       ├── downloader.py    # Preuzimanje videa (yt-dlp/S3)
│       ├── translator.py    # Pozivanje Modal Translator i Lektor API-ja sa Regex post-processorom
│       ├── tts_engine.py    # Priprema referentnog audia (fade, crossfade) i Piper length_scale proračun
│       └── merger.py        # FFmpeg filteri (AEcho, Compand), Rubber Band i asplit vokalno miksovanje
├── frontend/
│   └── src/
│       ├── App.jsx          # React Studio korisnički interfejs (Kompaktan DAW, Redis kanta, plejer slajderi)
│       └── index.css        # Premium Glassmorphism stilovi i lock scroll-a
├── modal_workers/           # Serverless radnici na Modal.com
│   ├── demucs_worker.py     # Demucs radnik na Modalu (separacija vokala - T4 GPU)
│   ├── stt_worker.py        # Whisper & SenseVoice STT radnik (T4 GPU)
│   ├── translator_worker.py # Multimodalni Translator radnik (Qwen2-VL - A10G GPU)
│   ├── lektor_worker.py     # Jezički lektor radnik (Qwen3-32B - A10G GPU)
│   └── tts_openvoice.py     # Piper + OpenVoice V2 + Resemble Enhance tts generator (L4 GPU)
├── doc/                     # Zvanična tehnička dokumentacija projekta (Uvod, backend, frontend, infra...)
├── sicret doc/              # Tajna tehnička dokumentacija (nije na GitHub-u)
├── docker-compose.yml       # Docker compose za lokalne servise (Postgres, Redis, MinIO)
├── Dockerfile               # API/Worker Docker slika za Hetzner VPS
├── requirements.txt         # Python biblioteke
```

---

## 🗺️ Plan Daljeg Razvoja

U narednim fazama razvoja planirane su sledeće strateške stavke iz brainstorm planova:
1. **Prepoznavanje Govornika (Diarization) & Multi-Voice Cloning:** Integracija `PyAnnote.audio` modela na Modalu za automatsko označavanje i isecanje referentnih audio isečaka za svakog govornika u videu, te slanje na individualnu sintezu glasa (idealno za intervjue i podcaste).
2. **HD Face Restoration za LipSync:** Propuštanje Wav2Lip izlaza kroz modele za restauraciju i izoštravanje lica (GFPGAN ili CodeFormer) kako bi se postigla HD rezolucija i izbeglo zamućenje predela oko usana na 1080p/4K videima.
3. **[ZAVRŠENO] Interaktivni Studio Editor (v2):** Izgradnja interaktivnog timeline editora koji podržava waveforms, realtime delta modifikacije, hot-patching splicing i pametno AI Lektor skraćivanje prevoda. *Naredni korak:* Vizuelno pomeranje i rastezanje/skraćivanje govornih blokova direktno na zvučnom talasu pomoću drag-and-drop-a (`wavesurfer.js`).
4. **[ZAVRŠENO] Pametan Prevodilac - Korisnički Rečnik (Glossary):** Mogućnost unosa prilagođenih rečnika i glosara u bazu podataka koji se primenjuju tokom prevođenja i lekture kako bi se osigurao konzistentan prevod specifičnih tehničkih termina.

---

**Sinhronizuj.me** — *Jer tehnologija treba da priča tvojim jezikom.* 🇷🇸
