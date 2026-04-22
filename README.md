# 🎙️ Daca Dub AI
### Inteligentna AI Sinhronizacija na Srpski Jezik

**Daca Dub AI** je napredni "end-to-end" sistem za automatizovanu video sinhronizaciju. Koristeći najmodernije modele veštačke inteligencije, sistem omogućava preuzimanje YouTube videa, izolaciju originalnog glasa, preciznu transkripciju, pametan prevod i sintezu govora koja zadržava boju glasa originalnog govornika.

---

## 🚀 Ključne Karakteristike
- **Voice Cloning (Kloniranje glasa):** Korišćenjem *Fish Speech 1.5* i restaurirane *Firefly GAN* arhitekture, postižemo 1:1 sličnost sa originalnim govornikom na srpskom jeziku.
- **Smart Translation:** Integracija sa *Qwen 2.5 14B* modelom omogućava prirodan prevod koji razume kontekst i tehničke termine.
- **Vocal Isolation:** *Demucs v4* odvaja glas od muzike, omogućavajući kristalno čistu podlogu za novu sinhronizaciju.
- **Lip Sync & Face Fix:** Opciona vizuelna sinhronizacija usana pomoću *Wav2Lip* i izoštravanje lica sa *GFPGAN*.
- **Premium UI:** Moderan i responzivan React frontend sa animacijama u realnom vremenu.

---

## 🛠️ Tehnološki Stack
- **Frontend:** React, Vite, Framer Motion, Lucide Icons.
- **Backend:** FastAPI, Celery (Task Queue), Redis (Message Broker).
- **Infrastruktura:** RunPod (Cloud GPU), SSH Tunneling, SOCKS5 Proxy podrška.
- **AI Pipeline:**
  - **Download:** `yt-dlp`
  - **Audio Sep:** `Demucs v4`
  - **STT:** `Faster-Whisper (Large-v3)`
  - **LLM:** `Qwen 2.5 14B` (Ollama)
  - **TTS:** `Fish Speech 1.5` + `Firefly GAN (Legacy Restoration)`
  - **Video:** `FFmpeg`, `OpenCV`, `Wav2Lip`

---

## 📦 Instalacija i Pokretanje

### 1. Serverska strana (RunPod/GPU)
Potrebno je instalirati zavisnosti i pokrenuti servise:
```bash
# Pokretanje svih servisa (API, Worker, Fish Speech)
./start_runpod.sh
```

### 2. Klijentska strana (Lokalno)
Uspostavite SSH tunel ka RunPodu:
```bash
ssh -L 8000:localhost:8000 -L 8080:localhost:8080 root@<IP_ADRESA> -p <PORT>
```

Pokrenite Frontend:
```bash
cd frontend
npm run dev
```

---

## 📐 Arhitektura Pipeline-a
1. **Faza 1:** Preuzimanje videa (ili korišćenje lokalnog `.mp4` za bypass).
2. **Faza 2:** Separacija vokala i pozadinske muzike.
3. **Faza 3:** Transkripcija originalnog govora sa tajminzima.
4. **Faza 4:** Kontekstualni prevod na srpski jezik.
5. **Faza 5:** Sinteza srpskog govora uz kloniranje glasa (Fish Speech).
6. **Faza 6:** Opcioni Lip Sync (samo za kadrove gde je detektovano lice).
7. **Faza 7:** Finalni miks zvuka i slike (Audio Ducking efekat).

---

## 📝 Autor i Istorija
Sistem je razvio **Igor Grujović** u sklopu **IG-systems**.
Razvojni proces i sve izmene su dokumentovane u `istorija_izrade.md`.
Projekat je optimizovan za rad na **NVIDIA GPU** sa minimum **12GB VRAM-a**.

**Daca Dub AI** - *Jer tehnologija treba da priča tvojim jezikom.*
