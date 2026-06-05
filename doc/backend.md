# ⚙️ Detaljna Dokumentacija Backenda (Control Plane)

Backend platforme **Sinhronizuj.me** dizajniran je kao brz, asinhroni API server napisan u **Python-u** uz pomoć **FastAPI** web framework-a. Služi kao orkestrator celokupnog toka podataka, komunicira sa bazom podataka, brokerom, skladištem i šalje teške poslove serverless radnicima na Modalu.

---

## 🛠️ FastAPI Arhitektura i Rutiranje

FastAPI koristi ASGI (Asynchronous Server Gateway Interface) i obezbeđuje visoke performanse kroz native asinhrono izvršavanje (`async/await`). 

### Glavni Endpoint-i (`backend/main.py`)
1.  **Autentifikacija (`/api/v1/auth/*`)**:
    *   `POST /register`: Registracija novih korisnika. Lozinke se hešuju pomoću `bcrypt.gensalt()` i čuvaju u bazi podataka.
    *   `POST /login`: Provera email-a i lozinke. Vraća JWT (JSON Web Token) potpisan tajnim ključem (`JWT_SECRET`) sa definisanim trajanjem.
    *   `GET /me`: Vraća profil ulogovanog korisnika na osnovu JWT tokena u Authorization zaglavlju.
2.  **Skladište (`/api/v1/storage/*`)**:
    *   `GET /upload_url`: Generiše **S3 Presigned URL** za direktan upload video fajlova sa klijenta na MinIO, čime se zaobilazi opterećenje API servera velikim payload-ima.
3.  **Projekti (`/api/v1/project*`)**:
    *   `POST /project`: Kreira prazan projekat u PostgreSQL bazi.
    *   `GET /projects`: Izlistava projekte prijavljenog korisnika.
    *   `DELETE /project/{project_id}`: Briše projekat iz baze, briše draft iz Redisa i sve povezane medija fajlove sa MinIO S3 skladišta.
    *   `GET /project/{project_id}`: Učitava nacrt projekta, kreira presigned URL-ove za audio i video resurse, i kešira nacrt u Redis na 7 dana.
    *   `POST /project/{project_id}/save`: Masovno čuvanje izmenjenih segmenata.
4.  **AI Obrada i Render (`/api/v1/project/{project_id}/*`)**:
    *   `POST /process-video` (Faza 1): Pokreće asinhroni Celery zadatak za analizu videa.
    *   `POST /segment/{segment_id}/shorten` (Magic Shorten): Poziva Modal Lektor API za skraćivanje teksta u realnom vremenu.
    *   `POST /segment/{segment_id}/tts` (Hot-Patching): Sinteza i ulepljivanje jednog segmenta govora.
    *   `POST /generate-all-tts`: Grupna sinteza svih segmenata projekta odjednom.
    *   `POST /render` (Faza 2): Pokreće Celery zadatak za sklapanje videa, audio miksovanje i LipSync.
    *   `GET /status/{task_id}`: Vraća status Celery zadatka (`PENDING`, `PROGRESS`, `SUCCESS`, `FAILURE`) sa uključenim live informacijama o troškovima (`costs`).
5.  **Redis kontrola (`/api/v1/redis/*`)**:
    *   `POST /redis/flush`: Bezbedno prazni aktivnu Redis bazu (`flushdb()`) prema parametrima konekcije iz `.env` kako bi se resetovalo stanje za čist početak rada.

---

## 🔒 Autentifikacija i Zaštita (`backend/core/auth.py`)

*   **JWT Tokeni**: Tokeni se kreiraju pomoću biblioteke `pyjwt` sa `HS256` algoritmom. U payload tokena se upisuje ID korisnika (`sub`) i vreme isteka (`exp`).
*   **Dependency Injection**: Pomoću FastAPI `Depends(oauth2_scheme)` funkcija `get_current_user` proverava prisustvo i validnost tokena za svaku rutu koja zahteva zaštitu. Ako je token nevalidan ili istekao, FastAPI automatski vraća status `401 Unauthorized`.
*   **Rate Limiting**: Integrisan je `slowapi` koji koristi Redis backend za zaštitu API endpoint-a od DDoS napada i zloupotrebe. Osetljive rute poput registracije i TTS preview-a imaju stroge limite (npr. 5 zahteva po satu za analizu videa, 30 zahteva po minuti za pojedinačni TTS).

---

## 💾 Baza Podataka i ORM (`backend/core/database.py`, `models.py`)

PostgreSQL baza podataka se mapira preko **SQLAlchemy** biblioteke.
*   **Konekciono stablo (Pool)**: Konfigurisano je da izdrži konkurentne zahteve sa `pool_size=10` i `max_overflow=20`. Parametar `pool_pre_ping=True` osigurava da se neaktivne konekcije automatski osveže pre slanja SQL upita.
*   **Modeli**:
    *   `User`: email, password_hash, created_at, relacije sa projektima.
    *   `Project`: Status projekta (`empty`, `analyzing`, `ready`, `completed`), S3 ključevi za originalni video, vokale, instrumental, vizuelne frejm-ove, miksovani audio i finalni video.
    *   `Segment`: Start i end vreme, originalni i prevedeni tekst, jačina zvuka (`volume`), brzina (`speed`), visina (`pitch`), stišavanje muzike (`bg_volume`), tts_duration i S3 ključ za sintetizovani wav fajl. Primarni ključ je kompozitni: `(project_id, segment_id)`.
    *   `Glossary`: Rečnik specifičnih termina koji korisnik može definisati za prevođenje i lekturu.

---

## ⚡ Asinhrona Orkestracija (Celery + Redis Broker)

Pošto AI operacije mogu trajati od nekoliko desetina sekundi do nekoliko minuta, one se ne mogu izvršavati unutar HTTP zahteva.
*   **Celery**: Pokreće se kao zaseban daemon proces na VPS-u. FastAPI koristi `.delay()` metodu da pošalje zadatak u Redis red. Celery radnik preuzima zadatak, periodično ažurira progres preko `update_state(state='PROGRESS', meta=...)` i upisuje finalne rezultate.
*   **Redis Nacrti (Drafts)**: Tokom brze pretrage i klijentskog polling-a, učitavanje iz baze podataka može biti sporo. Zato se kompletan JSON objekat sa segmentima čuva u Redisu pod ključem `project:{project_id}:draft`. Svi asinhroni zadaci i API čitaju/pišu u ovaj draft radi maksimalne brzine, a na kraju se vrši sinhronizacija sa PostgreSQL-om.
*   **Izolacija radnog prostora po zadatku (Task Workspace Isolation)**:
    Kako konkurentni Celery zadaci ne bi gazili fajlove jedni drugima na disku, Celery radnik na početku izvršavanja zadatka kreira izolovani pod-direktorijum na osnovu `task_id` (npr. `temp_workspace/<task_id>`). Privremeno preusmerava `settings.TEMP_WORKSPACE` na ovaj direktorijum, a na kraju obrade (bilo uspešne ili neuspešne, kroz `finally` blok) bezbedno briše ceo privremeni direktorijum i vraća podrazumevani workspace. Finalni video i audio se prethodno premeštaju u korenski `temp_workspace` kako bi ostali dostupni za preuzimanje.
*   **Paralelna ekstrakcija vizuelnog konteksta**:
    Kako bi se ubrzala Faza 1 obrade, pokretanje FFmpeg ekstrakcije i upload ključnih frejmova na MinIO se prebacuje u pozadinsku nit (`threading.Thread`) odmah nakon preuzimanja videa. Glavna nit Celery zadatka nastavlja sa Demucs separacijom i transkripcijom, a na početku Faze 4 se samo poziva `.join()` na pozadinskoj niti. Time se vreme generisanja vizuelnog konteksta drastično smanjuje.

---

## 🛠️ Konfiguracione opcije i prosljeđivanje na Modal (`backend/core/config.py`)

Uvedeni su opcioni prekidači u `.env` i bekenu:
- `DISABLE_OPENVOICE` (podrazumevano `False`): Ako je postavljeno na `True`, pri sintezi se preskače prenos boje glasa i koristi se čist Piper Marko glas.
- `DISABLE_ENHANCE` (podrazumevano `False`): Ako je `True`, preskače se korak zvučnog poboljšanja preko Resemble Enhance modela.

Ove opcije se čitaju preko `settings` i prenose u JSON payload-u prilikom svakog API poziva ka Modal TTS engine-u.

---

## 🎙️ Hot-Patching / Splicing Mehanizam

Najveći tehnički izazov u realtime DAW sistemima je kako korisniku omogućiti da čuje izmenu prevoda na vremenskoj liniji bez čekanja da se ponovo izgeneriše ceo audio. Ovo je rešeno mehanizmom **Hot-Patching-a**:

1.  Korisnik izmeni tekst segmenta #5 i pritisne Space.
2.  Frontend šalje `POST /api/v1/project/{project_id}/segment/5/tts` sa novim tekstom i parametrima.
3.  Backend proverava da li je u pitanju brza korekcija parametara zvuka (`is_fast_adjust`):
    *   Ako korisnik nije promenio tekst i model glasa, već samo jačinu, brzinu ili visinu tona, sistem preskače skupu sintezu na Modalu.
    *   Preuzima sirovi audio tog segmenta (`tts_raw_5.wav`) sa S3 (ili iz lokalnog keša).
    *   Primenjuje FFmpeg filtere na sirovi audio i pravi modifikovani fajl.
4.  Ako se tekst ili glas promenio, poziva se Modal TTS radnik koji generiše nov sirov audio u roku od 100ms.
5.  Nakon dobijanja modifikovanog segmenta, backend preuzima kompletnu audio traku vokala celog videa (`dubbed_audio.wav`).
6.  Koristeći biblioteku **pydub**, backend seče originalnu traku vokala na tačnoj poziciji segmenta:
    ```python
    start_ms = int(db_seg.start * 1000)
    old_duration_ms = int(db_seg.tts_duration * 1000)
    
    part1 = full_audio[:start_ms]
    part2 = AudioSegment.silent(duration=old_duration_ms) # Brišemo stari glas
    part3 = full_audio[start_ms + old_duration_ms:]
    
    temp_audio = part1 + part2 + part3
    full_audio = temp_audio.overlay(new_segment_audio, position=start_ms) # Ulepljujemo novi
    ```
7.  Novi spajani fajl se otprema na MinIO S3 pod ključem `dubbed_audio.wav` i osvežava u klijentu bez cache-buster modifikacija (kako se ne bi narušio potpis presigned URL-a).
