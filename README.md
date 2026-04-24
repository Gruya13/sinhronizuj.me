# 🎙️ Sinhronizuj.me AI
### Hibridna AI Sinhronizacija na Srpski Jezik (V2)

**Sinhronizuj.me AI** je napredni "end-to-end" sistem za automatizovanu video sinhronizaciju. Koristeći modernu hibridnu arhitekturu, sistem kombinuje stabilnost **Hetzner Control Plane-a** sa sirovom snagom **RunPod Serverless GPU** radnika.

---

## 🚀 Ključne Karakteristike
- **Hybrid Architecture:** Kontrolna logika i storage na Hetzner VPS-u, teška obrada (Whisper, Qwen, TTS) na RunPod Serverless GPU-ovima.
- **TOON Format:** Token-Oriented Object Notation omogućava ultra-brzu komunikaciju sa LLM-om i uštedu tokena do 40%.
- **Multimodalni Kontekst:** Sistem ekstrahuje vizuelne frejmove videa (sprite-sheets) koje AI model "gleda" radi preciznijeg prevoda.
- **Voice Cloning:** Korišćenjem *Fish Speech 1.5*, postižemo 1:1 sličnost sa originalnim govornikom.
- **Studio Interface:** Moderni React frontend sa uporednim prikazom originala i prevoda u realnom vremenu.

---

## 🛠️ Tehnološki Stack
- **Frontend:** React (Vite), Framer Motion, Lucide Icons.
- **Control Plane:** FastAPI, Celery, Redis, PostgreSQL, MinIO (S3 Storage) - Hostovano na Hetzner VPS-u.
- **Compute Plane:** RunPod Serverless (RTX 3090/4090/A6000).
- **AI Pipeline:**
  - **Download:** `yt-dlp`
  - **Vocal Separation:** `Demucs v4`
  - **Transcription:** `Faster-Whisper` (RunPod Serverless)
  - **Translation:** `Qwen 32B/35B` via vLLM (TOON Format)
  - **TTS:** `Fish Speech 1.5` (RunPod Serverless)
  - **Video:** `FFmpeg` (Stream Copy optimization)

---

## 📦 Pokretanje

### 1. Backend (Hetzner)
Sistem se pokreće putem Docker Compose-a na VPS-u:
```bash
cd infra/hetzner
docker compose up -d
```

### 2. Frontend (Lokalno/VPS)
```bash
cd frontend
npm run dev
```

---

## 📐 Faze Obrade
1. **Faza 1 (Download):** Preuzimanje i inicijalna provera.
2. **Faza 2 (Preprocessing):** Separacija vokala i ekstrakcija vizuelnog konteksta.
3. **Faza 3 (Transcription):** RunPod Whisper prepoznaje govor.
4. **Faza 4 (Translation):** Qwen analizira tekst i sliku, generiše TOON prevod.
5. **Faza 5 (Synthesis):** Paralelna sinteza glasa na RunPodu.
6. **Faza 6 (Mix):** Finalno spajanje slike i zvuka (ffmpeg copy mode).

---

## 📝 Dokumentacija
- `istorija_izrade.md`: Hronološki dnevnik svih izmena.
- `PLAN_ARHITEKTURE_V2.md`: Detaljan opis hibridnog sistema.

**Sinhronizuj.me AI** - *Jer tehnologija treba da priča tvojim jezikom.*
