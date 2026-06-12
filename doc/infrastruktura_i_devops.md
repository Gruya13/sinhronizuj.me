# Infrastruktura i DevOps (sinhronizuj.me)

Ovaj dokument pruža detaljan pregled produkcione i razvojne infrastrukture, Docker okruženja, automatizovanog backup sistema i CI/CD cevovoda za platformu **sinhronizuj.me**.

---

## 1. Specifikacija VPS Servera i Mrežna Topologija

Aplikacija je hostovana na Hetzner Cloud VPS serverima (Falkenstein lokacija), podeljenim na dva izolovana okruženja:

### 1.1. Razvojno okruženje (Development VPS)
*   **IP Adresa**: `116.202.103.35`
*   **Namena**: Testiranje novih funkcionalnosti pre puštanja u produkciju.
*   **Grana**: Povezano sa `development` granom na GitHub-u. Automatski deploy se vrši nakon svakog uspešnog CI testa.

### 1.2. Produkciono okruženje (Production VPS)
*   **IP Adresa**: `178.104.214.78`
*   **Namena**: Aktivna verzija aplikacije za krajnje korisnike.
*   **Grana**: Povezano sa `main` granom na GitHub-u. Zahteva prolazak celokupnog CI/CD ciklusa i manuelno odobrenje/tagovanje pre puštanja.

---

## 2. Docker i Docker Compose Lokalno Okruženje

Lokalni razvoj i servisi na serverima su kontejnerizovani pomoću Docker-a radi konzistentnosti okruženja. U nastavku je definicija servisa u [docker-compose.yml](file:///home/gruya/Projektri/sinhronizuj.me/docker-compose.yml):

```yaml
version: '3.8'

services:
  # 1. Baza Podataka (PostgreSQL)
  db:
    image: postgres:15-alpine
    container_name: sinhronizuj-db
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432" # Izložen port za lakše migracije sa host mašine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - sinhronizuj-net

  # 2. Redis (Broker za Celery i Cache)
  redis:
    image: redis:7-alpine
    container_name: sinhronizuj-redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - sinhronizuj-net

  # 3. FastAPI Web Server (API)
  api:
    build: .
    container_name: sinhronizuj-api
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      # ... ostale konfiguracione promenljive
    depends_on:
      - db
      - redis
    networks:
      - sinhronizuj-net

  # 4. Celery Radnik (Asinhroni poslovi)
  celery:
    build: .
    container_name: sinhronizuj-celery
    command: celery -A backend.worker.celery_app worker --loglevel=info
    restart: always
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    networks:
      - sinhronizuj-net

volumes:
  postgres_data:
  redis_data:

networks:
  sinhronizuj-net:
    driver: bridge
```

---

## 3. Automatski Backup Sistem sa Rotacijom

Za sprečavanje gubitka podataka u produkciji, postavljen je automatski backup sistem koji se izvršava svake noći u 02:00h preko cron posla na VPS-u:

1.  **Dampovanje baze**: Izvršava se komanda `pg_dump` unutar `sinhronizuj-db` kontejnera kako bi se dobio SQL fajl sa kompletnom šemom i podacima.
2.  **Kompresija**: SQL damp i lokalni korisnički fajlovi (koji nisu na S3) se pakuju u `.tar.gz` arhivu.
3.  **Otpremanje na S3 (MinIO)**: Arhiva se otprema na zaseban privatni S3 bucket na MinIO skladištu.
4.  **Rotacija od 7 dana**: Skripta proverava datume kreiranja backupa na S3 i automatski briše sve arhive starije od 7 dana kako bi se optimizovao prostor na skladištu.

---

## 4. CI/CD GitHub Actions Cevovodi (Workflows)

Proces testiranja i isporuke je podeljen na tri specijalizovana YAML fajla u direktorijumu `.github/workflows/`:

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
                 - SSH povezivanje na Hetzner VPS
                 - Povlačenje koda (git pull)
                 - Pokretanje docker-compose build/up
                 - Alembic migracije
```

### 4.1. Backend Integracioni Testovi ([backend-ci.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/backend-ci.yml))
*   **Triger**: Push ili Pull Request na grane `main` i `development`.
*   **Koraci**:
    1.  Podizanje Python 3.10 okruženja.
    2.  Instalacija zavisnosti iz `requirements.txt`.
    3.  Pokretanje `pytest` integracionih testova.

### 4.2. Frontend Testovi ([frontend-ci.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/frontend-ci.yml))
*   **Triger**: Push ili Pull Request na grane `main` i `development`.
*   **Koraci**:
    1.  Podizanje Node.js 18 okruženja.
    2.  Instalacija paketa preko `npm ci`.
    3.  Pokretanje unit testova komandom `npm run test:run` (pokreće Vitest u jednokratnom režimu).

### 4.3. Automatizovani Deployment ([deploy.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/deploy.yml))
*   **Mehanizam**: Koristi `needs: [backend-test, frontend-test]` i poziva ih preko `workflow_call` kako bi garantovao ispravnost aplikacije pre bilo kakve izmene na serveru.
*   **CD Logika**:
    *   Ukoliko je push na granu `development`, povezuje se preko SSH na **Development VPS (`116.202.103.35`)**.
    *   Ukoliko je push na granu `main`, povezuje se preko SSH na **Production VPS (`178.104.214.78`)**.
    *   Na serveru izvršava komandu osvežavanja kontejnera:
        ```bash
        git pull origin <grana>
        docker-compose up -d --build
        docker-compose exec -T api alembic upgrade head
        ```
