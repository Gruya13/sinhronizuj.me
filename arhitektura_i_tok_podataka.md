# 🎙️ Sinhronizuj.me — Celokupna Arhitektura i Tok Podataka Kroz Sistem

**Sinhronizuj.me** je napredna cloud platforma za automatsku video i audio sinhronizaciju (dubbing) na srpski jezik. Sistem koristi **hibridnu cloud arhitekturu** koja odvaja upravljanje i skladištenje (**Control Plane**) od zahtevnih AI proračuna (**Compute Plane**). 

Ovaj dokument pruža sveobuhvatan tehnički pregled arhitekture, svih komponenti sistema, detaljnog toka podataka kroz pipeline-ove, kao i načina na koji moduli međusobno komuniciraju.

---

## 🗺️ 1. Pregled Visokonivojske Arhitekture

Sistem se sastoji iz dva glavna sloja:
1. **Control Plane (Hetzner VPS)**: Hostuje klijentsku aplikaciju (React), API server (FastAPI), bazu podataka (PostgreSQL), keš/broker sloj (Redis), skladište podataka (MinIO S3) i Celery radnike za orkestraciju i lokalnu obradu audio/video signala.
2. **Compute Plane (Modal.com)**: Serverless platforma na kojoj su raspoređeni GPU kontejneri koji se pokreću po potrebi (Scale-to-Zero) za teške mašinske proračune (vokalna separacija, transkripcija, prevođenje, lektura, glasovna sinteza i LipSync).

### Dijagram Arhitekture i Interakcija

```mermaid
flowchart TB
    subgraph Klijentski Sloj (Korisnik)
        UI[React Frontend SPA]
    end

    subgraph Control Plane (Hetzner VPS - Docker Compose)
        API[FastAPI Web Server]
        DB[(PostgreSQL)]
        Cache[(Redis - Broker / Rate Limit / Drafts)]
        S3[(MinIO S3 Object Storage)]
        Celery[Celery Worker - Asinhroni Zadaci]
    end

    subgraph Compute Plane (Modal.com - Serverless GPU-ovi)
        Demucs[Demucs v4 Worker - NVIDIA T4]
        ASR[Whisper-large-v3 + SenseVoice - NVIDIA T4]
        QwenVL[Qwen2-VL-7B Translator - NVIDIA A10G]
        QwenLektor[Qwen3-32B-AWQ vLLM Lektor - NVIDIA A100 40GB]
        TTS[Piper & OpenVoice V2 TTS - NVIDIA L4]
        Wav2Lip[Wav2Lip LipSync - NVIDIA A10G]
    end

    %% Komunikacione veze
    UI <-->|HTTP / JWT Autentifikacija| API
    API <-->|SQLAlchemy| DB
    API <-->|Redis Client| Cache
    API <-->|S3 SDK / Presigned URL-ovi| S3
    
    API -->|Pokretanje Zadataka| Cache
    Cache -->|Preuzimanje Zadataka| Celery
    
    Celery <-->|Orkestracija i AI Pozivi| Demucs
    Celery <-->|Orkestracija i AI Pozivi| ASR
    Celery <-->|Orkestracija i AI Pozivi| QwenVL
    Celery <-->|Orkestracija i AI Pozivi| QwenLektor
    Celery <-->|Orkestracija i AI Pozivi| TTS
    Celery <-->|Orkestracija i AI Pozivi| Wav2Lip
    
    Celery <-->|Upis/Čitanje| DB
    Celery <-->|Preuzimanje/Upload audio/video| S3
```

---

## 🛠️ 2. Komponente Sistema i Njihove Uloge

### 2.1 Klijentski Sloj (Frontend)
Izgrađen korišćenjem **React**-a i stilizovan pomoću **Vanilla CSS**-a sa modernim vizuelnim efektima (glassmorphism, aurora blobos, fluidne animacije preko *Framer Motion*-a).
*   **StudioContext ([StudioContext.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/context/StudioContext.jsx))**: Centralni React Context koji drži globalno stanje aplikacije, listu projekata, trenutno selektovan projekat, stanje učitanog videa/audia i status polling-a.
*   **DAW Editor Vremenske Linije ([Timeline.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Studio/Timeline.jsx))**: 
    *   Omogućava vizuelni prikaz segmenata govora i talasnog oblika (Waveform) originalnog i srpskog vokala pomoću `wavesurfer.js`.
    *   Podržava **Drag-and-Drop** prevlačenje segmenata i rastezanje (Resizing) ivica direktno na vremenskoj osi.
    *   Detektuje kolizije (preklapanje) srpskih segmenata u realnom vremenu na osnovu brzine reprodukcije (Tempo).
*   **Grupne Operacije (Bulk Operations)**: Omogućava promenu parametara (jačina zvuka, tempo, visina glasa, tip glasa) na više segmenata odjednom pomoću `Ctrl+Click` selekcije.
*   **Undo/Redo Istorija**: Klijentski stack koji beleži do 50 istorijskih stanja izmena u Studiju.

### 2.2 API Server (FastAPI)
Nalazi se na [backend/main.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/main.py) i služi kao komunikacioni interfejs za klijenta.
*   **JWT Autentifikacija ([auth.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/core/auth.py))**: Upravljanje registracijom, prijavom i sesijama korisnika uz automatsku proveru tokena.
*   **Rate Limiting**: Integrisan `slowapi` koji koristi Redis za skladištenje kvota i ograničavanje učestalosti poziva na osetljive rute (npr. registracija, analiza, TTS preview).
*   **Upravljanje Projektima**: Rute za kreiranje, brisanje i listanje projekata, dobijanje statusa obrade i preuzimanje presigned URL-ova sa MinIO S3 skladišta.
*   **Hot-Patching API**: Rute koje u realnom vremenu primaju izmenjene parametre pojedinačnog segmenta iz Studija, vrše brzu generaciju i lepljenje (splicing) audia i vraćaju ga klijentu bez potrebe za renderovanjem celog videa.

### 2.3 Baza Podataka (PostgreSQL)
Koristi **SQLAlchemy** ORM za mapiranje relacionih entiteta definisanih u [models.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/core/models.py):
*   **User**: Podaci o korisnicima i njihove lozinke (hešovane pomoću bcrypt-a).
*   **Project**: Podaci o projektima (naziv, originalni video URL, status: `PENDING`, `PROCESSING`, `STUDIO`, `COMPLETED`, `FAILED`, i putanje fajlova na S3).
*   **Segment**: Pojedinačni segmenti govora sa originalnim engleskim tekstom, srpskim prevodom, vremenskim oznakama (`start`, `end`), i audio parametrima (`volume`, `tempo`, `pitch`, `ducking`, `voice_type`).
*   **Glossary**: Korisnički glosari za prevođenje specifičnih stručnih termina.

### 2.4 Broker i Keš (Redis)
Služi kao:
1.  **Celery Message Broker**: Prenosi poruke o novim zadacima od FastAPI-ja do Celery radnika.
2.  **Skladište Draftova**: Čuva privremene rezultate analize (`project:{project_id}:draft`) u JSON formatu kako bi se smanjilo opterećenje baze podataka tokom brze pretrage i obrade.
3.  **Rate Limiter Backend**: Pamti brojače zahteva po IP adresi ili korisničkom ID-ju.

### 2.5 Skladište Podataka (MinIO S3)
Kompatibilno sa AWS S3. Svi fajlovi se čuvaju pod privatnim pravima pristupa, a klijentu se prosleđuju privremeni **Presigned URL-ovi** (rok važenja 24 sata).
*   Putanja originalnog videa: `projects/{project_id}/original_video.mp4`
*   Originalni vokali: `projects/{project_id}/vocals.wav`
*   Instrumental/pozadinska muzika: `projects/{project_id}/no_vocals.wav`
*   Pojedinačni sintetizovani TTS segmenti: `projects/{project_id}/tts/segment_{segment_id}.wav`
*   Konačni sinhronizovani video: `projects/{project_id}/final_video.mp4`

---

## 🔄 3. End-to-End Tok Podataka Kroz Sistem

Celokupni životni ciklus obrade videa sastoji se iz tri ključne faze.

```
[Korisnik] ──(1. URL/Video)──> [FastAPI] ──(2. Enqueue)──> [Redis] ──(3. Dequeue)──> [Celery Worker]
                                                                                          │
                                                                                 (Komunikacija sa Modal GPU)
                                                                                          │
                                                                                          ▼
[Korisnik] <──(5. Polling/Studio)── [Redis Draft] <──(4. Save Draft & DB)── [Celery: Faza 1 Analiza]
    │
(Korisničke izmene, miksovanje, knobs, hot-patching)
    │
    ▼
[Korisnik] ──(6. Pokretanje Rendera)──> [FastAPI] ──(7. Enqueue)──> [Celery: Faza 2 Render]
                                                                            │
                                                                   (TTS, Stretch, Wav2Lip)
                                                                            │
                                                                            ▼
[Korisnik] <──(9. Play Video) ── [MinIO S3] <──(8. Upload Video & DB) ──────┘
```

---

## ⚙️ 4. Detaljan Opis Faza Pipeline-a

### 4.1 Faza 1: Asinhrona Analiza (`analyze_video_task`)
Pokreće se kada korisnik unese video. Zadatak vodi [backend/worker/tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py#L35):

1.  **Preuzimanje i Preprocesiranje**:
    *   Lokalni Celery radnik koristi `yt-dlp` (za YouTube linkove) ili preuzima uploadovan fajl sa S3.
    *   Video se konvertuje i deli na video traku i audio traku.
2.  **Separacija Zvuka (Demucs)**:
    *   Audio se šalje na Modal radnika ([demucs_worker.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/demucs_worker.py)) koji koristi **HTDemucs v4** model.
    *   Rezultat su dva fajla: `vocals.wav` (čisti vokali) i `no_vocals.wav` (instrumental i zvučni efekti).
    *   Vrativši se na VPS, oba fajla se odmah otpremaju na MinIO S3.
3.  **Ekstrakcija Vizuelnog Konteksta**:
    *   Dok se zvuk obrađuje, Celery lokalno pokreće FFmpeg i izvlači 10 ključnih frejmova ravnomerno raspoređenih kroz video.
    *   Frejmovi se konvertuju u JPEG, potom u Base64 i šalju kao multimodalni kontekst za prevodioca.
4.  **Transkripcija i Vremensko Pozicioniranje (STT)**:
    *   Fajl `vocals.wav` se šalje na Modal ASR radnika ([stt_worker.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/stt_worker.py) i [sensevoice_worker.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/sensevoice_worker.py)).
    *   **Whisper-large-v3** vrši transkripciju i kreira precizne vremenske odrednice na nivou reči (word-level timestamps).
    *   **SenseVoice-Small** vrši paralelnu analizu za prepoznavanje emocija, uzdaha, muzike i tačne interpunkcije, te vrši arbitražu.
5.  **Multimodalni Prevod (Translator)**:
    *   Transkript i 10 izvučenih frejmova se prosleđuju na Modal translator radnika ([translator_worker.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/translator_worker.py)).
    *   **Qwen2-VL-7B-Instruct** analizira vizuelni kontekst i tekst, određuje pol govornika (zbog pravilnih gramatičkih oblika u srpskom) i prevodi rečenice.
6.  **Lektura, Ekavizacija i Glosar (Lektor)**:
    *   Prevedeni tekst se šalje Modal Lektor radniku ([lektor_worker.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/lektor_worker.py)) koji koristi **Qwen3-32B-AWQ** model na **NVIDIA A100-40GB** instanci.
    *   Lektor primenjuje predefinisani glosar iz [glossaries.json](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/glossaries.json) (za stručne termine), vrši ekavizaciju, ispravlja padeže i pretvara prevod u "ti-formu" obraćanja.
    *   Na kraju, tekst prolazi kroz programsko čišćenje (`clean_translation_text`) radi otklanjanja neželjenih karaktera i dijalektizama.
7.  **Zapisivanje Nacrta**:
    *   Metapodaci o segmentima se čuvaju u Redis draft i u PostgreSQL bazu, a projekat prelazi u status `STUDIO`.

---

### 4.2 Interaktivna Studio Faza (DAW Real-Time)
Korisnik otvara projekat u Studiju, gde se podaci menjaju u realnom vremenu:

*   **Undo/Redo Mehanizam**: Svaka izmena prevoda ili promena knob-a upisuje trenutno stanje u lokalni stack. Korisnik može vršiti korak unazad/unapred (`Ctrl+Z` / `Ctrl+Y`).
*   **Knob Kontrole**: Podešavaju `volume` (jačina segmenta), `tempo` (brzina izgovora), `pitch` (visina) i `ducking` (jačina stišavanja pozadinske muzike).
*   **Hot-Patching / Splicing**:
    *   Kada korisnik promeni tekst ili parametre segmenta i pritisne Space/Play, klijent šalje brzi zahtev FastAPI endpointu `/api/v1/projects/{project_id}/preview`.
    *   API poziva Piper/OpenVoice na Modalu da generiše *samo* taj izmenjeni segment.
    *   API koristi biblioteku **pydub** da iseče stari segment iz spojenog vokala i ulepi (splice) novi segment na tačnu vremensku poziciju.
    *   Ovo omogućava instant audio preview u klijentu u roku od 150ms bez renderovanja celog videa.
*   **Detekcija Kolizija**: Ako je srpski tekst predugačak za originalno trajanje segmenta (s obzirom na odabrani tempo), vremenska linija vizuelno crveni i prikazuje upozorenje o preklapanju sa sledećim segmentom.

---

### 4.3 Faza 2: Finalno Renderovanje (`render_video_task`)
Kada korisnik klikne na **Render**, pokreće se asinhroni Celery zadatak na VPS-u:

1.  **Sinteza Govora i Kloniranje Glasa**:
    *   Za segmente koji nemaju prethodno generisane wav fajlove na S3, pokreće se sinteza na Modalu ([tts.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/tts.py) / [tts_openvoice.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/tts_openvoice.py)).
    *   Ako je izabran standardni glas, koristi se **Piper TTS** (srpski model).
    *   Ako je izabrano kloniranje, koristi se **OpenVoice V2** koji uzima 5-sekundni uzorak originalnog glasa tog govornika i klonira boju glasa u srpsku sintezu.
2.  **Audio Procesiranje i Rubberband Filteri**:
    *   Za svaki generisani wav fajl primenjuju se FFmpeg filteri:
        *   `rubberband` filter za precizno ubrzavanje/usporavanje (Tempo) i promenu visine glasa (Pitch) bez uticaja na kvalitet.
        *   `volume` filter za jačinu zvuka.
3.  **Dynamic Time Stretching (Vremensko Rastezanje)**:
    *   Ako je srpski audio na nekom segmentu i dalje duži od originalnog engleskog trajanja (i pored ubrzanja), pokreće se dinamički algoritam rastezanja.
    *   Sistem računa odnos trajanja i pomoću FFmpeg-a **usporava video frejmove i pozadinsku muziku** na tom specifičnom vremenskom intervalu (maksimalno do 1.15x) kako bi se video prilagodio govoru.
4.  **Audio Miksovanje i Ducking**:
    *   Svi obrađeni segmenti se spajaju u jednu vokalnu traku (`merged_vocals.wav`).
    *   Pozadinska muzika (`no_vocals.wav`) se miksuje sa vokalom, pri čemu se primenjuje **Ducking** (stišavanje muzike na mestima gde postoji srpski vokal).
5.  **LipSync Sinhronizacija (Wav2Lip)**:
    *   Sistem proverava učešće lica u video fajlu. Ako se lice detektuje u više od 10% frejmova, video i spojen srpski vokal se šalju na Modal GPU radnika ([lipsync.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/lipsync.py)).
    *   **Wav2Lip** model na **NVIDIA A10G** vrši fotorealističnu modifikaciju usana govornika kako bi se pokret usana savršeno poklapao sa izgovorenim srpskim rečima.
6.  **Konačno Spajanje i Upload**:
    *   FFmpeg spaja finalni video sa miksovanim audiom.
    *   Fajl se postavlja na MinIO S3 pod ključem `projects/{project_id}/final_video.mp4`, a status projekta u bazi podataka se menja u `COMPLETED`. Klijent preko polling-a detektuje uspešan završetak i nudi video za reprodukciju i preuzimanje.

---

## 💾 5. Backup Strategija i Održavanje

Za očuvanje integriteta podataka i brz oporavak u slučaju kvara, implementiran je automatizovani backup sistem:
*   **Backup Skripte**: Nalaze se u [infra/backup.py](file:///home/gruya/Projektri/sinhronizuj.me/infra/backup.py) i [infra/backup.sh](file:///home/gruya/Projektri/sinhronizuj.me/infra/backup.sh).
*   **Princip rada**:
    *   Pokreće se automatski dump PostgreSQL baze iz Docker kontejnera.
    *   Kreirani SQL fajl se kompresuje (gzip).
    *   Povezuje se na MinIO S3 skladište i otprema fajl u namenski `backups` bucket.
    *   Primenjuje se pravilo rotacije: skripta zadržava bekape za poslednjih 7 dana, a sve starije bekapa automatski briše sa MinIO skladišta kako bi se optimizovao prostor.
*   **Pokretanje**: Konfigurisano preko sistemskog `cron` servisa na Hetzner VPS-u koji skriptu izvršava svakog dana u 02:00.

---

## 🔒 6. Sigurnost i Mrežna Izolacija

1.  **Docker compose mreža**: Svi servisi na Control Plane-u (API, DB, Redis, MinIO, Celery) nalaze se u izolovanoj internoj Docker mreži. Samo FastAPI server ima izložene portove ka spoljnom svetu (preko Nginx obrnutog proksija sa SSL enkripcijom).
2.  **S3 Zaštita**: Buckets na MinIO S3 nemaju javni pristup. Svi fajlovi (video, audio, segmenti) su bezbedni, a pristup im se omogućava isključivo preko dinamički generisanih presigned URL-ova sa kratkim rokom trajanja.
3.  **Rate Limiting**: Zaštita API endpointova pomoću Redis token-bucket algoritma koji onemogućava DDoS napade i preopterećenje skupih GPU resursa na Modalu.
