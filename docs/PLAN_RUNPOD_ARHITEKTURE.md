# 🚀 Plan Implementacije: Custom RunPod Serverless Arhitektura

Ovaj dokument predstavlja detaljan, tehnički plan za prelazak sa predefinisanih RunPod šablona na visoko-optimizovane "Custom Docker" kontejnere za GPU obradu, koristeći postojeći (Monorepo) `sinhronizuj.me` repozitorijum.

## 🎯 Glavni Ciljevi
1. **Drastično smanjenje veličine kontejnera:** Održavanje kontejnera ispod 3GB radi brzog podizanja i poštovanja besplatnih GitHub/Docker kvota.
2. **Eliminacija Timeout-a u CI/CD-u:** Prestanak bespotrebnog kompajliranja C++ i CUDA biblioteka (`flash-attn`) na GitHub Actions serverima.
3. **Ubrzanje "Cold Start" ciklusa:** Eksternalizacija modela (Qwen 3.6, Whisper, Fish Speech) na RunPod Network Volume.
4. **Smanjenje troškova protoka (Bandwidth):** Lokalna priprema `.mp4` videa na Hetzneru pre slanja na RunPod.

---

## 📁 1. Nova Struktura Repozitorijuma

Zadržavamo **Monorepo** pristup. Dodaćemo novi direktorijum `runpod_workers` u koren projekta.

```text
sinhronizuj.me/
├── backend/            # Hetzner API
├── frontend/           # React App
├── docs/               # Dokumentacija
└── runpod_workers/     # 🚀 NOVI DIREKTORIJUM
    ├── stt_llm/        # Radnik A (Whisper + Qwen)
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   └── handler.py  
    └── tts/            # Radnik B (Fish Speech)
        ├── Dockerfile
        ├── requirements.txt
        └── handler.py  
```

---

## 🧠 2. Faza 1: Radnik A (Transkripcija + Prevod)

Ovaj kontejner integriše `faster-whisper` za govor-u-tekst i `vLLM` za pokretanje multimodalnog Qwen 3.6 modela.

### Tehnike Optimizacije:
- **Multi-Stage Build:** `Dockerfile` će imati dva sloja. Prvi ("Builder") sloj skida `cu121` točkove (wheels) za PyTorch i vLLM. Drugi ("Runtime") sloj preuzima samo kompajlirane fajlove, ostavljajući stotine megabajta keša u smeću.
- **Lazy Loading Modela:** U `handler.py` skripti pišemo funkciju koja pri pokretanju (boot) proverava `/runpod-volume/models`. Ukoliko `Qwen/Qwen2-VL-7B-Instruct-AWQ` ili `faster-whisper-large-v3` nedostaju, skripta ih automatski povlači sa Hugging Face-a pre pokretanja FastAPI/RunPod servera.

---

## 🗣️ 3. Faza 2: Radnik B (Voice Cloning & TTS)

Ovaj kontejner je izolovan kako bi se sprečio konflikt CUDA verzija i održao minimalan kapacitet. Pokreće isključivo *Fish Speech* model.

### Tehnike Optimizacije:
- **Bypass za `flash-attn`:** Biblioteka `flash-attention` se neće kompajlirati u kontejneru (što inače traje ~40 minuta i ruši GitHub Actions). Umesto toga, `Dockerfile` će preuzeti i instalirati specifičan `pre-compiled wheel` direktno iz zvaničnih GitHub izdanja prilagođenih za PyTorch 2.4.0 + CUDA 12.1.
- **Model Storage:** Svi Fish Speech checkpoint-i će se nalaziti na Network Volume-u.

---

## 🚧 4. Faza 3: Uklanjanje Uskih Grla (Bottlenecks)

### A. Pre-procesuiranje na Hetzneru (Bandwidth ušteda)
Trenutno Hetzner preuzima sirovi video (često teži od 1GB). Slanje celog fajla na RunPod je gubljenje vremena.
*   **Akcija:** Izmeniti Celery radnik na Hetzneru da pomoću FFmpeg-a lokalno izvuče **isključivo** čist audio u `.wav` formatu (15MB) i **10 ključnih frejmova** u `.jpg` formatu (2MB). Na RunPod se šalje samo paket od ~17MB, smanjujući vreme slanja za 98%.

### B. Mmap za Brzi "Cold Start"
*   **Akcija:** Modeli smešteni na RunPod Network Volume moraju biti isključivo u `.safetensors` formatu. Ovo omogućava hardveru "Memory Mapping", tj. mapiranje modela direktno sa mrežnog drajva u VRAM bez punog prolaska kroz radnu memoriju procesora.

### C. Continuous Batching na RunPod-u
*   **Akcija:** Na RunPod web panelu obavezno postaviti **"Concurrency"** vrednost na `10+`. Ovo sprečava RunPod da naplaćuje paljenje nove A6000 grafičke kartice za svaki nov zahtev, jer `vLLM` može komotno obraditi 10 uporednih zahteva na jednom GPU-u usled naprednog deljenja memorije.

---

## 🤖 5. Faza 4: CI/CD Pipeline (GitHub Actions)

Umesto Docker Hub-a (gde postoje limitacije za free naloge), prelazimo na **GitHub Container Registry (`ghcr.io`)**.

### GitHub Actions Workflow (`.github/workflows/runpod-builder.yml`):
- **Path Filtering:** Workflow će se trigerovati **samo** ako neko izvrši commit u folderu `runpod_workers/`. Izmene frontenda i API-ja ga neće pokretati.
- **Caching:** Koristićemo `docker/setup-buildx-action` (type=gha) koji kešira svaki sloj Dockera između build-ova. Sledeći build traje 30 sekundi umesto 15 minuta.
- **Automatski Push:** Nakon uspelog build-a, skripta sama vrši tagovanje i gura gotove kontejnere direktno na `ghcr.io`, koje RunPod zatim lako povlači na klik.

---

## 🗓️ Predlog Redosleda Izvršenja
1. Kreiranje direktorijuma `runpod_workers` i postavljanje arhitekture (Handler + Dockerfile).
2. Podešavanje CI/CD pipeline-a za testni build.
3. Refaktorizacija Hetzner Celery radnika da šalje lokalno ekstrakte (.wav i frejmove) umesto čitavih videa.
4. Preusmeravanje API ključeva i gašenje starih monolitskih instanci na RunPod-u.
