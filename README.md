# 🎙️ Sinhronizuj.me

### AI Video Sinhronizacija na Srpski Jezik — Hibridna Arhitektura (VPS + Modal.com)

**Sinhronizuj.me** je napredni "end-to-end" sistem za automatsku video sinhronizaciju (dubbing) na srpski jezik sa kloniranjem originalnog glasa. Koristeći hibridnu cloud arhitekturu, sistem kombinuje stabilnost i pristupačnost **Control Plane-a** na Hetzner VPS-u sa serverless GPU snagom na **Modal.com** platformi za izvršavanje zahtevnih AI modela na zahtev.

---

## 🚀 Ključne Karakteristike

*   **Hibridna Cloud Arhitektura**: Kontrolna logika, baza podataka, asinhroni Celery radnik i S3 kompatibilno skladište nalaze se na Hetzner VPS-u, dok se teške AI operacije (separacija zvuka, STT, prevod, lektura, kloniranje glasa i Wav2Lip LipSync) izvršavaju serverless na **Modal.com** (T4, L4, A10G i A100 GPU-ovi) uz model plaćanja po utrošku (scale-to-zero).
*   **Modularni Frontend (DAW Studio)**: Korisnički interfejs je kompletno refaktorisan u modularne komponente. Sadrži:
    *   `StudioTimeline`: Interaktivni prikaz vremenske linije sa waveform-om originalnog zvuka.
    *   `SegmentEditor`: Uređivanje prevoda, izbor glasa i kontrola brzine, jačine i visine tona po segmentu.
    *   `AudioMixer`: Slajderi integrisani u plejer za kontrolu nivoa jačine originala i sinhronizovanog glasa u realnom vremenu.
    *   `DashboardView`: Brz pregled projekata i upload videa sa pre-vizuelizacijom.
    *   `LandingPage`: Uvodna prezentaciona stranica za neprijavljene korisnike.
*   **Undo/Redo Mehanizam**: Ugrađen u `StudioContext.jsx` sa istorijskim stekom dubine do 50 koraka, omogućavajući klijentu lako poništavanje grešaka tokom editovanja u DAW-u.
*   **Mobilna Responzivnost**: Aplikacija je optimizovana za mobilne uređaje uklanjanjem fiksne `100vh` visine (kroz klase `.studio-mode-active` i `.studio-mode-inactive`), preslaganjem kontrola u 2x2 mrežu i kompaktnim statusnim ikonama.
*   **AI Lektor na klik (Magic Shorten)**: Integrisana opcija čarobnog štapića šalje zahtev Modal Qwen Lektoru da inteligentno skrati srpski prevod na optimalnu dužinu kako bi se uklopio u originalno trajanje videa.
*   **Kloniranje Glasa i Audio Poboljšanje**: **Piper TTS** (srpski model Marko) generiše bazni govor, a **OpenVoice v2** vrši prenos boje glasa iz originalnog audio snimka (Speaker Embedding izvučen iz čistog originalnog audia). CFM model (Resemble Enhance) dodatno otklanja šum i podiže frekvenciju na 44.1kHz.
*   **Dinamičko Uklapanje vremena (`merger.py`)**: Ukoliko je izgenerisani srpski govor duži od originalnog segmenta, sistem automatski primenjuje ubrzavanje (`speedup_audio_file` preko FFmpeg-a) kako bi sprečio kolizije sa sledećim segmentima i desinhronizaciju videa.
*   **Kompletan Admin Panel**: Administratorski interfejs sa praćenjem waitlist-a (zatvorene bete), upravljanjem korisnicima (dodeljivanje admin privilegija), zbirnom statistikom i live pretragom logova Celery radnika za svaki pojedinačni projekat.
*   **Bezbednost i Kvote**: Implementirane su bezbednosne provere i limiti na nivou API-ja za veličinu pojedinačnog fajla, dnevni upload u MB i ukupno dnevno trajanje obrade videa po korisniku.


---

## 🌐 Arhitektura i Infrastruktura

Mermaid dijagram ispod prikazuje protok podataka i povezanost komponenti unutar sinhronizuj.me sistema:

```mermaid
flowchart TD
    subgraph Klijent ["Klijentski Sloj"]
        Browser["Korisnički Browser (React/Vite)"]
    end

    subgraph CF ["Mrežna Zaštita"]
        Cloudflare["Cloudflare Proxy (DNS / SSL / DDoS)"]
    end

    subgraph HetznerVPS ["Hetzner VPS - Docker Compose Okruženje"]
        NginxProxy["Nginx SSL Reverse Proxy"]
        Frontend["sinhronizuj-frontend (Nginx Port 3000)"]
        API["sinhronizuj-api (FastAPI Port 8000)"]
        Celery["sinhronizuj-celery (Celery Worker)"]
        Redis["sinhronizuj-redis (Message Broker - AOF perzistentan)"]
        Postgres[(PostgreSQL Baza)]
        S3[(S3 Skladište - MinIO/R2/Hetzner)]
        DockerDaemon["Docker Engine (Upravljanje Slikama)"]
    end

    subgraph ModalCloud ["Modal.com Serverless GPU AI"]
        Demucs["Demucs Worker (Separacija - T4 GPU)"]
        STT["Faster-Whisper Worker (Primarni STT - T4 GPU)"]
        SenseVoice["SenseVoice Worker (Sekundarni ASR - T4 GPU)"]
        Translator["Translator Worker (Qwen2-VL - A10G GPU)"]
        Lektor["Lektor Worker (Qwen Lektor - A10G GPU)"]
        TTS["TTS OpenVoice Worker (Piper+OpenVoice - L4 GPU)"]
        Wav2Lip["Wav2Lip Worker (LipSync - T4 GPU)"]
    end

    subgraph GitHubFlow ["CI/CD Pipeline"]
        GHActions["GitHub Actions Runner"]
        GHCR["GitHub Container Registry (GHCR)"]
    end

    %% Klijentske veze
    Browser --> Cloudflare
    Cloudflare --> NginxProxy
    NginxProxy --> Frontend
    NginxProxy --> API

    %% API veze
    API --> Postgres
    API --> S3
    Browser --> S3
    API --> Redis
    Redis --> Celery

    %% Celery radnik i Modal/Lokalne veze
    Celery --> Demucs
    Celery --> STT
    Celery --> SenseVoice
    Celery --> Translator
    Celery --> Lektor
    Celery --> TTS
    Celery --> Wav2Lip

    Demucs -.-> Celery
    STT -.-> Celery
    SenseVoice -.-> Celery
    Translator -.-> Celery
    Lektor -.-> Celery
    TTS -.-> Celery
    Wav2Lip -.-> Celery

    Celery --> S3
    Celery --> Postgres

    %% CI/CD Tok
    GHActions --> GHCR
    GHCR --> DockerDaemon
    DockerDaemon --> Frontend
    DockerDaemon --> API
```

---

## 🛠️ Tehnološki Stack

| Sloj | Tehnologije i Modeli |
| :--- | :--- |
| **Frontend** | React (Vite), Vanilla CSS (Premium Glassmorphism), HTML5 Audio API |
| **Control Plane (VPS)** | FastAPI (API server), Celery (Asinhroni radnik), Redis (Message Broker sa AOF perzistencijom), PostgreSQL (Baza), S3 kompatibilno skladište (MinIO, Cloudflare R2 ili Hetzner S3) |
| **Compute Plane (Modal)** | **Demucs v4** (Separacija vokala), **Faster-Whisper** (Primarni STT), **SenseVoice Small** (Sekundarni ASR), **Qwen2-VL-7B** (Prevod), **Qwen Lektor** (Lektura), **Piper TTS (Marko) & OpenVoice v2** (Sinteza/Kloniranje), **Wav2Lip** (LipSync vizuelna sinhronizacija) |


---

## 📦 Struktura Projekta

```
sinhronizuj.me/
├── .github/workflows/       # CI/CD Workflows (GitHub Actions)
│   ├── backend-ci.yml       # Linter provera koda (Ruff) i bezbednosno skeniranje (Bandit SAST)
│   ├── frontend-ci.yml      # Pokretanje vitest-a i Playwright-a pri push-u
│   └── deploy.yml           # CD na Hetzner VPS (Staging / Production)
├── backend/
│   ├── main.py              # FastAPI server (API gateway orkestrator i lifespan inicijalizacija)
│   ├── alembic/             # Alembic konfiguracija i migracione skripte
│   ├── core/
│   │   ├── config.py        # Centralna konfiguracija (limiti, kvote, S3 provajderi)
│   │   ├── database.py      # SQLAlchemy povezivanje baze
│   │   ├── auth.py          # JWT autentifikacija i blocklist validacija
│   │   ├── limiter.py       # SlowAPI limiter stopa
│   │   └── models.py        # SQLAlchemy modeli (User, Project, Segment, Glossary, Waitlist, Job)
│   ├── routes/              # Modularni FastAPI APIRouter-i
│   │   ├── auth.py          # Rute za registraciju, login, me i logout
│   │   ├── projects.py      # Rute za projekte, upload url i analizu (process-video)
│   │   ├── segments.py      # Rute za editovanje, preview, shorten i renderovanje
│   │   ├── admin.py         # Rute za statistike, waitlist i upravljanje korisnicima
│   │   └── system.py        # Rute za hardver, warmup i status poslova
│   ├── services/            # Pomoćni servisi
│   │   ├── redis.py         # Klijent za Redis
│   │   └── s3.py            # Klijent za S3 kompatibilno skladište
│   └── worker/
│       ├── tasks.py         # Celery taskovi (workspace izolacija, caching, analyze i render zadaci)
│       ├── downloader.py    # Preuzimanje videa sa S3 i SSRF zaštita
│       ├── numbers_to_words.py # Konverzija brojeva i procenata u ekavske reči na srpskom
│       ├── translation/     # Paket za EN->SR prevodilački i lektorski pipeline
│       │   ├── masking.py   # Maskiranje IT entiteta (Wi-Fi, GPS...)
│       │   ├── transliter.py # Transliteracija i rečničke zamene
│       │   ├── dialect.py   # Ekavizacija i morfološke popravke
│       │   ├── glossary.py  # Integracija glosara i analiza tema
│       │   ├── qe.py        # CometKiwi QE procena kvaliteta i gating
│       │   ├── translate.py # Prevođenje i self-critique petlja
│       │   └── lektor.py    # Lektura, deduplikacija i vremenska kompresija
│       ├── translator.py    # Fasada za translator/lektor servise
│       ├── tts_engine.py    # Priprema referentnog audia i OpenVoice integracija
│       └── merger.py        # FFmpeg/pydub audio miksovanje i dinamički speedup
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # React ruter i globalni raspored (Studio DAW)
│   │   ├── components/      # Modularne komponente (Dashboard, Studio, Admin, Auth, Common, Landing)
│   │   │   ├── Studio/      # StudioTimeline, SegmentEditor, AudioMixer
│   │   │   ├── Dashboard/   # DashboardView, ProjectList
│   │   │   ├── Admin/       # AdminPanel
│   │   │   ├── Landing/     # LandingPage.jsx
│   │   │   └── Common/      # Header, HardwareMonitor, Knob
│   │   ├── context/         # StudioContext.jsx (globalno stanje i undo/redo stek)
│   │   ├── services/        # api.js (klijentske API funkcije)
│   │   └── index.css        # Globalni CSS (Glassmorphism, custom scroll, responzivnost)
│   └── package.json         # Konfiguracija i skripte
├── modal_workers/           # Serverless radnici na Modal.com
│   ├── demucs_worker.py     # Demucs separacija vokala (T4 GPU)
│   ├── sensevoice_worker.py # SenseVoice STT transkripcija (T4 GPU)
│   ├── translator_worker.py # Qwen2-VL prevodilac (A10G GPU)
│   ├── tts_openvoice.py     # OpenVoice + Piper kloniranje (L4 GPU)
│   ├── lektor_worker.py     # Lektorisanje i skraćivanje teksta
│   └── wav2lip_worker.py    # Wav2Lip vizuelna sinhronizacija (T4 GPU)
├── docker-compose.yml       # Docker compose za lokalne servise (Postgres, Redis, API)
└── Dockerfile               # API/Worker Docker slika za server
```

---

## 🖥️ Pokretanje i Testiranje (Lokalno)

### 1. Podizanje Infrastrukture (Docker)
U korenskom direktorijumu pokrenite Postgres i Redis servise:
```bash
docker compose up -d
```

### 2. Pokretanje i Migracija Bekenda
Aktivirajte virtuelno okruženje, primenite Alembic migracije i pokrenite FastAPI server:
```bash
# Aktiviranje venv-a
source venv/bin/activate

# Primena najnovije migracije na Postgres
cd backend
alembic upgrade head
cd ..

# Pokretanje FastAPI API Gateway-a
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Pokretanje Celery Radnika
Pokrenite Celery proces koji osluškuje Redis red poslova:
```bash
celery -A backend.worker.celery_app worker --loglevel=info --concurrency=1
```

### 4. Pokretanje Frontenda
Uđite u frontend folder, instalirajte pakete i pokrenite Vite server:
```bash
cd frontend
npm install
npm run dev
```

### 5. Pokretanje Testova
Sistem poseduje automatizovane testove na frontendu za komponente i E2E provere:
*   **Frontend testovi** (Vitest unit testovi i Playwright E2E):
    ```bash
    cd frontend
    npm run test:run     # Pokretanje Vitest unit testova komponenata
    npx playwright test  # Pokretanje Playwright E2E testova
    ```

---

## ⚙️ Konfiguracija (.env)

Kreirajte `.env` datoteku u korenu projekta sa sledećim varijablama:

```env
# Konfiguracija baze podataka (Docker/Postgres)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tvoja_db_lozinka
POSTGRES_DB=sinhronizuj_db
DATABASE_URL=postgresql://postgres:tvoja_db_lozinka@db:5432/sinhronizuj_db

# JWT parametri
JWT_SECRET=tvoj_jwt_secret_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Modal Serverless Endpoints
MODAL_STT_URL=https://tvoj-username--sm-stt-only-sttworker-task.modal.run
MODAL_SENSEVOICE_URL=https://tvoj-username--sm-sensevoice-stt-sensevoice-task.modal.run
MODAL_TRANSLATOR_URL=https://tvoj-username--sm-translator-serve.modal.run
MODAL_LEKTOR_URL=https://tvoj-username--sinhronizuj-lektor-serve.modal.run
MODAL_TTS_URL=https://tvoj-username--sm-tts-v110-workerv110-task.modal.run
MODAL_WAV2LIP_URL=https://tvoj-username--wav2lip-worker-render-task.modal.run

# Prekidači za audio kvalitet
DISABLE_OPENVOICE=False
DISABLE_ENHANCE=False

# Redis i Mrežni parametri
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=tvoja_redis_lozinka

# S3 Storage Konfiguracija (podržava minio, hetzner, r2, s3)
STORAGE_PROVIDER=minio
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=uploads
MINIO_PUBLIC_ENDPOINT=http://localhost:9000
MINIO_SECURE=False

# Eksterni S3 Parametri (koriste se ako je STORAGE_PROVIDER=hetzner, r2 ili s3)
S3_ENDPOINT=https://tvoj-s3-endpoint
S3_ACCESS_KEY=tvoj-s3-access-key
S3_SECRET_KEY=tvoj-s3-secret-key
S3_BUCKET=tvoj-s3-bucket
S3_PUBLIC_ENDPOINT=https://tvoj-public-s3-endpoint
S3_SECURE=True
S3_REGION=us-east-1

# Kvote i limiti po korisniku
MAX_SINGLE_FILE_SIZE_MB=250
MAX_DAILY_UPLOAD_MB=1000
MAX_DAILY_DURATION_SEC=3600
```

```

---

## 🗺️ Plan Daljeg Razvoja

1.  **Automatska Diarizacija (Multi-Voice Cloning)**: Integracija `PyAnnote.audio` modela na Modalu kako bi se u pozadini prepoznali pojedinačni govornici (intervjui/podkasti) i svaki segment se sintetizovao glasom koji odgovara tom govorniku.
2.  **HD Face Restoration za LipSync**: Propuštanje Wav2Lip izlaza kroz modele poput GFPGAN ili CodeFormer kako bi se eliminisala zamućenost lica oko predela usana i postigla HD rezolucija.
3.  **Drag-and-Drop Vremensko Rastezanje**: Unapređenje `StudioTimeline` komponente koja bi preko wavesurfer.js-a omogućila vizuelno povlačenje i rastezanje/skraćivanje blokova zvuka direktno na talasu.

---

**Sinhronizuj.me** — *Jer tehnologija treba da priča tvojim jezikom.* 🇷🇸
