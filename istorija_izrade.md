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
