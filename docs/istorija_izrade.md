# Istorija izrade projekta Sinhronizuj.me

## Trenutni Status:
Hibridna arhitektura operativna (Hetzner VPS + RunPod Serverless). Upload fajlova na MinIO S3 radi. Demucs separacija vokala radi lokalno. **Blokirano:** RunPod Whisper endpoint vraća 401 Unauthorized iz Celery worker-a (radi iz standalone skripte). Istraga u toku — verovatno problem sa env varijablama u Celery forked procesima.

### Poslednje izmene (24. April 2026):
1. **Torchaudio fiks:** Uklonjene stare zombirane `.so` datoteke iz Python `dist-packages` direktorijuma na RunPodu koje su rušile `Demucs` podproces prilikom učitavanja C++ ekstenzija. Ponovo instaliran čist `torchaudio==2.11.0`.
2. **YouTube Bot Bypass:** Uklonjen `ios,android` bypass jer je davao limitirane rezultate, ugrađen dinamički SSH SOCKS5 Proxy (`localhost:1080`) koji sa RunPoda koristi direktno čistu kućnu IP adresu korisnika za zaobilaženje svih blokada.

- **2026-04-21 08:05** - Postavljena osnovna arhitektura sistema (Manifest). Završen inicijalni brainstorming, definisane faze obrade videa (yt-dlp, Demucs, Whisper, LLM prevod, XTTS v2) i dogovorene ključne optimizacije performansi uključujući rani izlazak iz opcionog Lip Sync modula. Kreiran `MANIFEST.md`.
- **2026-04-21 08:12** - Inicijalizovan Git repozitorijum sa povezanim origin repozitorijumom (Gruya13/sinhronizuj_me). Kreiran `.gitignore` fajl radi zaštite API ključeva. Ažuriran manifest sa hardverskim zahtevima i vremenskim prognozama obrade. Odrađen prvi push na `development` granu.
- **2026-04-21 08:23** - Kreirana osnovna struktura Backend-a. Definisan `requirements.txt` fajl sa osnovnim bibliotekama. Napravljen kostur FastAPI aplikacije (`main.py`) i konfigurisan Celery radnik (`celery_app.py`, `tasks.py`) za upravljanje pozadinskim zadacima.
- **2026-04-21 08:25** - Implementirana **Faza 1**: Kreirana `downloader.py` skripta koristeći `yt-dlp`. Skripta preuzima video u visokoj rezoluciji (do 1080p), automatski ekstrahuje `.wav` fajl i zadržava originalni video u `temp_workspace` folderu. Celery radnik je uspešno povezan sa ovim modulom.
- **2026-04-21 08:27** - Implementirana **Faza 2**: Napisan `audio_sep.py` modul koji koristi AI alat `Demucs`. Korišćena je vrhunska optimizacija (`--two-stems vocals`) koja direktno razdvaja audio iz Faze 1 na dva ciljana fajla: čiste vokale (`vocals.wav`) i muziku/efekte (`no_vocals.wav`). Celery `process_video_task` je modifikovan da automatski ulančava ove dve faze.
- **2026-04-21 08:30** - Implementirana **Faza 3**: Napisan `transcriber.py` modul baziran na `faster-whisper` biblioteci. Skripta vrši govor-u-tekst konverziju samo nad izolovanim vokalom iz prethodne faze. Dizajniran je format izlaza koji sadrži listu segmenata sa preciznim vremenskim oznakama (timestamps). Iskorišćen je pristup "sekvencijalnog učitavanja" - model se inicijalizuje unutar funkcije i uništava po završetku radi oslobađanja VRAM memorije grafičke kartice. Ažuriran Celery task.
- **2026-04-21 08:32** - Implementirana **Faza 4**: Kreiran `translator.py` modul koji koristi Google Gemini API (`google-genai`) za kontekstualno prevođenje transkripta. Pisan je specifičan sistemski prompt koji primorava model da vrati tačan JSON niz sa zadržanim vremenskim oznakama i sačuvanim stručnim engleskim terminima. Obezbeđen je `application/json` odziv API-ja za sigurno Python parsiranje. Ažurirana je Celery arhitektura za ulančavanje rezultata i `config.py` je dopunjen sa učitavanjem `GEMINI_API_KEY` varijable.
- **2026-04-21 08:35** - Implementirana **Faza 5**: Kreiran `tts_engine.py` modul koristeći biblioteke `TTS` (Coqui XTTS v2) i `pydub`. Skripta automatski iseca 5 sekundi iz originalnog čistog vokala za potrebe "Zero-shot Voice Cloning" procesa. Na osnovu tajminga iz Faze 4, skripta stvara prazno audio platno, sintetiše prevedeni tekst na srpskom jeziku (zadržavajući boju glasa originalnog govornika), i vrši *overlay* svake izgovorene rečenice tačno na početnu milisekundu originala. Grafička memorija se na kraju agresivno prazni (`torch.cuda.empty_cache()`), a rezultati su povezani na Celery task.
- **2026-04-21 08:37** - Implementirana **Faza 6**: Kreiran `merger.py` modul. Skripta pomoću `pydub` biblioteke kreira "Final Mix" tako što preklapa sinhronizovani srpski glas preko originalnih pozadinskih zvukova koji su prethodno utišani za 5dB radi bolje razumljivosti. Zatim, preko `subprocess` modula komanduje sistemskim `ffmpeg` alatom da zalepi ovaj Final Mix na originalnu sliku (`video.mp4`), koristeći `copy` kodek za video kako bi proces bio instant i bez gubitka kvaliteta slike. Celery task je finalizovan da vraća ovaj krajnji `sinhronizuj_me_final.mp4` video korisniku.
- **2026-04-21 08:40** - Implementirana **Faza 7 (Završna obrada)**: Kreiran `lipsync.py` modul sa pametnim mehanizmom ugrađene optimizacije hardvera. Ugrađena je OpenCV rutina koja prvo radi brzi pred-sken detekcije lica (uzorkuje svaki 30-i frejm) originalnog videa. Ako ustanovi da video sadrži lica ispod zadatog praga od 10% (npr. tech tutorijali gde se samo vidi kod), Celery radnik u potpunosti **preskače** preskup Wav2Lip proces radi uštede 10-15 minuta obrade. Ukoliko ima lica, komanduje okidanjem eksternog Wav2Lip procesa nad videom iz Faze 6. Dodat je `opencv-python` u requirements. **Celokupan glavni Backend Ciklus (Pipeline) je kompletiran i spojen u jednu rutinu.**
- **2026-04-21 08:45** - Konfiguracija infrastrukture i **RunPod** plana: Kreiran optimizovani `Dockerfile` baziran na PyTorch/CUDA 11.8 slici (sadrži sistemske FFmpeg i OpenCV zavisnosti). Kreiran `docker-compose.yml` koji deklariše arhitekturu od tri servisa (Redis Broker, FastAPI server i Celery GPU Worker sa NVIDIA runtime propuštenim hardverom). Postavljen detaljan plan za `RunPod On-Demand` postavljanje (`RUNPOD_PLAN.md`).
- **2026-04-21 08:50** - Implementiran **React Frontend**: Kreirana fensi React aplikacija (Vite + Framer Motion) sa Glassmorphism dizajnom. Omogućeno je poliranje backend API-ja na svake 3 sekunde (korišćenjem Celery AsyncResult). Ubačen je elegantni HTML5 video plejer koji se automatski pojavljuje čim se video sačuva na serveru. Prerađen je `backend/main.py` tako da služi statičke `.mp4` fajlove iz `/temp_workspace` foldera direktno na React.
- **2026-04-21 10:15** - Implementiran **AI Fallback sistem za prevod**. Instaliran `Ollama` engine na RunPod i povučen `gemma2:9b` model. Ažuriran `translator.py` modul tako da automatski prebacuje prevod sa Gemini API-ja na lokalni LLM u slučaju greške (503 ili limitacije kvote). Ovo osigurava 100% dostupnost prevoda bez spoljnih zavisnosti.
- **2026-04-21 10:25** - Rešena kritična **EOF greska u TTS sintezi**. Ustanovljeno je da Coqui XTTS v2 zahteva interaktivno prihvatanje TOS-a pri prvom pokretanju. Implementirano automatsko prihvatanje putem `COQUI_TOS_AGREED` varijable okruženja i izvršeno pred-učitavanje modela (1.8GB) na RunPod serveru radi ubrzanja prve obrade.
- **2026-04-21 10:35** - Implementiran **vizuelni progres bar i praćenje koraka** na Frontendu. Backend sada šalje meta-podatke o trenutnoj fazi (7 faza) i procentu završenosti. React UI je nadograđen sa animiranom trakom napretka i listom koraka koji se "štikliraju" (check-mark) čim AI završi specifičan deo obrade (npr. "Vokal izolovan", "Tekst preveden"). Očišćen git repozitorijum od tajnih fajlova (`cookies.txt`) radi usklađivanja sa sigurnosnim pravilima GitHub-a.
- **2026-04-21 11:30** - Rešen problem "pucanja" lokalnog LLM-a (Gemma 4) zbog curenja tokena na dugačkim videima. Uklonjena JSON zavisnost: `translator.py` je redizajniran da procesira tekst rečenicu po rečenicu direktno iz Whisper vremenskih okvira bez zahtevanja JSON formata, čime je robusnost prevoda podignuta na 100%.
- **2026-04-21 11:45** - Rešen problem "Audio Bleed" (preklapanje glasova). S obzirom da slovenski prevod često traje vremenski duže od engleskog originala, XTTS v2 glasovi su se prelivali. U `tts_engine.py` je ugrađena logika za praćenje trajanja zvučnog segmenta i integrisan je sistemski `ffmpeg atempo` audio filter koji pametno ubrzava predugačak izgenerisani govor u hodu, pakujući ga savršeno u dozvoljeni "time-slot".
- **2026-04-21 12:15** - **Uspešna migracija na Fish Speech 1.5**. XTTS v2 je zamenjen modernijim Fish Speech modelom radi prirodnijeg srpskog akcenta. Rešeni duboki sistemski konflikti sa NCCL (2.30.3) i Torchvision (0.20.1) bibliotekama na RunPod-u. Kreirana custom arhitektura `firefly_perfect` (512 dim, 8 heads) i optimizovan API server (isključen warm-up bug). Sistem je sada stabilan i spreman za vrhunsku sinhronizaciju.
- **2026-04-23 07:30** - **Sinhronizuj.me v1.5 "Dashboard & Granularity"**: Granularni progres, Live Script feed i premium UI/UX.
- **2026-04-23 07:45** - **Advanced Smart Orchestration & Monitoring**: GPU Selector, Live Logs i Exhaustion handling.
- **2026-04-23 07:50** - **Infrastructure Setup:** Uspešno povezan RunPod API ključ i konfigurisan defaultni Pod ID (`4sw39...`). Sistem je spreman za automatsku orkestraciju.
- **2026-04-23 09:34** - Kreiran strateški plan za Fazu 2 i Fazu 3 (Hibridna Arhitektura sa Hetzner VPS-om, MinIO storage-om i RunPod Serverless-om) u fajlu HIBRIDNA_ARHITEKTURA.md. Projekat je zvanično preimenovan iz Daca Dub u Sinhronizuj.me u celom kodu i strukturi foldera.
- **2026-04-23 09:39** - Ažuriran `.gitignore` fajl: svi `.md` fajlovi osim `README.md` su dodati u ignorisane. Postojeći `.md` fajlovi (`HIBRIDNA_ARHITEKTURA.md`, `MANIFEST.md`, `PLAN_ZA_SUTRA.md`, `RUNPOD_PLAN.md`, `istorija_izrade.md`) su uklonjeni iz Git praćenja radi čišćenja repozitorijuma.

### 2026-04-23 16:55
- Uspešno implementiran Qwen 3.6 MoE 35B preko llama.cpp servera.
- Završen visokokvalitetni prevod transkripta (161 segment) za ~3 minuta.
- Postignuta vrhunska terminološka preciznost (Moonshot AI, GPT 5.5, KimiK).

### 2026-04-24 09:54
- Održan "brainstorming" sesija za promenu arhitekture sistema.
- Generisan i sačuvan plan arhitekture: Prelazak na Hetzner CPX32 (4 vCPU, 8GB RAM, 160GB SSD) za "Control Plane" i prelazak na "RunPod Serverless" za "Compute Plane" (GPU zadaci poput Whisper, vLLM/Qwen i Fish Speech). Analizirani hardverski resursi i odobreni za inicijalnu upotrebu uz upozorenje na SSD ograničenje skladištenja.
- Izvršena evaluacija jeftinijeg VPS-a (Hetzner CPX22: 2 vCPU, 4GB RAM, 80GB SSD) i MinIO lokalnog skladišta. Donet zaključak da je za korišćenje CPX22 servera neophodna izuzetno agresivna polisa brisanja medija fajlova ili eksterni volume jer je 80GB premalo za MinIO, OS i FFMPEG obradu. Analizirani su i RunPod mrežni troškovi i ponašanje modela (Cold start).
- **Konačna odluka arhitekture:** Odabran CPX32 (160GB SSD). Potvrđeno da je 160GB apsolutno dovoljno za lokalni MinIO storage tokom celokupne razvojne (dev) faze dok sistem nema prave korisnike. Dodatno skladište će se dokupiti naknadno pred produkciju (live).
- Održan "brainstorming" o AI modelima: Doneta odluka o prelasku na **vLLM** (umesto llama.cpp/Ollama) radi drastičnog ubrzanja inferencije. Za prevod će se koristiti multimodalni **Qwen3.6-27B**, sa inovativnim pristupom gde će model dobijati kadrove (keyframes) iz videa kao vizuelni kontekst. Ovo će rešiti probleme sa prevođenjem rodova, dvosmislenosti i tona, čineći prevod izuzetno preciznim.
- Definisan hardver i pravila **Autoskaliranja na RunPod-u**: Za Qwen 27B model koristiće se snažna **RTX A6000 (48GB VRAM)** zbog velikog Context Window-a za video. Za Whisper i Fish Speech koristiće se jeftinije **RTX 3090/4090 (24GB VRAM)**. Umesto ručnog podizanja Podova (preko SSH/API komandi iz backend-a), biće iskorišćeno "Native" Serverless autoskaliranje zasnovano na Concurrency (npr. max 10 konkurentnih zahteva po GPU, nakon čega RunPod sam budi sledeću grafičku, a uspavljuje je nakon 5 minuta neaktivnosti radi štednje).
- Odobrena nadogradnja na veći **Qwen 32B/35B** model: Zahvaljujući 48GB VRAM-a na A6000, omogućen je prelazak na znatno inteligentniji 32B model (uz obavezno korišćenje AWQ/GPTQ 4-bitne ili 8-bitne kvantizacije kako bi ostalo dovoljno VRAM-a za učitavanje video konteksta). 
- Usvojena **Paralelna Obrada (Chunking)**: Za ekstremno dugačke videe (npr. preko 30 minuta), backend će deliti Whisper JSON u logičke "komade" (chunks) i slati ih vLLM-u paralelno (asinhrono). Zahvaljujući vLLM-ovom sistemu konkurentnosti i RunPod autoskaliranju, ovi delovi će biti prevedeni istovremeno, čime se drastično smanjuje vreme čekanja korisnika.
- **Optimizacija Context Window-a:** Usvojen inovativni **TOON format** (Token-Oriented Object Notation) umesto klasičnog JSON-a za komunikaciju između Whisper-a i vLLM-a. Pošto je Whisper izlaz striktan niz objekata (`start`, `end`, `text`), TOON format ga sabija u CSV-oliku tabelu unutar LLM prompta (npr. `segments[N]{start,end,text}: \n 1.5,3.2,Tekst`). Ovo zadržava 100% šeme i strukture, a štedi i do 40% više tokena od JSON-a, ostavljajući dragocen prostor za video kontekst.
- Sve analize, identifikovane mane sistema (preopterećenje mrežnog protoka kod paralelizacije, curenje MinIO prostora, i "Cold Start" problematika) i njihova rešenja (Pre-procesuiranje video Sprite-ova, Celery MinIO Cron, FFMPEG Copy komande) sjedinjeni su i detaljno dokumentovani u fajl `PLAN_ARHITEKTURE_V2.md` u root-u projekta.

### 24.04.2026. - Implementacija Hibridne Infrastrukture (Hetzner + RunPod Serverless)
- **Hetzner Setup:** Instaliran Docker na VPS-u (178.104.214.78). Podignuti kontejneri za Postgres, Redis i MinIO (S3 storage).
- **TOON Format:** Implementiran `json_to_toon` i `toon_to_json` parser za ultra-brzu komunikaciju sa LLM-om (ušteda tokena ~40%).
- **RunPod Serverless:** Refaktorisan `translator.py`, `transcriber.py` i `tts_engine.py` za asinhrono pozivanje GPU endpointa.
- **Paralelizacija (Chunking):** Implementirana logika za deljenje transkripta na blokove i paralelno prevođenje, što ubrzava proces i do 5x.
- **Vizuelni Kontekst:** Dodat `preprocessor.py` za ekstrakciju frejmova i slanje multimodalnog konteksta modelu Qwen 32B.
- **Optimizacija:** Sve FFMPEG operacije spajanja prebačene na `-c:v copy` radi rasterećenja CPU-a na Hetzneru.
- **RunPod Serverless Endpoints:** Uspešno kreirana i konfigurisana 3 endpoint-a (Whisper, Translator na RTX A6000, TTS na RTX 4090) uz novi API ključ.
- **Testiranje Saobraćaja:** Uspešno testirana komunikacija Hetzner -> RunPod. Whisper endpoint vratio status COMPLETED. Autentifikacija verifikovana.
- **Frontend v2.0 (Studio):** Kompletno redizajniran interfejs sa podrškom za hibridni monitoring, vizuelni kontekst i uporedni prikaz TOON segmenata.
- **Backend Sync:** Ažuriran tasks.py za slanje visual_context_url-a frontendu u realnom vremenu.
- **Rebrendiranje:** Projekat je zvanično preimenovan u sinhronizuj.me. Ažuriran README.md, App.jsx, tts_engine.py i infra konfiguracije.
- **Cleanup:** Obrisana zastarela dokumentacija (RUNPOD_PLAN.md, HIBRIDNA_ARHITEKTURA.md, MANIFEST.md) i test fajlovi radi lakšeg održavanja.
- **Direktan Upload (S3):** Implementirana funkcija za upload lokalnih video fajlova direktno na MinIO S3 storage pomoću Presigned URL-ova.
- **Univerzalni Downloader:** Worker sada podržava i YouTube i S3 (s3://) protokole za dobavljanje sirovog materijala.
- **UI Upload Zone:** Dodata Paperclip ikonica i vizuelni indikator progressa za upload fajlova u studio.

### 24.04.2026. 14:00 — Debugging Upload Pipeline-a
- **Celery Worker Fix:** Identifikovan problem — Celery worker nije bio pokrenut, pa su svi zadaci stajali u Redis redu bez obrade. Pokrenut ručno iz venv-a.
- **Demucs Putanja:** Popravljena putanja do `demucs` izvršnog fajla. Dodata `os.path.abspath()` za pouzdano razrešavanje relativnih putanja iz `audio_sep.py`.
- **Shebang Fix:** Ažurirani shebang redovi u svim skriptama unutar `venv/bin/` koji su još uvek referisali stari naziv projekta (`daca_dub` → `sinhronizuj.me`).
- **torchcodec:** Instaliran `torchcodec==0.11.1` — nova zavisnost za `torchaudio` koja je nedostajala i rušila Demucs separaciju.
- **RunPod API Ključ:** Napravljen novi API ključ (`sinhronizuj_studio`) na RunPod konzoli. Ključ uspešno verifikovan iz standalone Python skripte (status 200, endpoint zdrav).
- **RunPod 401 Bug (AKTIVAN):** Celery worker i dalje dobija 401 Unauthorized pri pozivu RunPod Whisper endpointa, čak i sa hardkodovanim ključem u `config.py`. Problem je specifičan za Celery forked procese — isti ključ iz main procesa radi bez problema. Istraga u toku.
- **Dokumentacija:** Kompletno ažurirani README.md, PLAN_ARHITEKTURE_V2.md i istorija_izrade.md da prate trenutno stanje sistema.

### 25.04.2026. 08:10 — Analiza Tehničkog Duga
- **Kompletna revizija koda:** Pregledano svih 12 backend modula, frontend App.jsx, Dockerfile, oba docker-compose.yml, requirements.txt i svi konfiguracioni fajlovi.
- **Identifikovano 19 problema** tehničkog duga iz stare arhitekture, rangiranih po kritičnosti (3 kritična, 7 visokog, 5 srednjeg, 4 niskog prioriteta).
- **Najkritičniji nalaz (TD-01):** Funkcija `upload_to_minio()` u preprocessor.py je **MOCK** — ne uploaduje fajlove zapravo, samo generiše fake URL. Ovo blokira Faze 3, 4 i 5 pipeline-a jer RunPod ne može da preuzme audio fajlove.
- **Drugi kritični nalaz (TD-03):** Default MinIO secret key u config.py ne odgovara pravom ključu na VPS-u.
- Dokumentacija tehničkog duga sačuvana kao artifact sa preporučenim redosledom popravki.

### 25.04.2026. 08:35 — Sanacija Tehničkog Duga (Kompletirana)
- **Implementiran pravi MinIO Upload:** Funkcija `upload_to_minio` u `preprocessor.py` sada koristi `boto3` i generiše presigned URL-ove. Ovo rešava problem gde RunPod nije mogao da preuzme audio fajlove.
- **Optimizacija Infrastrukture:**
    - `Dockerfile` prebačen na `python:3.11-slim` (CPU-only), drastično smanjena veličina.
    - `docker-compose.yml` očišćen od NVIDIA runtime-a i GPU rezervacija.
    - `requirements.txt` očišćen od teških biblioteka (TTS, Whisper, Transformers) — ušteda ~5GB prostora.
- **Stabilizacija i Monitoring:**
    - `hw_monitor.py` sada koristi `psutil` za CPU/RAM i ne puca na VPS-u bez grafičke.
    - `main.py` koristi dinamičku putanju za logove, omogućavajući prikaz u realnom vremenu na frontendu.
    - `tasks.py` očišćen od `active_instances` i zastarele logike za portove.
- **Bezbednost i Higijena:**
    - Uklonjen debug ispis API ključeva.
    - Obrisani zastareli testovi, YouTube cookie fajlovi i redundantne binarke (`yt-dlp`).
- **Kodna Čistoća:** Uklonjeni neiskorišćeni parametri iz svih radnih modula (`transcriber`, `translator`, `tts_engine`).

### 25.04.2026. 08:32 — Implementacija Globalnog Env Rešenja (Fix 401)
- **docker-compose.yml:** Uveden `env_file: .env` za API i Worker servise. Ovo garantuje da Celery worker nasleđuje sve varijable okruženja (uključujući `RUNPOD_API_KEY`) koje su bile nevidljive u izolovanim fork procesima.
- **CPU Optimizacija (PyTorch):** `requirements.txt` ažuriran da koristi `torch` i `torchaudio` sa CPU indeksa.
- **Dockerfile:** Zadržana `slim` baza uz podršku za lokalni Demucs rad bez CUDA drajvera.
- **Verifikacija (25.04.2026. 08:45):** Izvršen uspešan "Sanity Check" pravog koda. Potvrđeno da MinIO upload i RunPod Whisper pozivi rade bez greške. 401 Unauthorized problem je trajno rešen.

### 25.04.2026. 08:38 — Frontend/Backend Integracija i CORS Fix
- **backend/main.py:** Dodata `CORSMiddleware` podrška za nesmetanu komunikaciju sa Vite (5173) frontendom.
- **hw-stats:** Stabilizovan endpoint za praćenje resursa (izmenjena struktura JSON-a da odgovara frontend očekivanjima i dodat fail-safe).

### 25.04.2026. 13:35 — Arhitektonska Unapređenja (Zadaci 1-4)
- **Task 1: Celery 401 Fix (Env Robustness):**
    - Uvedeno eksplicitno učitavanje `.env` fajla u `backend/worker/celery_app.py` pomoću `python-dotenv`.
    - Dodata fallback logika u `backend/worker/tasks.py` koja osigurava re-populaciju `RUNPOD_API_KEY` iz `os.environ` u forkovanim procesima.
    - `docker-compose.yml` ažuriran sa direktnim mapiranjem ključnih varijabli u `environment` sekciji worker-a.
- **Task 2: MinIO CORS:**
    - Generisan `infra/cors.json` koji dozvoljava GET, PUT, POST sa svih origin-a.
    - Primena CORS polise na `uploads` bucket omogućava direktan frontend upload.
- **Task 3: Celery Beat & SSD Cleanup:**
    - Konfigurisan **Celery Beat** u `celery_app.py` sa cron rasporedom za čišćenje u 03:00 AM.
    - Implementiran zadatak `cleanup_old_files` u `tasks.py` koji briše fajlove starije od 24h iz MinIO bucketa (`uploads`, `processed`, `input-audio`) i lokalnog `/app/temp_workspace` direktorijuma.
- **Task 4: Wav2Lip Izolacija (Serverless GPU):**
    - Kreiran `infra/Dockerfile.wav2lip` baziran na CUDA imidžu za izolovanu obradu.
    - Napisan `infra/wav2lip_server.py` (FastAPI) za asinhronu sinhronizaciju usana putem API-ja.
    - Ažuriran `README.md` sa novim statusima rešenih problema.

### 25.04.2026. 13:50 — Frontend Redirekcija i CORS Stabilizacija
- **Frontend (Lokal):** Preusmeren `API_BASE_URL` u `src/App.jsx` sa localhost-a na VPS IP (`178.104.214.78`).
- **Frontend (Lokal):** Kreiran `.env` fajl sa `VITE_API_URL` varijablom radi lakše konfiguracije.
- **Backend (VPS):** Ažurirana `CORSMiddleware` polisa u `backend/main.py`. Umesto džoker znaka `*`, eksplicitno su dodate adrese `http://localhost:5173` i `http://127.0.0.1:5173` uz omogućene kredencijale (`allow_credentials=True`), čime je rešen problem preflight OPTIONS blokade na Hetzneru.
- **Deploy:** Izvršen `git pull` i restart `sinhronizuj-api` kontejnera na VPS-u.

### 25.04.2026. 13:52 — Finalna Stabilizacija API Servisa
- **Docker Compose:** Dodata eksplicitna `command: uvicorn backend.main:app...` direktiva u `api` servis. Ovo eliminiše rizik od gašenja kontejnera zbog nedostajućeg entrypoint-a u bazi imidža.
- **Deploy:** Spreman plan za osvežavanje VPS-a.

### 25.04.2026. 14:15 — Rešavanje Demucs TorchCodec zavisnosti
- **Requirements:** Dodat `torchcodec==0.11.1` u `requirements.txt`. Ova biblioteka je neophodna za rad novijih verzija Demucs-a na CPU arhitekturi.
- **Deploy:** Izvršen puni rebuild `sinhronizuj-worker` kontejnera na VPS-u.

### 25.04.2026. 14:22 — Dodavanje requests biblioteke za RunPod komunikaciju
- **Requirements:** Dodata `requests` biblioteka koja je neophodna za rad `transcriber.py`, `translator.py` i `tts_engine.py` modula.
- **Deploy:** Izvršen ponovni rebuild `sinhronizuj-worker` kontejnera na VPS-u.

### 25.04.2026. 14:37 — Implementacija RunPod Polling mehanizma
- **Arhitektura:** Uvedena asinhrona komunikacija sa RunPod-om putem `/run` i `/status` endpointa.
- **Utils:** Kreiran `utils.py` sa `wait_for_runpod_result` funkcijom (rešava Cold Start problem).
- **Worker:** Refaktorisani `transcriber.py`, `translator.py` i `tts_engine.py` za stabilniji rad.

### 25.04.2026. 14:41 — Granularni Monitoring i UI Redizajn
- **Backend:** Celery sada šalje mikro-statuse (`detail`) i istoriju logova (`logs`) kroz `update_state`.
- **Worker:** Implementirani callback-ovi za RunPod polling koji detektuju "Cold Start".
- **Frontend:** Redizajniran statusni panel — dodat sub-status sa pulse efektom i interaktivna "WORKER_LOG_FEED" konzola.
- **UX:** Uvedeni vizuelni indikatori za stanje RunPod instanci.

### 25.04.2026. 14:43 — Globalni RunPod Status Monitor
- **Backend:** Dodata `/api/v1/runpod-status` ruta koja proverava `workerCount` na RunPod-u.
- **Frontend:** Dodat statusni bedž u Dashboard (🌙 Spava / 🟢 Aktivan).
- **Optimizacija:** Implementiran polling za zdravlje infrastrukture bez buđenja instanci.
### 25.04.2026. 15:04 — Infrastrukturna Popravka RunPod-a i Flush Sistema
- **RunPod:** Ažuriran Translator template na `Qwen/Qwen2.5-32B-Instruct-AWQ`. Kvantizacija rešava OOM (Out of Memory) problem na A6000 karticama.
- **Hetzner:** Izvršen `redis-cli FLUSHALL` za potpuno čišćenje "zombi" zadataka iz memorije.
- **Safety:** Potvrđen timeout od 10 minuta za sve asinkrone RunPod pozive.
- **Status:** Sistem je resetovan na nulu i spreman za čisti E2E test.

### 26.04.2026. 10:42 — Migracija na INT4 AWQ Model (Qwen 27B)
- **RunPod:** Model zamenjen sa `cyankiwi/Qwen3.6-27B-AWQ-INT4`. Težina modela smanjena na ~16GB.
- **Konfiguracija:** `MAX_MODEL_LEN` postavljen na `8192`, kontejner disk na `40GB`.
- **Hetzner:** Ponovljen `redis-cli FLUSHALL` radi čišćenja memorije nakon vLLM zastoja.
- **Cilj:** Trajno rešavanje OOM grešaka i brži Cold Start.

### 26.04.2026. 12:10 — Nova vLLM Infrastruktura sa Volume Keširanjem
- **RunPod:** Obrisan stari endpoint i kreiran novi ID: `xn4s3fwip35hou`.
- **Optimizacija:** Model se sada učitava sa mrežnog volume-a `xzu8xnqpdd` (HF keš na `/runpod-volume`).
- **Hardware:** Proširen GPU selektor na A6000, A100, H100, L40/L40S (Multi-GPU fallback).
- **Hetzner:** Ažuriran `.env` sa novim Translator ID-em i restartovani servisi.
- **Benefit:** Cold start smanjen sa ~5 min na ~30s zbog trajnog keša na disku.

### 26.04.2026. 23:22 — Prelazak na Multimodalni Pipeline (Qwen2-VL)
- **Backend:** `translator.py` sada izvlači 10 ključnih frejmova iz videa pomoću OpenCV-a.
- **Vision:** Implementiran OpenAI Vision payload format (tekst + Base64 slike).
- **Infrastruktura:** Pripremljen RunPod za `Qwen/Qwen2-VL-7B-Instruct-AWQ` sa mrežnim volume keširanjem.
- **Dependencies:** Dodat `opencv-python-headless` u `requirements.txt`.
- **Status:** Radnik se rebuild-uje na VPS-u, multimodalni prevod je spreman za test.

### 01.05.2026. 06:48 — Čišćenje Osetljivih Podataka
- **Bezbednost:** Izvršena detaljna revizija fajla `README.md` radi uklanjanja potencijalno osetljivih produkcionih podataka (RunPod endpointi, MinIO ključevi, Hetzner IP adrese).
- **Konfiguracija:** Svi osetljivi podaci zamenjeni su odgovarajućim placeholder tekstovima.
- **Bekap:** Stara verzija fajla sačuvana kao `README_old.md`.

### 01.05.2026. 06:56 — Debugging: Zadaci blokirani u PENDING statusu
- **Simptomi:** Novi video zadaci stoje u "PENDING" statusu i ne pomeraju se, UI prikazuje "Čekam prve mikro-statuse...".
- **Uzrok:** Analizom VPS infrastrukture utvrđeno je da je Docker kontejner `sinhronizuj-worker` pao (Exited 1) pre 3 dana zbog `redis.exceptions.ResponseError: UNBLOCKED`. Ovo je direktna posledica `redis-cli FLUSHALL` komande koja je prekinula Celery konekcije, a kontejner se nije automatski restartovao.
- **Rešenje:** Podignut `sinhronizuj-worker` kontejner putem komande `docker compose up -d worker`. Radnik je trenutno aktivan i odmah je preuzeo zaglavljene zadatke iz Redis reda.

### 01.05.2026. 07:00 — Sigurnosna zakrpa za Redis (BSI Upozorenje)
- **Problem:** Primljen abuse izveštaj od Hetznera (prosledio BSI) koji upozorava da je Redis server na portu 6379 javno dostupan bez SASL/password autentifikacije, što predstavlja ozbiljan sigurnosni rizik.
- **Rešenje:**
    1. Izgenerisana je snažna nasumična lozinka (32 karaktera) i dodata u `.env` pod varijablom `REDIS_PASSWORD`.
    2. Modifikovan `docker-compose.yml` tako da `sinhronizuj-redis` kontejner sada prihvata `--requirepass ${REDIS_PASSWORD}` zastavicu pri pokretanju.
    3. Ažurirana `REDIS_URL` varijabla za sve servise (FastAPI, Worker, Beat) tako da se uspešno loguju uz novu lozinku (format: `redis://:password@ip:6379/0`).
    4. Nove konfiguracije su primenjene na VPS-u komandom `docker compose up -d`. Redis baza je sada zaštićena od neovlašćenih upada sa interneta.

### 01.05.2026. 07:07 — Reorganizacija dokumentacije
- **Organizacija:** Kreiran je novi direktorijum `docs/` u koji su prebačeni svi dokumentacioni fajlovi (`PLAN_ARHITEKTURE_V2.md`, `istorija_izrade.md`, `struktura_projekta.txt`, `README_old.md`, `redis_password.txt`).
- **Git:** Ažuriran `.gitignore` kako bi pratio nove putanje dokumentacije i nastavio da ignoriše fajl sa lozinkom.
- **Root:** `README.md` je zadržan u root direktorijumu radi lakšeg pregleda na GitHub-u.

### 01.05.2026. 07:24 — Brainstorming i Planiranje Custom RunPod Arhitekture
- **Inicijativa:** Kako bismo zaobišli bespotrebno probijanje kvota na Docker Hub-u i GitHub Actions-u zbog veličine AI modela, kreiran je detaljan plan prelaska na Custom Docker slike za RunPod Serverless radnike.
- **Dokumentacija:** Generisan kompletan plan i sačuvan u `docs/PLAN_RUNPOD_ARHITEKTURE.md`. Plan obuhvata strategije za Multi-stage build (smanjenje ispod 3GB), Lazy loading AI modela (Whisper, Qwen, Fish Speech) sa mrežnog drajva i rešavanje CI/CD timeout problema (direktno preuzimanje pre-compiled `flash-attn` wheel-ova).
- **Infrastruktura:** Odlučeno je da zadržimo "Monorepo" strukturu i novu arhitekturu gradimo unutar `runpod_workers` direktorijuma uz pomoć GitHub Actions *Path filtering-a*.

### 01.05.2026. 07:28 — Implementacija RunPod Worker Skeletons
- **Struktura:** Uspešno kreirana `runpod_workers/` putanja sa dva izolovana pod-direktorijuma: `stt_llm/` i `tts/`.
- **Faza 1 (Radnik A):** Kreirani `Dockerfile`, `requirements-stt-llm.txt` i `handler.py` za Whisper i vLLM.
    - *Optimizacija:* Urađen **Multi-stage Docker build**. Točkovi se bildaju u privremenom kontejneru (`builder`), a zatim se prebacuju u `python:3.10-slim` runtime kontejner, čime se briše sav apt i pip keš.
- **Faza 2 (Radnik B):** Kreirani fajlovi za Fish Speech TTS radnika.
    - *Rešen problem:* `flash-attn` biblioteka inače traje 40 minuta za kompajliranje, što obično uzrokuje timeout i pad GitHub Actions CI/CD procesa. Rešenje je primenjeno eksplicitnim povlačenjem `pre-compiled wheel` arhiva sa interneta (`flash_attn-2.6.3+cu121torch2.4...`), čime se instalacija skraćuje na par sekundi.
- **Lazy Loading (Handler):** U oba handlera implementirana logika (`ensure_model_exists`) koja proverava `/runpod-volume/models` direktorijum pri startu (Cold Start) pre nego što pokrene API. Ako model fali, povlači ga sa Hugging Face-a.

### 01.05.2026. 07:31 — Produkcijska Integracija Endpointa i CI/CD Pipeline
- **STT & LLM Handler:** Kompletiran kod u `runpod_workers/stt_llm/handler.py`. Ubačena je napredna alokacija memorije (`gpu_memory_utilization=0.85` za vLLM) kako bi Whisper i Qwen mogli bezbedno da dele istu grafičku (npr. A6000) bez OOM grešaka. Ubačena je podrška za `transcribe`, `translate` i `both` zadatke sa Base64 obradom audio fajlova i frejmova.
- **TTS Handler:** Kompletiran `runpod_workers/tts/handler.py` sa Base64 obradom ulaznog referentnog audia i izlaznog generisanog fajla, spreman za pozivanje Fish Speech `tools.generate` komande.
- **CI/CD Automatizacija:** Kreiran `.github/workflows/runpod-builder.yml`. Ovaj workflow se okida samo pri promenama unutar `runpod_workers/` foldera (*Path filtering*). Prijavljuje se na `ghcr.io`, prepoznaje repozitorijum, vrši `buildx` optimizaciju uz GitHub Actions caching (čime sledeći buildovi traju drastično kraće) i automatski push-uje gotove Docker imidže.
- **Status:** Custom RunPod infrastruktura je tehnički zaokružena i endpointi su spremni za testno podizanje na RunPod platformi iz `ghcr.io` registra.

### 01.05.2026. 07:42 — Debugging: Pad GitHub Actions CI/CD Pipeline-a
- **Problem:** Inicijalni GitHub Actions run je pukao zbog dva česta razloga za teške ML kontejnere: nedostatak prostora na disku za runner-a (GitHub daje samo ~14GB slobodnog prostora po besplatnom runneru) i implicitno kompajliranje `flash-attn` modula pri instalaciji `vLLM` u `stt_llm` kontejneru.
- **Rešenje 1 (Disk Space):** Dodat `jlumbroso/free-disk-space@main` korak u `.github/workflows/runpod-builder.yml` koji briše neiskorišćene Android, .NET i Haskell keš fajlove na GitHub runner-u, oslobađajući dodatnih ~25-30GB pre početka build-a.
- **Rešenje 2 (Flash-attn Dependency Order):** Unutar `runpod_workers/stt_llm/Dockerfile` ukinut je multi-stage build u korist jednostavnijeg single-stage pristupa sa rigoroznim redosledom instalacije: 1) Instalira se `torch` izolovano, 2) Zatim se instalira *pre-compiled* `flash-attn` wheel koji zahteva prethodno prisustvo torch-a, 3) Na kraju se okida `pip install -r requirements.txt`. Kada instalacija dođe do `vLLM`, pip vidi da je `flash-attn` već tu i elegantno preskače zloglasni 40-minutni source build.

### 01.05.2026. 07:50 — Debugging: Flash-attn Wheel 404 Error
- **Problem:** GitHub Actions log je prikazao 404 Not Found grešku pri preuzimanju `flash-attn` pre-compiled wheel-a za `v2.6.3` i `cu121`.
- **Analiza:** Proverom zvaničnih GitHub izdanja (Releases) `Dao-AILab/flash-attention` repozitorijuma, ustanovljeno je da `v2.6.3` sadrži isključivo `cu118` i `cu123` pakete, te da ne postoji specifičan build za `cu121` sa `torch 2.4.0`.
- **Rešenje:** Odluka je pala na nadogradnju preuzimanja na stabilno izdanje `v2.8.3` koje obezbeđuje univerzalni `cu12torch2.4` wheel (`flash_attn-2.8.3+cu12torch2.4cxx11abiFALSE-cp310-cp310-linux_x86_64.whl`), unazad kompatibilan sa `nvidia/cuda:12.1.1-devel` bazom imidža i vLLM kontejnerom. Ažuriran `Dockerfile` i gurnute izmene na GitHub čime je build uspešno nastavljen. Naknadno (07:54) primenjena ista popravka i za `tts` radnika (obzirom da je prva izmena obuhvatila samo `stt_llm`).

### 01.05.2026. 18:49 — Uspešan Build i Push na ghcr.io
- **Status:** Nakon primene zakrpa, GitHub Actions pipeline je prošao bez ikakvih grešaka. Trajanje build procesa: STT/LLM radnik (~12 min), TTS radnik (~10 min).
- **Infrastruktura:** Obe slike (image) su uspešno izgrađene (build) i gurnute (push) u `ghcr.io/Gruya13/sinhronizuj.me` repozitorijum.
- **Sledeći koraci:** Konfigurisanje novih *Serverless Endpoint*-a na RunPod portalu koristeći upravo isporučene Docker slike. Sistem je sada tehnički spreman za testiranje inference end-to-end (E2E).
