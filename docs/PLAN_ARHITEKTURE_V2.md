# Sinhronizuj.me — Plan Arhitekture V2 (Hibridni Cloud)

Ovaj dokument definiše tehničke specifikacije, infrastrukturu i optimizacije za finalnu produkcionu arhitekturu sistema. Oslanja se na razdvajanje kontrolne logike (Hetzner VPS) i teške GPU obrade (RunPod Serverless).

*Poslednje ažuriranje: 24. April 2026.*

---

## 1. Control Plane (Hetzner VPS)

Služi kao "mozak" operacije. Upravlja bazom, web zahtevima, skladištem fajlova i orkestracijom zadataka.

- **Model Servera:** Hetzner CPX32
- **Specifikacije:** 4 vCPU (AMD), 8 GB RAM, 160 GB NVMe SSD, 20 TB protoka
- **IP Adresa:** `178.104.214.78`
- **Servisi (Docker Compose):**
  - **Redis** (port 6379) — Message broker za Celery
  - **MinIO** (port 9000) — S3-kompatibilno skladište za video fajlove
  - **PostgreSQL** — Baza podataka (priprema za produkciju)

### Ključne Optimizacije na Control Plane-u

1. **MinIO SSD Zaštita:** Pošto je 160GB SSD ograničen za sirove 1080p fajlove, implementiran je strogi `Cron-Job` na nivou Celery-ja. Svake noći u 03:00h skripta briše sve fajlove starije od 24h iz MinIO kofa.
2. **FFMPEG Muxing bez GPU-a:** FFMPEG komande za spajanje striktno koriste `-c:v copy` parametar. Time se preskače re-renderovanje slike i rasterećuju 4 vCPU jezgra.
3. **Red Čekanja (Queue) za CPU:** Celery red za finalno spajanje (Muxing) je ograničen na maksimalno 2 konkurentna procesa. Ostali čekaju, čime se sprečava obaranje servera.
4. **Presigned URL Upload:** Korisnik uploaduje fajlove direktno u MinIO putem Presigned URL-ova koje generiše backend. Fajl ne prolazi kroz backend, čime se eliminiše bottleneck.

---

## 2. Compute Plane (RunPod Serverless GPU)

Grafičke kartice se više ne rentiraju na mesečnom nivou, već se bude na REST API poziv i plaćaju po sekundi.

### Aktivni Endpointi

| Endpoint | ID | GPU | Namena |
|---|---|---|---|
| Whisper (Transkripcija) | `3wqmtjpb3z2z18` | RTX 3090 / RTX 4000 Ada (24GB) | Prepoznavanje govora |
| Qwen (Prevod + Vizuelni Kontekst) | `ehsr5yiypxz4ap` | RTX A6000 (48GB) | Kontekstualni prevod sa video frejmovima |
| Fish Speech (TTS) | `9zx2al4sof2ian` | RTX 3090 / 4090 (24GB) | Sinteza srpskog glasa |

### Serverless Autoskaliranje

- **Concurrency:** vLLM podržava *Continuous Batching*. 1 GPU može asinhrono da obradi npr. 10 zadataka istovremeno.
- **Scale-up:** Kada dođe 11-ti zahtev, RunPod automatski budi sledeću grafičku.
- **Idle Timeout:** Radnik se gasi tek nakon `300 sekundi` (5 min) neaktivnosti, da bi dočekao eventualne nadovezane zadatke "vruć".
- **Min/Max Workers:** `Min: 0` (noću nema troškova) / `Max: 5` (zaštita od neograničenih troškova).
- **UX Upozorenje:** Ako je sistem na `0` radnika, UI obaveštava korisnika o "Cold Start-u" (buđenju) i mogućem čekanju od 2-3 minuta.

---

## 3. Workflow (Faze Obrade)

```
[Korisnik] → Upload (Presigned URL) → [MinIO S3]
                                            ↓
[Celery Worker] ← Redis ← [FastAPI Backend]
     ↓
Faza 1: Preuzimanje sa S3 (ili yt-dlp za YouTube)
     ↓
Faza 2: Demucs separacija vokala (lokalno)
     ↓
Faza 3: RunPod Whisper → Transkripcija
     ↓
Faza 4: Ekstrakcija frejmova + RunPod Qwen → TOON prevod
     ↓
Faza 5: RunPod Fish Speech → Sinteza glasa
     ↓
Faza 6: FFmpeg → Finalni mix (copy mode)
     ↓
Faza 7: Wav2Lip lip sync (opciono, preskače se za videa bez lica)
     ↓
[Gotov video] → Korisnik
```

---

## 4. Specijalne Inženjerske Optimizacije

### A. Kompresija Vizuelnog Konteksta (Pre-processing)

- **Problem:** Slanje 2GB videa preko REST API-ja guši mrežu i izaziva *Out of Memory* na A6000 kartici.
- **Rešenje:** Backend na Hetzneru (preko FFMPEG) unapred ekstrahuje 1 frejm na svakih 3-5 sekundi, lepi ih u minijaturni video klip od par Megabajta (bez zvuka) i šalje **taj** klip na RunPod preko MinIO Presigned URL-a. Zadržava se 100% potrebnog konteksta, a štedi gigabajte prenosa.

### B. Minimizacija LLM Prompt-a (TOON Format)

- **Problem:** JSON fajl iz Whisper-a obiluje zagradama, navodnicima i ključevima, trošeći bespotrebno hiljade tokena u LLM Context Window-u.
- **Rešenje:** Usvojen je **TOON (Token-Oriented Object Notation)** format. Backend prevodi JSON u tabelarni niz (`[start, end, text] \n 1.2,3.5,Hello`). Ovo smanjuje LLM prompt za čak 40%, pojeftinjuje poziv i oslobađa VRAM za video analizu.

### C. Paralelna Obrada Dugih Videa (Chunking)

- **Problem:** Prevođenje transkripta od 2 sata ide linearno, rečenicu po rečenicu.
- **Rešenje:** Backend na Hetzneru deli TOON fajl na manje blokove (npr. po 100 rečenica). Zatim ispaljuje asinhrone REST pozive ka vLLM-u za sve komade *istovremeno*. Vreme prevođenja pada sa više minuta na 15-tak sekundi.

### D. Bulletproof Parsiranje (Fallback mehanizam)

- **Problem:** U retkim slučajevima LLM halucinira i prekrši TOON formatiranje.
- **Rešenje:** Implementirana je Retry logika. Ako Regex pukne prilikom čitanja TOON-a, oštećeni *Chunk* se automatski šalje nazad vLLM-u uz striktni "Correction Prompt".

---

## 5. Trenutni Status Projekta

### ✅ Implementirano
- Kompletna 7-fazna pipeline logika (tasks.py)
- Direktan upload lokalnih fajlova u MinIO S3
- Demucs separacija vokala (lokalno, iz venv-a)
- React Studio interfejs sa real-time progresom
- TOON format parser (json_to_toon / toon_to_json)
- Vizuelni kontekst ekstrakcija (preprocessor.py)
- MinIO konfiguracija na Hetzner VPS-u

### 🔴 U Toku (Debugging)
- **RunPod 401 autentifikacija iz Celery worker-a:** API ključ radi iz standalone skripte ali ne iz Celery forked procesa. Istraga u toku.

### 🟡 Planirano
- CORS konfiguracija na MinIO (za direktan browser PUT)
- Produkcioni deploy frontenda
- Cron job za čišćenje starih fajlova iz MinIO-a

---

*Kreirano: 24. April 2026. — Sinhronizuj.me Development Team*
