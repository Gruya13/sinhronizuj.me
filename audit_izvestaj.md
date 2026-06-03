# 🎙️ Sinhronizuj.me — Detaljan Izveštaj o Auditu Sistema

Ovaj dokument predstavlja sveobuhvatnu analizu i audit sistema **Sinhronizuj.me**, uključujući arhitekturu koda, implementirane funkcionalnosti, analizu prednosti (snaga) i mana (slabosti/ograničenja) sistema, kao i preporuke za dalji razvoj.

---

## 1. Arhitektura Sistema i Kod

Sistem je izgrađen na bazi **hibridne cloud arhitekture** koja je logički i hardverski podeljena na dva dela kako bi se maksimizovala efikasnost i smanjili troškovi:

1. **Control Plane (VPS - Hetzner CPU-only)**:
   - **FastAPI API Server (`backend/main.py`)**: Upravlja REST rutama, generisanjem presigned URL-ova za upload na MinIO, komunikacijom sa Redis-om i pokretanjem asinhronih Celery zadataka.
   - **Celery Radnik i Beat (`backend/worker/tasks.py`)**: Izvršava teške i dugotrajne poslove u pozadini (downloadi, FFmpeg manipulacije, spajanje audio/video zapisa). Beat vrši periodično čišćenje starih fajlova na disku i MinIO skladištu.
   - **Redis**: Koristi se kao message broker za Celery i kao primarna baza podataka za metapodatke projekata i radne nacrte (drafts).
   - **MinIO Object Storage**: S3 kompatibilno skladište za direktan upload originalnih videa i preuzimanje finalnih sinhronizovanih fajlova.

2. **Compute Plane (Modal.com - Serverless GPU)**:
   - Hostuje zahtevne AI modele koji se pokreću i naplaćuju **samo u sekundi izvršavanja** (Demucs za vokalnu separaciju, Whisper i SenseVoice za STT, Qwen2-VL i Qwen 2.5/3.0 za prevođenje i lekturu, Piper i OpenVoice V2 za sintezu i kloniranje glasa).

3. **Frontend (React + Vite + Tailwind CSS)**:
   - Napisan kao monolitna klijentska aplikacija u datoteci [`App.jsx`](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/App.jsx). Sadrži naprednu interaktivnu vremensku liniju (timeline) i klijentski audio mikser.

---

## 2. Detaljna Analiza Funkcionalnosti i Pipeline-a

### Faza 1: Asinhrona Analiza
- **Separacija vokala (Demucs)**: Uspešno odvaja vokale od muzike i šumova.
- **Ekstrakcija vizuelnog konteksta**: OpenCV lokalno izvlači 10 ključnih frejmova iz videa, što omogućava multimodalnom modelu (Qwen2-VL) da prepozna pol govornika i kontekst scene za tačniji prevod.
- **Ensemble ASR i LLM Arbitraža**: Vokalni audio se paralelno transkribuje preko **Whisper-large-v3** (koji daje precizne vremenske oznake) i **SenseVoice-Small** (koji ima bolju interpunkciju). Zatim **Qwen 32B** vrši arbitražu i ispravlja greške u sluhu za tehničke i specifične reči, zadržavajući tačne tajminge.
- **Prevođenje i Lektura**: Dvoetapni proces (Multimodalni prevod na srpsku ekavsku latinicu preko Qwen2-VL + Lektura preko Qwen3-32B-AWQ sa primenom tematskog i dinamičkog glosara).

### Interaktivni Studio Mod
- **Granularno podešavanje**: Nezavisno menjanje teksta, jačine zvuka (Volume), brzine govora (Tempo), visine glasa (Pitch) i jačine pozadinske muzike (Ducking) po svakom segmentu.
- **Čarobni štapić (Magic Shorten)**: Na klik korisnika šalje se zahtev Modal Lektoru da inteligentno skrati srpski tekst na preporučeni limit karaktera (`trajanje * 15` ili `trajanje * 20`) kako bi se uklopio u vremenski okvir bez narušavanja smisla.
- **Hot-Patching Splicing**: Omogućava trenutno preslušavanje izmenjenog segmenta (u roku od 100-200ms) tako što se TTS generiše samo za taj segment i dinamički ubacuje u celokupan miks vokala u memoriji i na disku preko `pydub` biblioteke.
- **Realtime Klijentski Mikser**: Dva plejera na frontendu (vokali + pozadinska muzika) koji se u 50ms intervalu usklađuju sa videom i reaguju na promenu slajdera u realnom vremenu (menjaju playback rate i jačinu zvuka plejera).

### Faza 2: Finalno Renderovanje
- **TTS Sinteza**: Batch generisanje srpskih vokala preko Piper-a (standardni glasovi) ili OpenVoice V2 (kloniranje glasa govornika sa L4 GPU).
- **Dynamic Time Stretching**: Ako je srpski izgovor i dalje duži od originalnog (i nakon primene proračunatog ubrzanja govora u opsegu 0.75-1.25x), FFmpeg usporava video i pozadinsku muziku na tom specifičnom mestu (maksimalno do 1.15x) kako bi se dobila prirodna i sinhronizovana traka.
- **LipSync (Wav2Lip)**: Provera lica OpenCV modelom (ako je prisutno na >10% frejmova). Ako jeste, pokreće se Wav2Lip model za sinhronizaciju pokreta usana sa srpskim audio fajlom.

---

## 3. Prednosti Sistema (Snage)

1. **Izuzetno Ekonomična Arhitektura**: Hibridni pristup (VPS + Modal serverless GPU) eliminiše potrebu za skupim VPS serverima sa namenskim grafičkim karticama koji bi naplaćivali rad 24/7 čak i kada sistem niko ne koristi.
2. **Kvalitet i Konzistentnost Prevoda**: Ensemble ASR (Whisper + SenseVoice) uz LLM arbitražu i dinamički glosar rešavaju česte probleme AI prevodilaca (kao što su izmišljene reči, nepravilna deklinacija brendova, ijekavizmi i pogrešni padeži za skraćenice poput "Ej Aj").
3. **Vrhunski Korisnički Doživljaj (UX)**: Interaktivna vremenska linija, hot-patching splicing i klijentski mikser omogućavaju korisniku rad u realnom vremenu bez čekanja na dugotrajne rendere za svaku sitnu izmenu.
4. **Dynamic Time Stretching**: Pametno usporavanje videa sprečava "naguravanje" reči i neprirodno brz govor koji je čest kod standardnih sinhronizacija na srpski jezik (budući da srpski u proseku zahteva oko 15-20% više prostora/vremena od engleskog za isti smisao).

---

## 4. Mane i Ograničenja Sistema (Slabosti)

### ⚠️ 1. Lokalni Wav2Lip i CPU-only Bottleneck (Kritično)
- **Problem**: U dokumentaciji piše da Wav2Lip radi na Modalu (NVIDIA A10G), ali se u kodu [`backend/worker/lipsync.py`](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/lipsync.py#L54-L90) on pokreće preko lokalnog podprocesa koji traži instalaciju u `/opt/Wav2Lip` na VPS-u.
- **Implikacija**: Pošto je Hetzner VPS CPU-only i docker radi u laganom režimu bez instaliranog Wav2Lip-a, sistem stalno upada u fallback i **u potpunosti preskače LipSync**, vraćajući običan renderovani video bez usklađenih usana. Ako bi se Wav2Lip i pokrenuo lokalno na CPU-u, obrada bi trajala izuzetno dugo i blokirala bi radnika.

### ⚠️ 2. Monolitni i Težak Frontend (`App.jsx`)
- **Problem**: Kompletan frontend kod (više od 2300 linija) sa celokupnim stanjem, API pozivima, tajmerima, logikom sinhronizacije zvučnih plejera i renderovanjem interfejsa nalazi se u jednoj datoteci [`App.jsx`](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/App.jsx).
- **Implikacija**: Kod je izuzetno težak za čitanje, debagovanje i proširivanje. Bilo kakva promena u UI komponenti zahteva pretragu kroz hiljade linija koda i povećava rizik od neželjenih nuspojava u drugim delovima aplikacije.

### ⚠️ 3. Nepostojanje Prave Perzistentne Baze Podataka (PostgreSQL)
- **Problem**: U `README.md` se spominje PostgreSQL baze podataka u sklopu Hetzner VPS-a. Međutim, u celom projektu (uključujući konfiguraciju i API server) nema nikakvih tragova PostgreSQL-a niti ORM-a (npr. SQLAlchemy). Svi podaci o projektima i nacrtima se čuvaju isključivo u Redis memorijskom skladištu.
- **Implikacija**: Redis je prevashodno keš i message broker. Draftovi imaju rok trajanja od 7 dana (`ex=604800`). Ako se Redis kontejner restartuje ili obriše bez ispravno podešene disk perzistentnosti (AOF/RDB), svi podaci o projektima, segmentima i podešavanjima korisnika biće nepovratno izgubljeni. Takođe, rok od 7 dana znači da projekti automatski nestaju nakon tog perioda.

### ⚠️ 4. Apsolutne Lokalne Putanje u Redis Draftovima
- **Problem**: Nacrti projekata u Redis-u čuvaju apsolutne lokalne putanje do fajlova na disku (npr. `"vocals_path": "/app/temp_workspace/vocals_xyz.wav"`).
- **Implikacija**: Ako se promeni struktura foldera, kontejner rekreira sa drugim volumenima, ili se projekat migrirao, ove putanje postaju nevažeće, što dovodi do pucanja API-ja ili Celery radnika pri pokušaju pristupa fajlovima. Sistem bi trebao da čuva MinIO S3 ključeve (npr. `uploads/vocals_xyz.wav`) i preuzima ih po potrebi, umesto da se oslanja na lokalni fajl sistem.

### ⚠️ 5. Sigurnost i Nedostatak Autentifikacije
- **Problem**: API server je potpuno otvoren (`allow_origins=["*"]`) i nema nikakav sistem autentifikacije (JWT, API ključevi).
- **Implikacija**: Svaki korisnik može pristupiti bilo kom projektu, menjati segmente ili obrisati tuđe projekte jednostavnim slanjem HTTP zahteva sa ID-jem projekta koji se lako može presresti ili pogoditi. Takođe, ne postoji izolacija projekata po korisnicima.

### ⚠️ 6. Cold Start i Latencija na Modalu
- **Problem**: Zbog serverless prirode platforme Modal.com, pokretanje neaktivnih kontejnera (cold start) može potrajati i do 15-30 sekundi, posebno za teške modele (poput Qwen Lektora i OpenVoice V2).
- **Implikacija**: Prvi API zahtev u novoj sesiji ili nakon pauze može delovati blokirano ili izazvati timeout na klijentu pre nego što Modal radnik postane aktivan.

---

## 5. Preporuke za Unapređenje Sistema

Za prelazak sistema na viši, produkcioni nivo, preporučuje se implementacija sledećih koraka:

### 🚀 1. Migracija Wav2Lip-a na Modal.com (Visok Prioritet)
- **Opis**: Kreirati namenskog serverless radnika na Modalu za Wav2Lip (npr. `wav2lip_worker.py` unutar `modal_workers/` sa A10G ili T4 GPU).
- **Prednost**: Omogućiće stabilan i brz LipSync bez opterećenja lokalnog VPS-a i rešiće trenutni problem gde se ova ključna funkcionalnost uvek preskače zbog nedostatka lokalnih resursa.

### 🚀 2. Refaktoring i Modularizacija Frontenda (Srednji Prioritet)
- **Opis**: Razbiti monolitni `App.jsx` na manje, funkcionalne React komponente:
  - `components/ProjectList.jsx` (pregled i kreiranje projekata)
  - `components/StudioTimeline.jsx` (vremenska linija sa segmentima)
  - `components/SegmentEditor.jsx` (uređivanje teksta i poziv lektora)
  - `components/MixerPanel.jsx` (slajderi za volume, tempo, pitch, ducking)
  - `components/HardwareMonitor.jsx` (prikaz statusa resursa)
  - `services/api.js` (svi API pozivi izdvojeni iz komponenti)
- **Prednost**: Čistiji kod, lakše održavanje i brži razvoj novih UI mogućnosti.

### 🚀 3. Implementacija PostgreSQL Baze Podataka (Srednji Prioritet)
- **Opis**: Povezati stvarni PostgreSQL kontejner (kroz `docker-compose.yml`) i implementirati modele za projekte i segmente na backendu (koristeći npr. SQLModel ili SQLAlchemy). Redis ostaviti isključivo za Celery broker i keširanje brzih operacija (poput privremenih logova ili task statusa).
- **Prednost**: Dugoročna perzistentnost podataka, nema gubljenja projekata nakon 7 dana, bolja struktura podataka i lakše pretraživanje.

### 🚀 4. Prelazak sa Lokalnih Putanja na S3 Ključeve (Srednji Prioritet)
- **Opis**: Izmeniti backend tako da u Redis-u (ili novoj bazi) čuva relativne ključeve objekata u MinIO skladištu (npr. `projects/{project_id}/vocals.wav`) umesto lokalnih apsolutnih putanja na disku VPS-a. Celery radnici bi pre svakog koraka preuzeli potreban fajl iz MinIO skladišta u svoj privremeni radni prostor.
- **Prednost**: Arhitektura postaje potpuno nezavisna od lokalnog fajl sistema, što olakšava skaliranje radnika na više mašina i sprečava pucanje koda pri promeni kontejnera.

### 🚀 5. Uvođenje Autentifikacije i Korisničkih Naloga (Nizak/Srednji Prioritet)
- **Opis**: Implementirati jednostavnu autentifikaciju (npr. FastAPI OAuth2 sa JWT tokenima) i povezati projekte sa ID-jem prijavljenog korisnika.
- **Prednost**: Osigurava privatnost projekata i štiti resurse (API i Modal GPU troškove) od neovlašćenog korišćenja.
