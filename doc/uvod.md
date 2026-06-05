# 🎙️ Sinhronizuj.me — Uvod i Visokonivojska Arhitektura

Dobrodošli u zvaničnu tehničku dokumentaciju za **Sinhronizuj.me** — naprednu cloud platformu za automatsku video i audio sinhronizaciju (dubbing) video zapisa sa engleskog na srpski jezik.

Svrha ovog sistema je da omogući korisnicima da unesu engleski video zapis (ili YouTube link) i dobiju visoko-kvalitetan sinhronizovani video na srpskom jeziku, gde je:
1. Glas govornika kloniran (boja i ton glasa odgovaraju originalnom govorniku).
2. Tekst preveden, lekturisan, ekavizovan i prilagođen srpskom govornom području uz poštovanje glosara.
3. Brzina govora automatski i dinamički prilagođena dužini trajanja originalnih segmenata (kroz Piper length_scale) kako bi se sprečila preklapanja i očuvao prirodan ritam.
4. Pokret usana govornika se može sinhronizovati sa novim srpskim zvukom (LipSync - opciono/privremeno isključeno u standardnom renderu radi stabilizacije modela).

---

## 🗺️ Hibridna Cloud Arhitektura

Sistem je dizajniran na principu razdvajanja upravljačkog (Control) i računarskog (Compute) sloja, što omogućava maksimalnu ekonomičnost i skalabilnost:

```
                  ┌──────────────────────────────────────────┐
                  │          React Frontend SPA              │
                  │   (Studio DAW, Vremenska linija, Knobs)  │
                  └────────────────────┬─────────────────────┘
                                       │ HTTP / WebSockets
                                       ▼
                  ┌──────────────────────────────────────────┐
                  │        Hetzner VPS (Control Plane)       │
                  │                                          │
                  │  ┌───────────────┐      ┌─────────────┐  │
                  │  │ FastAPI Server│◄────►│ PostgreSQL  │  │
                  │  └───────┬───────┘      └─────────────┘  │
                  │          │               ┌─────────────┐  │
                  │          ├──────────────►│  Redis Cache│  │
                  │          │               └─────────────┘  │
                  │          ▼               ┌─────────────┐  │
                  │  ┌───────────────┐      │  MinIO S3   │  │
                  │  │ Celery Worker │◄────►│  Storage    │  │
                  │  └───────┬───────┘      └─────────────┘  │
                  └──────────┼───────────────────────────────┘
                             │ gRPC / REST API pozivi (Base64 payloads)
                             ▼
                  ┌──────────────────────────────────────────┐
                  │        Modal.com (Compute Plane)         │
                  │       (Serverless GPU-ovi, Scale-to-Zero)│
                  │                                          │
                  │  ┌───────────────┐      ┌─────────────┐  │
                  │  │  Demucs (T4)  │      │  STT (T4)   │  │
                  │  └───────────────┘      └─────────────┘  │
                  │  ┌───────────────┐      ┌─────────────┐  │
                  │  │Qwen2-VL(A10G) │      │Qwen3-AWQ(A1)│  │
                  │  └───────────────┘      └─────────────┘  │
                  │  ┌───────────────┐      ┌─────────────┐  │
                  │  │  TTS (L4)     │      │Wav2Lip(A10G)│  │
                  │  └───────────────┘      └─────────────┘  │
                  └──────────────────────────────────────────┘
```

### 1. Control Plane (Hetzner VPS - Docker Compose)
Upravljački sloj hostuje sve stateful servise, orkestraciju i web aplikaciju. Nalazi se na Hetzner VPS instanci i pokreće se kroz Docker Compose:
- **React Frontend**: Korisnički interfejs koji pruža bogato vizuelno iskustvo studija sa vremenskom linijom i DAW kontrolama.
- **FastAPI API Server**: Izlaže REST API za autentifikaciju, upravljanje projektima, brisanje i hot-patching.
- **PostgreSQL**: Čuva relacione podatke (korisnike, projekte, segmente sa parametrima, glosare).
- **Redis**: Broker za Celery i keš za nacrte (drafts) projekata i rate limiting.
- **MinIO**: Privatno S3 kompatibilno skladište podataka za audio, video i TTS segmente.
- **Celery Worker**: Lokalni asinhroni procesor koji vrši koordinaciju celog pipeline-a, preuzimanje videa, preprocesiranje preko FFmpeg-a i pozivanje Modal GPU servisa.

### 2. Compute Plane (Modal.com)
Računarski sloj koristi serverless GPU resurse na platformi Modal.com. Kontejneri se podižu po potrebi (cold start) i gase nakon perioda neaktivnosti (scale-to-zero), čime se troškovi svode na čisto vreme izvršavanja mašinskih modela:
- **Demucs Worker (NVIDIA T4)**: Odvajanje vokala od pozadinske muzike.
- **Speech-To-Text STT (NVIDIA T4)**: Transkripcija engleskog jezika preko Whisper-large-v3 modela i SenseVoice-Small modela za detekciju emocija i tačne interpunkcije.
- **Translator Worker (NVIDIA A10G)**: Multimodalni prevod pomoću Qwen2-VL-7B koji pored teksta prima i ključne frejm-ove videa radi boljeg konteksta i prepoznavanja roda govornika.
- **Lektor Worker (NVIDIA A10G / A100-40GB)**: Napredna lektura, ekavizacija i provera kroz glosar korišćenjem Qwen3-32B-AWQ modela na A10G/A100 GPU.
- **TTS & Voice Cloning (NVIDIA L4)**: Sinteza srpskog jezika preko Piper modela, kloniranje glasa korišćenjem OpenVoice V2 i dramatično poboljšanje kvaliteta zvuka preko Resemble Enhance modela.
- **Wav2Lip (NVIDIA A10G)**: Generisanje pokreta usana u skladu sa srpskim audiom (trenutno u razvoju/opciono).

---

## 🔄 Životni Ciklus Projekta (Pipeline Tok)

1. **Inicijalizacija i Analiza (Faza 1)**: Korisnik unosi URL ili otprema video. FastAPI registruje projekat i pokreće Celery task. Video se preuzima, vokal se izoluje (Demucs), vrši se STT transkripcija, multimodalno prevođenje sa prepoznavanjem frejmova (Qwen2-VL) i lektura sa glosarom (Qwen3). Rezultujući nacrt se snima u bazu podataka i Redis. Ekstrakcija frejmova se odvija u paralelnoj niti radi uštede vremena.
2. **Korisnički Studio (DAW)**: Korisnik na vremenskoj liniji pregleda segmente, ispravlja prevod, menja parametre (jačina, brzina, visina tona) i koristi "hot-patching" preview koji u roku od 150ms sintetiše i lepi izmenjeni audio segment.
3. **Renderovanje i Spajanje (Faza 2)**: Korisnik pokreće render. Celery radnik poziva TTS engine za sve preostale segmente (Piper/OpenVoice V2 + Resemble Enhance), primenjuje FFmpeg audio filtere (reverb, kompresor, ekvilajzer), po potrebi vrši blago rastezanje trajanja videa i pozadinske muzike (Dynamic Video Stretching), spaja audio trake i generiše finalni video koji se otprema na MinIO.
