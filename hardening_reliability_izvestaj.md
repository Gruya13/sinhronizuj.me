# Izveštaj o ojačavanju pouzdanosti sistema (P1 Reliability) - "sinhronizuj.me"

Ovaj izveštaj detaljno prikazuje tehničke izmene koje su sprovedene u cilju ojačavanja pouzdanosti i otpornosti sistema na padove, čime je kompletirana **Faza 1 (P1 Reliability)**.

---

## 1. Redis Perzistencija
- **Opis**: Da bi se sprečio gubitak aktivnih Celery poslova pri neočekivanom restartu Redis kontejnera, konfigurisana je puna perzistencija.
- **Izmene**:
  - U [docker-compose.yml](file:///home/gruya/Projektri/sinhronizuj.me/docker-compose.yml) je dodat flag `--appendonly yes` (AOF - Append Only File) koji upisuje svaku promenu na disk.
  - Dodat je perzistentni Docker volume `redis_data` mapiran na `/data` unutar Redis kontejnera.
  - Postavljen je restart flag `restart: always` na Redis servisu.

---

## 2. State Machine za Poslove (Jobs Table)
- **Opis**: Uvedena je Postgres tabela za praćenje stanja obrade svakog zadatka u realnom vremenu, što pruža transparentnost i stateless arhitekturu.
- **Izmene**:
  - Kreiran je novi SQLAlchemy model `Job` u [backend/core/models.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/core/models.py) koji sadrži status, fazu (downloading, separating, transcribing, translating, diarizing, mixing, lipsyncing, completed), pokušaj (attempt) i reference na kreirane S3 ključeve.
  - Generisana je i primenjena Alembic migracija `9d45a91db31f` za tabelu `jobs`.
  - Integrisano je kreiranje i ažuriranje statusa i faza u Celery zadacima `analyze_video_task` i `render_video_task` u [backend/worker/tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py).

---

## 3. Idempotentnost i Caching na S3/MinIO
- **Opis**: Implementirano je inteligentno keširanje intermedijalnih faza kako bi se izbeglo ponavljanje skupih operacija na serverless GPU-ovima u slučaju pada i ponovnog pokretanja radnika.
- **Izmene u [backend/worker/tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py)**:
  1. **Separacija zvuka (Demucs)**: Kešira se na S3 na osnovu SHA256 hash-a ulaznog zvuka pod ključem `cache/separation/{audio_hash}_vocals.wav`. Pre pokretanja se vrši provera i preuzimanje ako postoji.
  2. **Transkripcija (Whisper)**: Kešira se u JSON formatu na osnovu hash-a vokalne trake i prompta (`cache/transcription/{transcription_hash}.json`).
  3. **Prevođenje (Qwen)**: Kešira se u JSON formatu na osnovu hash-a transkripta i videa (`cache/translation/{translation_hash}.json`).
  4. **TTS sinteza po segmentima**: Kešira se audio za svaki pojedinačni segment na osnovu hash-a prevedenog teksta, tipa glasa i modifikatora (`cache/tts/{tts_hash}.wav`). Ovo omogućava da se prilikom ponovnog renderovanja (npr. izmene samo jednog segmenta) svi ostali segmenti preuzmu iz keša, drastično štedeći GPU resurse na Modalu.

---

## 4. Celery Queue Hardening i Dead Letter Queue (DLQ)
- **Opis**: Povećana je otpornost na nivoa reda poruka kroz konfigurisanje automatskih ponovnih pokušaja, timeout-a i beleženja fatalnih grešaka.
- **Izmene**:
  - Konfigurisani su `acks_late=True` i `reject_on_worker_lost=True` na svim kritičnim Celery zadacima, osiguravajući da se poruka vrati u red ili obradi na failure handleru ukoliko worker neočekivano padne (npr. OOM).
  - Podešen je `max_retries=3` i `retry_backoff=True` (sa maksimalnim eksponencijalnim kašnjenjem od 300s) za automatsko rešavanje prolaznih mrežnih grešaka pri pozivu serverless GPU-ova.
  - Definisani su timeout-i: `time_limit=1200s` (soft: 1100s) za analizu, i `time_limit=1800s` (soft: 1700s) za render.
  - Implementiran je `handle_task_failure` callback koji na fatalnom neuspehu ažurira status Job-a u bazi na `failed` i šalje sve metapodatke i traceback greške u Redis Dead Letter Queue (`dead_letter_queue` lista).

---

## 5. Izolacija radnog prostora (Workspace Cleanup)
- **Opis**: Uklonjena je mutacija globalne promenljive `settings.TEMP_WORKSPACE` koja je uzrokovala trke za resursima (race conditions) u višenitnim Celery workerima.
- **Izmene**:
  - Radni prostori se izoluju kreiranjem pod-direktorijuma sa jedinstvenim ID-em zadatka (`settings.TEMP_WORKSPACE/task_id`).
  - Ispravljena je kritična greška `UnboundLocalError` u [backend/worker/lipsync.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/lipsync.py) gde se pristupalo neinicijalizovanoj promenljivoj `workspace`.

---

## 6. Backup i Restore procedure
- **Opis**: Kreirane su skripte za pravljenje rezervnih kopija baze i S3 skladišta, i obezbeđeno je uputstvo za oporavak u slučaju katastrofe.
- **Izmene**:
  - Kreirana je bash skripta [scripts/backup.sh](file:///home/gruya/Projektri/sinhronizuj.me/scripts/backup.sh) i Python skripta [scripts/backup_s3.py](file:///home/gruya/Projektri/sinhronizuj.me/scripts/backup_s3.py) za automatski dump PostgreSQL baze i S3 bucketa u vremenski označen `.tar.gz` arhiv.
  - Kreirana je skripta za oporavak [scripts/restore.sh](file:///home/gruya/Projektri/sinhronizuj.me/scripts/restore.sh) i [scripts/restore_s3.py](file:///home/gruya/Projektri/sinhronizuj.me/scripts/restore_s3.py).
  - Napisano je detaljno uputstvo [backup_restore_uputstvo.md](file:///home/gruya/Projektri/sinhronizuj.me/backup_restore_uputstvo.md).
  - Uspešno je sproveden i verifikovan kompletan **Restore Drill** (brisanje baze, reinstanciranje, uvoz podataka iz dump-a i oporavak S3 objekata).

---

## 7. Verifikacija testovima
- Svi postojeći i novi unit testovi uspešno prolaze:
  `27 passed, 48 warnings in 29.28s`
