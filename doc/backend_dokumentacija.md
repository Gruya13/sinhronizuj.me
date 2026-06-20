# Dokumentacija Backend Sloja (sinhronizuj.me)

Ovaj dokument pruža detaljan pregled FastAPI serverske aplikacije, autentifikacionih protokola, pozadinske Celery infrastrukture i bezbednosnih mera primenjenih na backendu platforme **sinhronizuj.me**.

---

## 1. FastAPI Web Server

FastAPI je izabran kao primarni web server zbog svojih izuzetnih performansi (zasnovan na ASGI i Uvicorn-u), automatske validacije podataka preko Pydantic-a i asinhronog rada.

### 1.1. Struktura API Ruta
Glavna startna tačka je [backend/main.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/main.py) koji sada služi isključivo kao orkestrator (registruje middleware, slowapi limiter, static mounts i rutere). API rute su modularno podeljene u paketu `backend/routes/` i registrovane u aplikaciji:

*   **Autentifikacija (`routes/auth.py`)**:
    *   `POST /api/v1/auth/register`: Registracija korisnika (podložna odobrenju sa waitlist-a).
    *   `POST /api/v1/auth/login`: Prijavljivanje korisnika, vraća JWT token.
    *   `GET /api/v1/auth/me`: Podaci o trenutnom korisniku.
    *   `POST /api/v1/auth/logout`: Odjavljivanje korisnika uz upis tokena u Redis blocklist.
*   **Waitlist (`routes/system.py` za waitlist i status)**:
    *   `POST /api/v1/waitlist`: Prijava email-a u zatvorenu betu. Koristi rate-limiting.
    *   `GET /api/v1/status/{task_id}`: Provera statusa asinhronog Celery zadatka u realnom vremenu.
*   **Projekti i Storage (`routes/projects.py`)**:
    *   `GET /api/v1/storage/upload_url`: Generiše pre-potpisani URL za direktan upload video fajlova na S3 skladište (sa server-side UUID generisanjem i proverom vlasništva).
    *   `GET /api/v1/projects`: Listanje svih projekata ulogovanog korisnika.
    *   `POST /api/v1/project`: Kreiranje novog praznog projekta.
    *   `GET /api/v1/project/{project_id}`: Učitavanje nacrta i svih segmenata projekta.
    *   `POST /api/v1/project/{project_id}/save`: Snimanje izmena na segmentima.
    *   `DELETE /api/v1/project/{project_id}`: Kaskadno brisanje projekta i povezanih S3 resursa.
    *   `POST /api/v1/process-video`: Inicijalizuje Celery task za analizu (sa proverom vlasništva, video formata, trajanja i dnevnih korisničkih kvota).
*   **Segmenti i Zvuk (`routes/segments.py`)**:
    *   `POST /api/v1/project/{project_id}/segment/{segment_id}/tts`: Generiše srpski TTS/OpenVoice audio za specifičan segment.
    *   `POST /api/v1/project/{project_id}/segment/{segment_id}/shorten`: Poziva Modal Lektor za skraćivanje teksta segmenta.
    *   `POST /api/v1/project/{project_id}/generate-all-tts`: Pokreće sintezu za sve segmente u projektu.
    *   `POST /api/v1/project/{project_id}/render`: Inicijalizuje Celery task za finalno renderovanje videa.
*   **Sistemske rute (`routes/system.py`)**:
    *   `GET /api/v1/hw-stats`: Vraća iskorišćenost resursa host VPS-a (samo za administratora).
    *   `GET /api/v1/modal-status`: Proverava status serverless radnika na Modalu (samo za admina).
    *   `POST /api/v1/warmup`: Podizanje Modal radnika unapred (samo za admina).


### 1.2. Zaštićene Admin Rute
Admin rute zahtevaju JWT token sa `is_admin=True` privilegijom i zaštićene su zavisnošću `get_current_admin_user` u [backend/core/auth.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/core/auth.py):

*   `GET /api/v1/admin/stats`: Vraća zbirne metrike baze podataka (broj korisnika, projekata, waitlist-a na čekanju).
*   `GET /api/v1/admin/waitlist`: Lista sve prijave za zatvorenu betu.
*   `POST /api/v1/admin/waitlist/{waitlist_id}/approve` / `reject`: Odobravanje ili odbijanje prijava. Odobrenim korisnicima se dozvoljava registracija.
*   `GET /api/v1/admin/users`: Pregled svih registrovanih korisnika.
*   `POST /api/v1/admin/users/{user_id}/toggle-admin`: Dodela ili oduzimanje administratorske uloge.
*   `GET /api/v1/admin/projects`: Detaljan uvid u sve projekte na sistemu.
*   `GET /api/v1/admin/project/{project_id}`: Uvid u resurse projekta i pretraga sistemskih logova radnika za taj projekat.

---

## 2. JWT Autentifikacija

Autentifikacija se zasniva na OAuth2 standardu sa JWT (JSON Web Tokens) nosiocem (Bearer):
*   **Generisanje tokena**: Prilikom uspešnog logovanja, kreira se token sa korisničkim ID-em i trajanjem od 60 minuta (konfigurisano kroz `ACCESS_TOKEN_EXPIRE_MINUTES`). Heširanje lozinki se vrši pomoću `passlib` sa `bcrypt` algoritmom.
*   **Verifikacija**: Svaki zaštićeni endpoint presreće zaglavlje `Authorization: Bearer <token>`, dekoduje potpis pomoću tajnog ključa (`SECRET_KEY` iz `.env` fajla) i proverava postojanje korisnika u bazi.

---

## 3. Celery i Redis Infrastruktura za Asinhrone Zadatke

Za zadatke koji traju duže od nekoliko sekundi koristi se **Celery** asinhroni red (queue) kako se ne bi blokirala nit API servera.

*   **Broker**: **Redis** kontejner se koristi kao prenosilac poruka (broker) i skladište rezultata (result backend).
*   **Konfiguracija**: Definisana u [backend/worker/celery_app.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/celery_app.py). Celery radnik se pokreće kao zaseban proces koji uvozi zadatke iz [backend/worker/tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py).
*   **Orkestracija i Greške**: Celery zadaci imaju ugrađene mehanizme za praćenje progresa (putem ažuriranja meta-podataka zadatka u Redis-u) koje klijent povlači preko `/api/v1/status/{task_id}` rute. U slučaju pada Modal radnika, Celery zadatak hvata izuzetke i bezbedno menja status projekta u bazi na `failed` kako klijent ne bi ostao u beskonačnom čekanju.

---

## 4. Bezbednosni Okvir i Zaštita

Zaštita produkcionog VPS servera implementirana je kroz više slojeva:

1.  **Nginx SSL Reverse Proxy**:
    Nginx služi kao ulazna tačka na VPS serveru. Preusmerava javni saobraćaj sa portova 80 (HTTP) i 443 (HTTPS) na interne portove aplikacije (npr. FastAPI na portu 8000, Vite na 5173). SSL sertifikati su generisani preko Let's Encrypt-a.
2.  **UFW Firewall**:
    Mrežni firewall na serveru je strogo konfigurisan. Dozvoljeni su samo portovi `80`, `443` i `22` (za SSH pristup sa specifičnih IP adresa). Interni portovi za Redis, PostgreSQL i Celery su blokirani za spoljni saobraćaj i dostupni su isključivo unutar Docker mreže.
3.  **Rate Limiting (SlowAPI)**:
    U FastAPI je integrisan `SlowAPI` limiter zasnovan na Redis-u. Štiti osetljive rute od brute-force napada:
    *   Prijava na waitlist: Ograničena na 5 zahteva po minuti po IP adresi.
    *   Login i Register: Ograničeni na 10 zahteva po minuti po IP adresi.
4.  **Cloudflare Proxy**:
    Javni DNS zapisi za `sinhronizuj.me` prolaze kroz Cloudflare proxy. Ovo sakriva stvarnu IP adresu VPS-a, pruža automatsku DDoS zaštitu i omogućava keširanje statičkih frontend resursa na Cloudflare ivici (edge).
5.  **Sentry Monitoring i Izveštavanje o Greškama**:
    U FastAPI i Celery radnike je integrisan Sentry SDK. Ukoliko se u konfiguraciji definiše `SENTRY_DSN` ključ, sve neočekivane greške, izuzeci (500 internal server error) i kritični logovi se automatski prijavljuju i grupišu na Sentry kontrolnoj tabli u realnom vremenu, što olakšava i ubrzava otklanjanje problema u produkciji.

---


## 5. Backend Testiranje

Backend koristi **pytest** i **httpx** za integraciono i API testiranje.

*   **Lokalna baza za testove**: Testovi su konfigurisani u [tests/conftest.py](file:///home/gruya/Projektri/sinhronizuj.me/tests/conftest.py) da koriste PostgreSQL test bazu umesto SQLite-a. Ovo omogućava verodostojno testiranje UUID kolona i JSON tipova podataka, dok SQLite služi kao automatski fallback ukoliko Postgres nije dostupan.
*   **Struktura testova**: Smešteni su u direktorijum `tests/` i pokrivaju autentifikaciju, rute za projekte, administrativne komande, kao i složene integracione provere (A/V merger sa ducking-om, segmentne kolizije, active speaker detekciju i selektivni lipsync).
*   **Pokretanje testova**:
    ```bash
    pytest tests/
    ```
    Svi testovi (30 integracionih i golden testova) uspešno prolaze i automatski se pokreću u CI pipeline-u kroz [.github/workflows/backend-ci.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/backend-ci.yml).

