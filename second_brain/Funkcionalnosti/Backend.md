# Backend Dokumentacija (FastAPI)

Ovaj dokument pruža detaljan pregled FastAPI serverske aplikacije, autentifikacionih protokola, pozadinske Celery infrastrukture i bezbednosnih mera primenjenih na backendu platforme **sinhronizuj.me**.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Arhitektura_Sistema]]
*   [[Baza_Podataka]]
*   [[Audio_i_Video_Procesiranje]]
*   [[Docker_i_Infrastruktura]]

---

## 1. FastAPI Web Server

FastAPI je primarni web server zadužen za API Gateway, validaciju preko Pydantic-a i asinhroni rad.

### 1.1. Struktura API Ruta
Glavna startna tačka je [main.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/main.py) koji služi kao orkestrator (registruje middleware, slowapi limiter, static mounts i rutere). API rute su modularno podeljene u paketu `backend/routes/`:

*   **Autentifikacija (`routes/auth.py`)**:
    *   `POST /api/v1/auth/register`: Registracija korisnika (podložna odobrenju sa waitlist-a).
    *   `POST /api/v1/auth/login`: Prijavljivanje korisnika, vraća JWT token.
    *   `GET /api/v1/auth/me`: Podaci o trenutnom korisniku.
    *   `POST /api/v1/auth/logout`: Odjavljivanje korisnika uz upis tokena u Redis blocklist.
*   **Waitlist (`routes/system.py` za waitlist i status)**:
    *   `POST /api/v1/waitlist`: Prijava email-a u zatvorenu betu. Koristi rate-limiting.
    *   `GET /api/v1/status/{task_id}`: Provera statusa asinhronog Celery zadatka u realnom vremenu.
*   **Projekti i Storage (`routes/projects.py`)**:
    *   `GET /api/v1/storage/upload_url`: Generiše pre-potpisani URL za direktan S3 upload.
    *   `GET /api/v1/projects`: Listanje svih projekata ulogovanog korisnika.
    *   `POST /api/v1/project`: Kreiranje novog praznog projekta.
    *   `GET /api/v1/project/{project_id}`: Učitavanje nacrta i svih segmenata projekta.
    *   `POST /api/v1/project/{project_id}/save`: Snimanje izmena na segmentima.
    *   `DELETE /api/v1/project/{project_id}`: Kaskadno brisanje projekta i povezanih S3 resursa.
    *   `POST /api/v1/process-video`: Inicijalizuje Celery task za analizu.
*   **Segmenti i Zvuk (`routes/segments.py`)**:
    *   `POST /api/v1/project/{project_id}/segment/{segment_id}/tts`: Generiše srpski TTS/OpenVoice audio za segment. Vidi [[Audio_i_Video_Procesiranje]].
    *   `POST /api/v1/project/{project_id}/segment/{segment_id}/shorten`: Poziva Modal Lektor za skraćivanje teksta segmenta.
    *   `POST /api/v1/project/{project_id}/generate-all-tts`: Pokreće sintezu za sve segmente.
    *   `POST /api/v1/project/{project_id}/render`: Inicijalizuje Celery task za finalno renderovanje videa.
*   **Sistemske rute (`routes/system.py`)**:
    *   `GET /api/v1/hw-stats`: Vraća iskorišćenost resursa host VPS-a (admin only).
    *   `GET /api/v1/modal-status`: Proverava status serverless radnika na Modalu (admin only).
    *   `POST /api/v1/warmup`: Podizanje Modal radnika unapred (admin only).

### 1.2. Zaštićene Admin Rute
Admin rute zahtevaju JWT token sa `is_admin=True` privilegijom i zaštićene su zavisnošću `get_current_admin_user` u [auth.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/core/auth.py):

*   `GET /api/v1/admin/stats`: Vraća zbirne metrike baze podataka.
*   `GET /api/v1/admin/waitlist`: Lista sve prijava za zatvorenu betu.
*   `POST /api/v1/admin/waitlist/{waitlist_id}/approve` / `reject`: Odobravanje ili odbijanje prijava.
*   `GET /api/v1/admin/users`: Pregled svih registrovanih korisnika.
*   `POST /api/v1/admin/users/{user_id}/toggle-admin`: Dodela/oduzimanje admin uloge.
*   `GET /api/v1/admin/projects`: Detaljan uvid u sve projekte na sistemu.
*   `GET /api/v1/admin/project/{project_id}`: Uvid u resurse projekta i pretraga logova radnika.

---

## 2. JWT Autentifikacija

Autentifikacija se zasniva na OAuth2 standardu sa JWT (JSON Web Tokens) nosiocem (Bearer):
*   **Generisanje tokena**: Prilikom uspešnog logovanja, kreira se token sa korisničkim ID-em i trajanjem od 60 minuta. Heširanje lozinki se vrši pomoću `passlib` sa `bcrypt` algoritmom.
*   **Verifikacija**: Svaki zaštićeni endpoint presreće zaglavlje `Authorization: Bearer <token>`, dekoduje potpis pomoću tajnog ključa (`SECRET_KEY` iz `.env` fajla) i proverava postojanje korisnika u bazi.

---

## 3. Celery i Redis Infrastruktura za Asinhrone Zadatke

Za zadatke koji traju duže od nekoliko sekundi (obrada, renderovanje) koristi se Celery asinhroni red.

*   **Broker**: **Redis** kontejner se koristi kao prenosilac poruka (broker) i skladište rezultata.
*   **Konfiguracija**: Definisana u [celery_app.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/celery_app.py). Celery radnik se pokreće kao zaseban proces koji uvozi zadatke iz [tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py).
*   **Orkestracija i Greške**: Celery zadaci ažuriraju svoj progres u Redis-u, koji klijent povlači preko `/api/v1/status/{task_id}` rute. U slučaju pada Modal radnika, Celery zadatak hvata izuzetke i menja status projekta u bazi na `failed`.

---

## 4. Bezbednosni Okvir i Zaštita

Zaštita produkcionog VPS servera implementirana je kroz više slojeva:

1.  **Nginx SSL Reverse Proxy**:
    Nginx preusmerava javni saobraćaj sa portova 80 (HTTP) i 443 (HTTPS) na FastAPI na portu 8000 i Vite na 5173. SSL sertifikati su generisani preko Let's Encrypt-a.
2.  **UFW Firewall**:
    Mrežni firewall na serveru dozvoljava samo portove `80`, `443` i `22` (SSH). Interni portovi za Redis, PostgreSQL i Celery su zatvoreni za spoljni saobraćaj.
3.  **Rate Limiting (SlowAPI)**:
    U FastAPI je integrisan `SlowAPI` limiter zasnovan na Redis-u:
    *   Prijava na waitlist: Ograničena na 5 zahteva po minuti po IP adresi.
    *   Login i Register: Ograničeni na 10 zahteva po minuti po IP adresi.
4.  **Cloudflare Proxy**:
    Javni DNS zapisi za `sinhronizuj.me` prolaze kroz Cloudflare proxy radi sakrivanja IP adrese VPS-a, DDoS zaštite i keširanja.
5.  **Sentry Monitoring**:
    U FastAPI i Celery radnike je integrisan Sentry SDK za automatsku prijavu neočekivanih grešaka u realnom vremenu.

---

## 5. Backend Testiranje

Backend koristi **pytest** i **httpx** za integraciono i API testiranje.

*   **Lokalna baza za testove**: Testovi su konfigurisani u [conftest.py](file:///home/gruya/Projektri/sinhronizuj.me/tests/conftest.py) da prvenstveno koriste PostgreSQL test bazu (kako bi se vernije testirali UUID i JSON tipovi), sa SQLite-om kao automatskim fallback-om.
*   **Struktura testova**: Nalazi se u folderu `tests/` i pokriva autentifikaciju, rute za projekte, administrativne komande, A/V spajanje (merger) sa prigušivanjem i active speaker detekciju.
*   **Pokretanje testova**:
    ```bash
    pytest tests/
    ```
    CI pipeline je konfigurisan u [.github/workflows/backend-ci.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/backend-ci.yml).
