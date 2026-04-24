# Sinhronizuj.me - Plan Arhitekture V2 (Hibridni Cloud)

Ovaj dokument definiše tehničke specifikacije, infrastrukturu i optimizacije za finalnu produkcionu arhitekturu sistema. Oslanja se na razdvajanje kontrolne logike (Hetzner VPS) i teške GPU obrade (RunPod Serverless).

---

## 1. Control Plane (Hetzner VPS)

Služi kao "mozak" operacije. Upravlja bazom, web zahtevima, preuzimanjem videa i orkestracijom.
*   **Model Servera:** Hetzner CPX32
*   **Specifikacije:** 4 vCPU (AMD), 8 GB RAM, 160 GB NVMe SSD, 20 TB protoka.
*   **Servisi:** Node.js/Python (FastAPI) Backend, PostgreSQL, Redis, Celery (Worker), MinIO (Storage).

**Ključne Optimizacije i Pravila na Control Plane-u:**
1.  **MinIO SSD Zaštita:** Pošto je 160GB SSD prilično malo za sirove 1080p fajlove, implementiran je strogi `Cron-Job` na nivou Celery-ja. Svake noći u 03:00h skripta briše sve fajlove (uključujući i oštećene/zombi fajlove) starije od 24h iz MinIO kofa.
2.  **FFMPEG Muxing bez GPU-a:** FFMPEG komande koje spajaju sinhronizovani audio i originalni video striktno koriste `-c:v copy` parametar. Time se preskače re-renderovanje slike i rasterećuju 4 vCPU jezgra.
3.  **Red Čekanja (Queue) za CPU:** Kako FFMPEG ipak opterećuje procesor zbog audija, Celery red za finalno spajanje (Muxing) je ograničen na maksimalno 2 konkurentna procesa. Ostali čekaju, čime se sprečava obaranje web servera.

---

## 2. Compute Plane (RunPod Serverless GPU)

Grafičke kartice se više ne rentiraju na mesečnom nivou, već se bude na REST API poziv i plaćaju po sekundi.

*   **Endpoint 1: Transkripcija (Whisper)**
    *   **GPU:** RTX 3090 ili RTX 4000 Ada (24GB VRAM) - Brzo i povoljno.
*   **Endpoint 2: Prevod i Vizuelni Kontekst (Qwen 3.6 Multimodal 32B/35B)**
    *   **GPU:** RTX A6000 (48GB VRAM). Zbog 32B parametara model se obavezno kvantizuje (AWQ/GPTQ 4-bit ili 8-bit) na ~20GB. Preostalih ~28GB služi za masivni Video Context Window.
*   **Endpoint 3: TTS Sinteza (Fish Speech)**
    *   **GPU:** RTX 3090 ili RTX 4090 (24GB VRAM).

**Serverless Autoskaliranje (Endpoint Konfiguracija):**
*   **Concurrency:** vLLM podržava *Continuous Batching*. 1 Grafička može asinhrono da radi npr. 10 zadataka istovremeno.
*   **Scale-up:** Kada dođe 11-ti zahtev, RunPod automatski budi sledeću grafičku.
*   **Idle Timeout:** Radnik se gasi tek nakon `300 sekundi` (5 min) neaktivnosti, da bi dočekao eventualne nadovezane zadatke "vruć".
*   **Min/Max Workers:** `Min: 0` (noću nema troškova) / `Max: 5` (zaštita od neograničenih troškova).
*   **UX Upozorenje:** Ako je sistem na `0` radnika, UI obaveštava korisnika o "Cold Start-u" (bđenju) i mogućem čekanju od 2-3 minuta.

---

## 3. Workflow i Specijalne Inženjerske Optimizacije

Sledeće optimizacije drastično rešavaju probleme curenja memorije, sporosti i mrežnog zagušenja:

### A. Kompresija Vizuelnog Konteksta (Pre-processing)
Model mora da "vidi" video kako bi rešio probleme prevoda (rodovi, dvosmislenosti, situacioni idiomatski prevodi).
*   **Problem:** Slanje 2GB videa preko REST API-ja guši mrežu i izaziva *Out of Memory* na A6000 kartici. LLM inače interno odbacuje 95% frejmova i gleda po 1 sliku na par sekundi.
*   **Rešenje:** Backend na Hetzneru (preko FFMPEG) unapred ekstrahuje 1 frejm na svakih 3-5 sekundi, lepi ih u minijaturni video klip od par Megabajta (bez zvuka) i šalje **taj** klip na RunPod preko MinIO Presigned URL-a. Zadržava se 100% potrebnog konteksta, a štedi gigabajte prenosa.

### B. Minimizacija LLM Prompt-a (TOON Format umesto JSON-a)
*   **Problem:** JSON fajl iz Whisper-a obiluje zagradama, navodnicima i ključevima (`start`, `end`, `text`), trošeći bespotrebno hiljade tokena u LLM *Context Window-u*.
*   **Rešenje:** Usvojen je **TOON (Token-Oriented Object Notation)** format. Backend prevodi JSON u tabelarni niz (`[start, end, text] \n 1.2,3.5,Hello`). Ovo smanjuje LLM prompt za čak 40%, pojeftinjuje poziv i oslobađa VRAM za video analizu. Backend ga po završetku lako parsira nazad u liste.

### C. Paralelna Obrada Dugih Videa (Chunking)
*   **Problem:** Prevođenje transkripta od 2 sata na vLLM-u ide linearno, rečenicu po rečenicu, što traje.
*   **Rešenje:** Backend na Hetzneru deli TOON fajl na manje blokove (npr. po 100 rečenica). Zatim ispaljuje asinhrone REST pozive ka vLLM-u za sve komade *istovremeno*. vLLM (zahvaljujući Concurrency parametru) i RunPod (zahvaljujući automatskom podizanju više grafičkih) ih prevode paralelno. Vreme prevođenja pada sa više minuta na 15-tak sekundi.

### D. Bulletproof Parsiranje (Fallback mehanizam)
*   **Problem:** U retkim slučajevima LLM halucinira i prekrši TOON formatiranje.
*   **Rešenje:** Implementirana je Retry logika. Ako Hetzner `Regex` pukne prilikom čitanja TOON-a, ne obustavlja se ceo video. Oštećeni *Chunk* (komad) se automatski šalje nazad vLLM-u uz striktni "Correction Prompt" da ispravi sintaksu.

---
*Kreirano: 24. April 2026. (Sinhronizuj.me Development)*
