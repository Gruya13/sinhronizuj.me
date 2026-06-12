# Infrastruktura i DevOps (sinhronizuj.me)

Ovaj dokument pruža detaljan pregled produkcione i razvojne infrastrukture, Docker okruženja, optimizovanog backup sistema i modernizovanog CI/CD cevovoda zasnovanog na GitHub Container Registry (GHCR) za platformu **sinhronizuj.me**.

---

## 1. Specifikacija VPS Servera i Mrežna Topologija

Aplikacija je hostovana na Hetzner Cloud VPS serverima (Falkenstein lokacija), podeljenim na dva izolovana okruženja:

### 1.1. Razvojno okruženje (Development VPS)
*   **IP Adresa**: `116.202.103.35`
*   **Namena**: Testiranje novih funkcionalnosti pre puštanja u produkciju.
*   **Grana**: Povezano sa `development` granom na GitHub-u. Automatski deploy se vrši nakon uspešnog CI testa i build-a slika na GHCR.

### 1.2. Produkciono okruženje (Production VPS)
*   **IP Adresa**: `178.104.214.78`
*   **Namena**: Aktivna verzija aplikacije za krajnje korisnike.
*   **Grana**: Povezano sa `main` granom na GitHub-u. Zahteva prolazak celokupnog CI/CD ciklusa i manuelno odobrenje/tagovanje pre puštanja.

---

## 2. Docker i Docker Compose Okruženje

Sistem je u potpunosti kontejnerizovan pomoću Docker-a radi konzistentnosti razvojnog, staging i produkcionog okruženja.

### 2.1. Lokalno Razvojno Okruženje ([docker-compose.yml](file:///home/gruya/Projektri/sinhronizuj.me/docker-compose.yml))
Lokalni compose podiže bazu (`db`), Redis, Celery radnika, beat i FastAPI API. Koristi lokalni build i mount-uje kod u realnom vremenu radi lakšeg razvoja.

### 2.2. Produkciono Okruženje ([docker-compose.prod.yml](file:///home/gruya/Projektri/sinhronizuj.me/infra/hetzner/docker-compose.prod.yml))
Produkciono okruženje je optimizovano za visoke performanse, bezbednost i monitoring:
*   **Bezbednost portova**: Portovi baze (`5432`) i Redis-a (`6379`) su uklonjeni i nisu izloženi internetu. Dostupni su isključivo unutar izolovane Docker mreže (`sinhronizuj-net`).
*   **Healthcheck-ovi**: Postgres i Redis imaju ugrađene zdravstvene provere, a ostali servisi zavise od njih preko `condition: service_healthy`.
*   **Ograničenje resursa**: Kontejnerima su definisani limiti za procesorsko vreme i memoriju (1 CPU / 1G RAM za API, 2 CPU / 2G RAM za teške AI Celery radnike) kako bi se osigurala stabilnost host VPS-a.
*   **Log rotacija**: Konfigurisana je log rotacija na nivou Docker-a (maksimalno 3 fajla po 10MB) kako logovi ne bi popunili hard disk servera.
*   **Kontejnerizovan Frontend**: Klijentska React/Vite aplikacija se servira kroz laganu Nginx instancu unutar Docker kontejnera na portu `3000`.

---

## 3. Automatski Backup Sistem sa Rotacijom

Za sprečavanje gubitka podataka, postavljen je automatski backup sistem koji se izvršava svake noći u 02:00h preko cron posla na VPS-u:

1.  **Dampovanje baze**: Izvršava se komanda `pg_dump` unutar `sinhronizuj-db` kontejnera kako bi se dobio kompresovani SQL fajl sa kompletnom šemom i podacima.
2.  **Otpremanje na S3**: Skripta [backup.py](file:///home/gruya/Projektri/sinhronizuj.me/infra/backup.py) otprema arhivu na zasebno S3 kompatibilno skladište (npr. eksterni MinIO ili AWS S3).
3.  **Rotacija od 7 dana**: Skripta proverava datume kreiranja backupa na S3 i automatski briše sve arhive starije od 7 dana kako bi se optimizovao prostor na skladištu.

---

## 4. CI/CD GitHub Actions Cevovodi (Workflows)

Proces testiranja, izgradnje slika i isporuke je automatizovan i podeljen na četiri specijalizovana YAML fajla u direktorijumu `.github/workflows/`:

```
                    [Korisnički Push na GitHub]
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
           [backend-ci.yml]              [frontend-ci.yml]
           - Pokretanje Pytest           - Instalacija node_modules
           - Linting (Ruff/Black)        - Pokretanje Vitest testova
                  │                             │
                  └──────────────┬──────────────┘
                                 ▼
                         [deploy.yml] (workflow_call)
                         - Čeka uspešan prolazak oba CI
                         - Build-uje i šalje slike na GHCR
                         - SSH povezivanje na Hetzner VPS
                         - docker compose pull (GHCR slike)
                         - docker compose up -d (brzi deploy)
                         - Alembic migracije
```

### 4.1. Backend Testovi ([backend-ci.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/backend-ci.yml))
*   **Triger**: Push ili Pull Request na grane `main` i `development`.
*   **Koraci**: Podizanje Python okruženja, instalacija zavisnosti, Ruff linting, i pokretanje integracionih testova preko `pytest`. Ignoriše pomoćne skripte zahvaljujući [pytest.ini](file:///home/gruya/Projektri/sinhronizuj.me/pytest.ini) konfiguraciji.

### 4.2. Frontend Testovi ([frontend-ci.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/frontend-ci.yml))
*   **Triger**: Push ili Pull Request na grane `main` i `development`.
*   **Koraci**: Podizanje Node.js okruženja, instalacija paketa preko `npm ci`, pokretanje unit testova komandom `npm run test:run`, i pokretanje E2E Playwright testova.

### 4.3. Automatizovani Deployment ([deploy.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/deploy.yml))
*   **Mehanizam**: Pokreće se nakon uspešnog prolaska testova.
*   **Logika Izgradnje**:
    *   Gradi Docker slike za backend (FastAPI) i frontend (React + Nginx) na GitHub Actions trkaču.
    *   Radi push slika na **GitHub Container Registry (GHCR)** pod tagovima grane (npr. `development` ili `latest`).
*   **CD Logika (Hetzner VPS)**:
    *   Povezuje se preko SSH na VPS.
    *   Radi `docker login ghcr.io` koristeći tajnu `GHCR_READ_TOKEN`.
    *   Radi `docker compose pull` da povuče pre-built slike sa GHCR-a na server.
    *   Radi `docker compose up -d` za brzu i bezbednu zamenu aktivnih kontejnera bez lokalnog opterećenja procesora.
    *   Izvršava Alembic migracije: `docker compose exec -T api alembic upgrade head`.

### 4.4. Generisanje Release Changelog-a ([release.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/release.yml))
*   **Triger**: Push na granu `main`.
*   **Koraci**: Automatski generiše oznaku verzije (tag na osnovu trenutnog datuma i vremena, npr. `v2026.06.12-0926`) i kreira GitHub Release sa automatski generisanim beleškama o izmenama (changelog).
