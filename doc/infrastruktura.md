# 🖥️ Detaljna Dokumentacija Infrastrukture i Postavljanja

Infrastruktura platforme **Sinhronizuj.me** oslanja se na **Hetzner VPS** (Control Plane) za hosting core servisa i **Modal.com** (Compute Plane) za serverless GPU obradu.

---

## 🐋 1. Docker Compose Arhitektura (VPS)

Svi stateful servisi i orkestratori na Hetzner VPS-u se pokreću i izoluju pomoću **Docker Compose-a** (`docker-compose.yml`):

### Definisani Servisi:
1.  **FastAPI Server (`api`)**:
    *   *Kontejner*: `sinhronizuj-api`
    *   *Komanda*: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
    *   *Izloženi portovi*: `8000:8000`
    *   *Volume-i*: deli `/temp_workspace` i `/app` sa hostom kako bi FFmpeg mogao direktno da pristupa lokalnim video fajlovima tokom manipulacije.
2.  **Celery Radnik (`worker`)**:
    *   *Kontejner*: `sinhronizuj-worker`
    *   *Komanda*: `celery -A backend.worker.tasks worker --loglevel=info --concurrency=1`
    *   *Opis*: Konkurentnost je postavljena na 1 (`--concurrency=1`) jer su poslovi (FFmpeg rendering, normalizacija) procesorski intenzivni i zahtevaju sekvencijalnu obradu kako se VPS procesor ne bi preopteretio.
3.  **Celery Beat (`beat`)**:
    *   *Kontejner*: `sinhronizuj-beat`
    *   *Komanda*: `celery -A backend.worker.tasks beat --loglevel=info`
    *   *Opis*: Planira periodične pozadinske poslove i održava zdravlje keš sistema.
4.  **Redis Cache & Broker (`redis`)**:
    *   *Kontejner*: `sinhronizuj-redis`
    *   *Slika*: `redis:7-alpine`
    *   *Pristup*: Zaštićen lozinkom (`--requirepass ${REDIS_PASSWORD}`) na portu `6379`.
5.  **PostgreSQL Baza podataka (`db`)**:
    *   *Kontejner*: `sinhronizuj-db`
    *   *Slika*: `postgres:15-alpine`
    *   *Volume-i*: `pgdata` volume mapiran na `/var/lib/postgresql/data` radi perzistencije podataka.

---

## 🌐 2. MinIO S3 Object Storage

Za čuvanje i serviranje svih medijskih datoteka (engleski video, vokali, instrumental, tts wav segmenti, finalni mp4) koristi se **MinIO**, samohostovani S3-kompatibilan servis konfigurisan na VPS-u:
*   **Endpoint**: `178.104.214.78:9000`
*   **Buckets**:
    *   `uploads`: Svi radni mediji projekata.
    *   `backups`: Istorijske SQL baze podataka.
*   **Pravilo Pristupa**: Svi resursi su u privatnom režimu. Klijent i radnici im pristupaju isključivo preko privremenih **Presigned URL-ova** koje API server generiše pomoću `boto3` biblioteke (rok važenja 24h).

---

## 🔒 3. Sigurnost i Mrežna Izolacija

1.  **Zatvoreni Portovi (UFW Firewall)**:
    *   Na Hetzner VPS-u aktiviran je firewall koji dozvoljava isključivo saobraćaj na portovima `80` (HTTP), `443` (HTTPS) i `22` (SSH).
    *   Portovi za bazu podataka (`5432`), Redis (`6379`) i internu MinIO konzolu nisu izloženi javno.
2.  **Docker Mreža (Isolated Bridge Network)**:
    *   Svis kontejneri se nalaze unutar default Docker bridge mreže, što im omogućava da komuniciraju koristeći interne nazive servisa (npr. API se povezuje na bazu preko `postgresql://sinhronizuj_user:pass@db:5432/sinhronizuj_db` umesto spoljne IP adrese).
3.  **Nginx Reverse Proxy i SSL**:
    *   Nginx je konfigurisan na hostu da sluša portove `80` i `443`, obezbeđuje SSL enkripciju (sertifikati generisani preko Let's Encrypt / Certbot) i prosleđuje zahteve FastAPI serveru na port `8000`.

---

## 💾 4. Automatizovani Backup Sistem

Za prevenciju gubljenja podataka, postavljen je cron posao koji vrši backup celokupne PostgreSQL baze svake noći u 02:00.

### Princip rada backup skripte (`infra/backup.py` & `infra/backup.sh`):
1.  **Izvoz (Dump)**: Poziva se `docker exec` komanda koja unutar kontejnera `sinhronizuj-db` izvršava `pg_dump` alat.
2.  **Kompresija**: Izvezeni SQL fajl se kompresuje pomoću `gzip` alata u `/tmp` direktorijumu.
3.  **Upload na S3**: Povezuje se na MinIO S3 i otprema `.sql.gz` arhivu u namenski bucket `backups`.
4.  **Uklanjanje lokalnog traga**: Briše se privremeni fajl iz `/tmp`.
5.  **Rotacija (7 dana)**: Skripta preuzima listu svih bekapa sa MinIO-a i briše sve zapise koji su modifikovani pre više od 7 dana, čime se sprečava nekontrolisano trošenje diskovnog prostora.

### Cron podešavanje na VPS-u:
```bash
# Otvoriti crontab preko: crontab -e
# Upisati liniju za izvršavanje svake noći u 02:00
0 2 * * * /home/gruya/Projektri/sinhronizuj.me/infra/backup.sh >> /var/log/sinhronizuj_backup.log 2>&1
```
