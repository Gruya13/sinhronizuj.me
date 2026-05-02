# Plan Migracije Arhitekture: Prelazak sa RunPod-a na Modal.com

## 1. Analiza trenutnog stanja i problema (RunPod)
Trenutna hibridna arhitektura se oslanja na **Hetzner VPS** (Control Plane) i **RunPod Serverless** (Compute Plane) za AI zadatke (Faster-Whisper, Qwen vLLM, Fish Speech). 
**Ključni problemi sa RunPod-om:**
- **Nedostatak GPU resursa:** Cesto se javljaju "No available GPUs" greške, što blokira automatsko procesiranje videa.
- **Teško održavanje Docker slika:** Multi-stage Docker build proces u GitHub Actions pipeline-u je kompleksan, podložan "timeout-ima" (posebno zbog kompajliranja `flash-attn` paketa) i često probija besplatne Action kvote.
- **Cold Start sporost:** Iako ublažena Network Volume drajvom, pokretanje hladnih instanci na RunPodu za teške AI modele može biti vrlo sporo.

## 2. Ciljevi i prednosti Modal.com arhitekture
- **Garantovana GPU dostupnost i Skalabilnost:** Modal agregira kapacitete sa više cloud provajdera i rešava probleme nedostatka resursa automatski.
- **"Infrastructure-as-Code" (Zaboravljamo Dockerfiles):** Modal definiše kompletno okruženje i imidže unutar samog Python koda koristeći method chaining (npr. `modal.Image.debian_slim().pip_install(...)`). Odbacujemo GH Actions Docker buildove u potpunosti.
- **Ultra-brz Cold Start:** Pomoću naprednog izolovanog keširanja i `Memory Snapshots` funkcija, teški modeli se učitavaju višestruko brže.
- **Integracija Storage-a:** Modal Volumes (`modal.Volume`) omogućava lako i sigurno keširanje Hugging Face modela direktno na cloud instancama.

## 3. Dizajn Nove Arhitekture (Modal Compute Plane)

Celokupan `runpod_workers` folder biće zamenjen jednim novim sistemom `modal_workers/` koji će se deploy-ovati direktno sa Hetzner-a komandom `modal deploy`.

### A. STT & LLM (Whisper + vLLM Qwen 27B) Radnik
- **Modal Aplikacija:** Zaseban `modal.App` sa funkcijom rutiranom na `@app.function()`.
- **GPU Dodela:** Eksplicitno se traži 1x `A100` ili `H100` uz pomoć parametra `gpu="A100"`.
- **Environment:**
  - Base Image: `modal.Image.debian_slim(python_version="3.11")`
  - Paketi: `vllm`, `faster-whisper`, instalacija `flash-attn` preko unapred kompajliranog wheel fajla (direktno kroz `pip_install`).
- **Ponašanje:** Kao i ranije, obrađivaće asinhrono zahteve za transkripciju i prevod sa podrškom za vizuelni kontekst videa.

### B. TTS (Fish Speech 1.5) Radnik
- **Modal Aplikacija:** Drugi endpoint dizajniran isključivo za generisanje glasa.
- **GPU Dodela:** Zbog manje potrošnje VRAM-a, dovoljno je definisati jeftinije grafike: `gpu="A10G"` ili `gpu="L4"`.
- **Ponašanje:** Prihvataće S3 presigned URL-ove za referentni `vocals.wav` i generisaće sinhronizovani dub koji vraća nazad na MinIO ili direktno kao Base64 stream.

## 4. Strategija Keširanja i Preuzimanja Modela (Volume Cache)
Da bismo eliminisali bilo kakvo preuzimanje težina modela (model weights) u run-time okruženju, kreiraćemo **Modal Volume** (npr. `sinhronizuj-models-vol`).
- Prilikom izgradnje image-a, definisaćemo poseban korak `Image.run_function()` koji će unapred pozvati `huggingface_hub` i preuzeti `Qwen3.6-27B-AWQ`, `faster-whisper` i `fish-speech` modele i sačuvati ih u taj volume.
- Svi budući Modal kontejneri će pri "Cold Start-u" jednostavno mount-ovati ovaj volume direktno i čitati težine instantno.

## 5. Koraci Implementacije (Faze Migracije)

**Faza 1: Čišćenje repozitorijuma i priprema baze**
1. Brisanje `runpod_workers/` celokupnog foldera (opciono, premeštanje u `/archive` dok se ne uverimo da Modal radi).
2. Brisanje `.github/workflows/runpod-builder.yml` jer nam Docker registar više nije potreban.
3. Kreiranje Modal Accounta i generisanje tokena za autentifikaciju. Pokretanje `modal setup` na Hetzner serveru.

**Faza 2: Razvoj Modal Backend Servisa (modal_workers)**
1. Pisanje `modal_workers/stt_llm.py` koji implementira STT/LLM endpoint koristeći FastAPI klase za webhooke (npr. `@app.function` + `@modal.web_endpoint`).
2. Pisanje `modal_workers/tts.py` na sličan način.
3. Kreiranje Python build skripte za download HF modela u `modal.Volume`.

**Faza 3: Prilagođavanje Celery Radnika (Hetzner)**
1. `backend/worker/utils.py` - Uklanjanje koda specijalizovanog za RunPod (polling mehanizam).
2. Učenje postojećih Celery zadataka (`transcriber.py`, `translator.py`, `tts_engine.py`) da šalju regularne HTTP POST zahteve prema novim stalnim Modal Web Endpoint URL-ovima (npr. `https://gruya--sinhronizuj-me-stt.modal.run`). 
3. Ovi endpointi će, za razliku od RunPod asinhronih job-ova, možda zadržavati konekciju otvorenom, ili ćemo implementirati `modal.Function.spawn()` za asinhrono čekanje kako ne bismo opteretili Hetzner radnike držanjem otvorenih HTTP socket-a 3 minuta.

**Faza 4: Testiranje i Skaliranje**
1. Testiranje end-to-end video pipeline-a kako bismo osigurali performanse preklapanja prevoda (lipsync/TTS).
2. Podešavanje `concurrency_limit` atributa na Modal funkcijama radi optimizacije troškova.

## 6. Zaključak
Prelazak na Modal.com će efektivno ukloniti najkrhkiji deo trenutne arhitekture - Docker Hub i RunPod dostupnost. Postajemo čisti **Python-Native projekat** gde se GPU resursi kodiraju u istoj aplikaciji, a "Control Plane" na Hetzneru ostaje isključivo za laku organizaciju Celery poslova i frontend UI zahetva.
