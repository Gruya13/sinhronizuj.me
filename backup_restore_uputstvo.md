# Uputstvo za Backup i Restore sistema "sinhronizuj.me"

Ovo uputstvo opisuje procedure za pravljenje rezervnih kopija (backup) i oporavak sistema (restore) za bazu podataka i S3 skladište (MinIO).

---

## 1. Šta se bekapuje?

Skripta za bekap automatski prikuplja i pakuje:
1. **PostgreSQL bazu podataka**: Kompletan dump šeme i podataka (koristi `pg_dump`).
2. **S3/MinIO skladište**: Sve originalne i obrađene datoteke (video, vokalne trake, pozadinska muzika, finalni videi) koje se nalaze u bucketu definisanom u `.env` (preskačući privremeni keš u `cache/` kako bi se uštedeo prostor).

---

## 2. Pokretanje Bekapa (Backup)

Za ručno pokretanje bekapa koristite pripremljenu skriptu `scripts/backup.sh`:

```bash
./scripts/backup.sh
```

### Detalji izvršavanja:
- Skripta učitava konfiguraciju direktno iz `.env` fajla u korenu projekta.
- Ako su Docker kontejneri pokrenuti, koristi se `docker compose exec` za kreiranje dump-a direktno unutar baze. U suprotnom, koristi se lokalni port forward za Postgres (port `5435`).
- Nakon dump-a baze, pokreće se Python skripta `scripts/backup_s3.py` koja koristi `boto3` za preuzimanje S3 fajlova i njihovo pakovanje u `tar.gz` arhivu.
- Na kraju se kreira jedinstveni kompresovani fajl sa vremenskim žigom u `backups/` folderu:
  `backups/backup_YYYYMMDD_HHMMSS.tar.gz`

---

## 3. Pokretanje Oporavka (Restore)

Za oporavak sistema iz bekapa, koristite skriptu `scripts/restore.sh`:

### A) Oporavak iz najnovijeg bekapa:
Ako ne prosledite argument, skripta će automatski uzeti najnoviji backup fajl iz `backups/` foldera:

```bash
./scripts/restore.sh
```

### B) Oporavak iz specifičnog bekapa:
Možete eksplicitno navesti putanju do arhive:

```bash
./scripts/restore.sh backups/backup_20260620_041500.tar.gz
```

### Detalji izvršavanja:
- Skripta raspakuje arhivu.
- Briše postojeću PostgreSQL bazu podataka i ponovo je kreira kako bi se osigurao čist uvoz podataka.
- Uvozi SQL dump u bazu podataka.
- Pokreće Python skriptu `scripts/restore_s3.py` koja proverava i kreira S3 bucket ukoliko ne postoji, a zatim otprema sve datoteke iz arhive na njihove originalne lokacije.

---

## 4. Periodično Izvršavanje (Cron Job)

Preporučuje se postavljanje cron job-a na VPS-u za automatski dnevni bekap.
Da biste dodali cron job koji pravi bekap svakog dana u 02:00 ujutru, pokrenite `crontab -e` i dodajte sledeću liniju:

```cron
0 2 * * * cd /home/gruya/Projektri/sinhronizuj.me && ./scripts/backup.sh >> /var/log/sinhronizuj_backup.log 2>&1
```
