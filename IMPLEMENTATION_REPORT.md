# IMPLEMENTATION REPORT — Perpetual Learning System & Translation Pipeline Optimization

Ovaj izveštaj detaljno opisuje implementaciju trostepenog **Perpetual Learning System-a** i pratećih optimizacija asinhronog pipeline-a za prevođenje i sinhronizaciju video sadržaja na platformi **sinhronizuj.me**.

---

## 1. Pregled dodatih i izmenjenih tabela u bazi podataka

Sve izmene u bazi podataka su aditivnog karaktera i unete su kroz Alembic migracije kako bi se osigurala kompatibilnost sa produkcionim podacima.

### 1.1 Nova tabela: `pending_translation_memory`
Služi za privremeno čuvanje prevoda srednjeg kvaliteta koji čekaju na potencijalnu promociju u glavnu Translation Memory bazu ukoliko se dovoljno puta ponove.

| Kolona | Tip | Ograničenja | Opis |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key, Default: `uuid_generate_v4()` | Jedinstveni identifikator zapisa. |
| `user_id` | `UUID` | Foreign Key (`users.id`), Nullable: False | Identifikator korisnika koji je vlasnik projekta. |
| `project_id` | `String` | Nullable: False | ID projekta iz kojeg je nastao prevod. |
| `source_text` | `Text` | Nullable: False | Originalni engleski tekst. |
| `target_text` | `Text` | Nullable: False | Prevedeni srpski tekst (ekavica, latinica). |
| `occurrence_count` | `Integer` | Default: 1 | Broj pojavljivanja ove tačne fraze/rečenice. |
| `created_at` | `DateTime` | Default: `utcnow()` | Vreme kreiranja zapisa. |

### 1.2 Izmene nad postojećim tabelama
*   **Tabela `translation_memory`**:
    *   Dodata kolona `auto_approved` (`Boolean`, default: `False`, `Nullable: False`). Označava da li je par prebačen u memoriju automatskim putem kroz Real-time "Tihi Konsenzus" ili je korisnik ručno odobrio prevod.
*   **Tabela `segments`**:
    *   Dodata kolona `qe_score` (`Float`, `Nullable: True`). Čuva Quality Estimation skor izračunat nad lekturisanim segmentom.
    *   Dodata kolona `confidence_score` (`Float`, `Nullable: True`, default: 5.0). Čuva ocenu pouzdanosti koju je Lektor vratio.
*   **Tabela `wiki_rules`**:
    *   Kolona `user_id` je modifikovana u `Nullable: True`. Ovo omogućava definisanje **globalnih pravila** (`is_global = True`) koja važe za sve korisnike, a koja automatski generiše noćni analiza job (Subagent Beta).

---

## 2. Celery Beat raspored (Schedules) i Cron izrazi

Unutar Celery Beat konfiguracije u `backend/worker/celery_app.py` integrisana su tri asinhrona zadatka koji zatvaraju petlju kontinuiranog učenja.

```python
celery_app.conf.beat_schedule = {
    # ... postojeći schedules ...
    "promote_pending_tm_every_4_hours": {
        "task": "backend.worker.tasks.promote_pending_tm_task",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "run_nightly_pattern_analysis_at_2am": {
        "task": "backend.worker.tasks.run_nightly_pattern_analysis_task",
        "schedule": crontab(minute=0, hour=2),
    },
    "deploy_lora_every_sunday_3am": {
        "task": "backend.worker.tasks.deploy_lora_task",
        "schedule": crontab(minute=0, hour=3, day_of_week="sunday"),
    },
}
```

### Detalji schedules:
1.  **Promocija pending TM-a (`promote_pending_tm_task`)**:
    *   **Zadatak**: Skenira `pending_translation_memory` i grupiše zapise po `source_text`. Ukoliko se isti izvor ponovio $\ge 2$ puta sa visokim kvalitetom, prevod se promoviše u glavnu `translation_memory` sa `auto_approved = True`, a privremeni zapisi se brišu.
    *   **Cron izraz**: `0 */4 * * *` (Svaka 4 sata, na početku sata).
2.  **Noćni Lovac na Obrasce (`run_nightly_pattern_analysis_task`)**:
    *   **Zadatak**: Pokreće analizu segmenata u poslednjih 24 sata gde je `qe_score < 0.85`. Vrši DBSCAN klasterovanje na bazi MiniLM embeddinga i šalje klastere Qwen-u da prepozna sistemske greške i upiše globalno Wiki pravilo u bazu.
    *   **Cron izraz**: `0 2 * * *` (Svaki dan u 02:00 po serveru).
3.  **Nedeljni LoRA Fine-Tuning (`deploy_lora_task`)**:
    *   **Zadatak**: Prikuplja "zlatne" parove iz TM-a i korisničkih ispravki, generiše sintetički dataset preko `data_generator.py` sa parafrazerom, pokreće PEFT/LoRA finetuning nad Qwen3-32B na Modalu i osvežava Redis ključ active_lora_path po završetku treninga.
    *   **Cron izraz**: `0 3 * * 0` (Svake nedelje u 03:00 ujutru).

---

## 3. Procedura za brz Rollback u slučaju degradacije performansi

Ukoliko novi model (LoRA adapter), nova pravila ili automatski upisi u TM dovedu do degradacije performansi, lošijeg prevoda ili zastoja u produkciji, implementirani su brzi mehanizmi za trenutan oporavak sistema bez ponovnog build-a i deploy-a koda.

### 3.1 Onemogućavanje LoRA adaptera (Blue-Green Rollback)
Ako fino podešeni model (LoRA) počne da daje lošije rezultate ili izaziva mrežne timeout-e, isključivanje adaptera se vrši jednostavnim brisanjem ili promenom Redis ključa `active_lora_path`.

*   **Rollback komanda (preko Redisa)**:
    Povežite se na Redis instancu i obrišite ključ:
    ```bash
    redis-cli -a <REDIS_PASSWORD> DEL active_lora_path
    ```
    *Efekat:* Radnici će pri sledećem API pozivu Qwen-u poslati payload bez `lora_path` parametra, što automatski vraća sistem na osnovni (base) Qwen3-32B model.

### 3.2 Rollback automatski generisanih Wiki pravila
Ako automatski generisano Wiki pravilo (napravljeno kroz DBSCAN i LLM) unese nepoželjne stilske devijacije, pravilo se može isključiti ili obrisati direktno iz baze podataka.

*   **Deaktivacija / Brisanje preko SQL-a**:
    ```sql
    -- Pronađite automatski generisana pravila koja su globalna
    SELECT id, title, content FROM wiki_rules WHERE is_global = True AND title LIKE 'Auto Rule%';

    -- Obrišite problematično pravilo na osnovu njegovog ID-ja
    DELETE FROM wiki_rules WHERE id = <WIKI_RULE_ID>;
    ```
    *Efekat:* Prilikom sledećeg prevoda, radnik učitava sveža pravila iz baze i problematično pravilo više neće biti injektovano u sistemski prompt.

### 3.3 Rollback "Tihog Konsenzusa" (Automatskih TM upisa)
Ukoliko se ispostavi da su se loši prevodi greškom upisali u glavnu bazu prevođenja (`translation_memory`), možete očistiti sve automatski odobrene prevode iz baze.

*   **Brisanje automatskih TM zapisa preko SQL-a**:
    ```sql
    DELETE FROM translation_memory WHERE auto_approved = True;
    ```
    *Efekat:* Brišu se svi prevodi ubačeni kroz Real-time petlju, dok se ručno uneti i odobreni prevodi od strane korisnika čuvaju.

### 3.4 Lokalni Sandbox i Dijagnostika
Za potrebe testiranja rollback-a i simulacije pipeline-a, u repozitorijumu je konfigurisan `docker-compose.override.yml`.
Pokretanje sandbox okruženja vrši se pomoću:
```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d
```
Ovo podiže lokalne kontejnere za Redis i Postgres sa ugrađenim healthcheck-ovima koji u potpunosti oponašaju produkciono okruženje.
