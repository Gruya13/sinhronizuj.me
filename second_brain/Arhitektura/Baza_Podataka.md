# Baza Podataka i Modeli

Ovaj dokument opisuje strukturu baze podataka, SQLAlchemy modele i migracioni tok pomoću Alembic-a za platformu **sinhronizuj.me**.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Arhitektura_Sistema]]

---

## 1. Specifikacija Baze Podataka (SQLAlchemy Modeli)

Baza podataka koristi PostgreSQL. Tabele su mapirane kroz SQLAlchemy modele u [backend/core/models.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/core/models.py).

### Specijalni tip: GUID
Zbog korišćenja UUID ključeva umesto auto-inkrementalnih integera (radi veće bezbednosti i nemogućnosti predviđanja ID-eva), implementiran je `GUID` tip dekorator koji na PostgreSQL nivou koristi nativni `UUID` tip, dok se na lokalnim SQLite okruženjima za testiranje mapira na `CHAR(32)`:

```python
class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True
    # ... rukovanje bind parametrima i rezultatima u zavisnosti od dijalekta baze
```

### 1.1. Tabela Korisnika (`users`)
Služi za registraciju korisnika, verifikaciju lozinke i definisanje privilegija.

| Kolona | Tip Podataka | Ograničenja | Opis |
| :--- | :--- | :--- | :--- |
| `id` | `GUID` | Primary Key, Default UUID | Jedinstveni identifikator korisnika |
| `email` | `String` | Unique, Index, Nullable=False | Email adresa korisnika |
| `password_hash` | `String` | Nullable=False | Hešovana lozinka (koristi passlib/bcrypt) |
| `is_admin` | `Boolean` | Default=False, Server Default=false | Indikator administratorskih privilegija |
| `created_at` | `DateTime` | Default=UTC.now | Datum i vreme registracije naloza |

**Relacije:**
*   `projects`: Jedan korisnik može imati više projekata (`one-to-many` prema tabeli `projects`, kaskadno brisanje).
*   `glossaries`: Jedan korisnik može definisati više glosarskih parova (`one-to-many` prema tabeli `glossaries`, kaskadno brisanje).

### 1.2. Tabela Projekata (`projects`)
Sadrži meta-podatke o video fajlovima i putanjama na S3 skladištu.

| Kolona | Tip Podataka | Ograničenja | Opis |
| :--- | :--- | :--- | :--- |
| `id` | `GUID` | Primary Key, Default UUID | Jedinstveni identifikator projekta |
| `name` | `String` | Nullable=False | Korisnički definisan naziv projekta |
| `user_id` | `GUID` | ForeignKey(users.id, CASCADE), Nullable=False | Vlasnik projekta |
| `status` | `String` | Default="empty" | Status projekta (`empty`, `analyzing`, `ready`, `completed`) |
| `video_title` | `String` | Default="" | Naslov video fajla (npr. naziv učitanog fajla) |
| `video_s3_key` | `String` | Nullable=True | Putanja do originalnog videa na S3 |
| `vocals_s3_key` | `String` | Nullable=True | Putanja do izdvojenog vokala na S3 |
| `no_vocals_s3_key` | `String` | Nullable=True | Putanja do videa/audia bez vokala na S3 |
| `visual_context_s3_key` | `String` | Nullable=True | Putanja do metapodataka o vizuelnom kontekstu |
| `dubbed_audio_s3_key` | `String` | Nullable=True | Putanja do izgenerisanog srpskog audio miksa |
| `final_video_s3_key` | `String` | Nullable=True | Putanja do finalnog sinhronizovanog videa |
| `costs` | `JSON` | Nullable=True | Detaljna struktura troškova obrade na Modalu |
| `created_at` | `DateTime` | Default=UTC.now | Vreme kreiranja projekta |

**Relacije:**
*   `user`: Povezuje projekat sa roditeljskim korisnikom (`many-to-one`).
*   `segments`: Povezuje sa svim segmentima prevoda (`one-to-many` prema tabeli `segments`, kaskadno brisanje).

### 1.3. Tabela Segmenata (`segments`)
Sadrži vremenske isečke, tekstualni prevod i parametre audio sinteze za svaki segment videa.

| Kolona | Tip Podataka | Ograničenja | Opis |
| :--- | :--- | :--- | :--- |
| `project_id` | `GUID` | ForeignKey(projects.id, CASCADE), Primary Key | Projekat kojem segment pripada |
| `segment_id` | `Integer` | Primary Key | Hronološki indeks segmenta (0, 1, 2...) |
| `start` | `Float` | Nullable=False | Početno vreme segmenta u sekundama |
| `end` | `Float` | Nullable=False | Krajnje vreme segmenta u sekundama |
| `original` | `String` | Default="" | Originalni transkript govora na izvornom jeziku |
| `translated` | `String` | Default="" | Prevedeni srpski tekst |
| `voice_type` | `String` | Default="clone" | Izbor glasa (`clone` za kloniranje, `male` za generički) |
| `volume` | `Float` | Default=0.0 | Jačina glasa u decibelima (relativno od originala) |
| `speed` | `Float` | Default=1.0 | Faktor brzine reprodukcije (npr. 1.0 = normalno) |
| `pitch` | `Float` | Default=0.0 | Modifikacija visine glasa |
| `bg_volume` | `Float` | Default=0.0 | Jačina pozadinskog zvuka tokom ovog segmenta |
| `tts_s3_key` | `String` | Nullable=True | Putanja do generisanog srpskog govora za ovaj segment |
| `tts_duration` | `Float` | Nullable=True | Realno trajanje izgenerisanog audio zapisa |
| `status` | `String` | Default="edited" | Status segmenta (`edited`, `previewed`) |

**Relacije:**
*   `project`: Povezuje segment sa roditeljskim projektom (`many-to-one`).

### 1.4. Tabela Glosara (`glossaries`)
Služi za definisanje pravila prevođenja specifičnih reči (rečnik).

| Kolona | Tip Podataka | Ograničenja | Opis |
| :--- | :--- | :--- | :--- |
| `id` | `GUID` | Primary Key, Default UUID | Identifikator glosarskog para |
| `user_id` | `GUID` | ForeignKey(users.id, CASCADE), Nullable=False | Vlasnik glosara |
| `source_word` | `String` | Nullable=False | Izvorna reč (npr. na engleskom) |
| `target_word` | `String` | Nullable=False | Željeni prevod (na srpskom) |
| `created_at` | `DateTime` | Default=UTC.now | Vreme dodavanja u rečnik |

### 1.5. Tabela Poslova (`jobs`)
Prati stanje izvršavanja asinhronih zadataka u realnom vremenu (State Machine).

| Kolona | Tip Podataka | Ograničenja | Opis |
| :--- | :--- | :--- | :--- |
| `id` | `GUID` | Primary Key, Default UUID | Jedinstveni identifikator posla |
| `project_id` | `GUID` | ForeignKey(projects.id, CASCADE), Nullable=True | Projekat povezan sa poslom |
| `status` | `String` | Default="pending" | Status posla (`pending`, `running`, `completed`, `failed`) |
| `phase` | `String` | Default="pending" | Aktivna faza (`downloading`, `separating`, `transcribing`, `translating`, `diarizing`, `mixing`, `lipsyncing`) |
| `attempt` | `Integer` | Default=1 | Trenutni pokušaj izvršavanja |
| `max_attempts` | `Integer` | Default=3 | Maksimalni dozvoljeni broj pokušaja |
| `error_message` | `String` | Nullable=True | Poruka o grešci u slučaju neuspeha |
| `created_at` | `DateTime` | Default=UTC.now | Vreme kreiranja posla |
| `updated_at` | `DateTime` | Default=UTC.now, onupdate | Vreme poslednjeg ažuriranja |

---

## 2. Inicijalizacija i Sigurnosno Ojačavanje (Hardening)

1.  **Bezbedan start aplikacije**: Iz [backend/main.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/main.py) su uklonjeni svi startup DDL iskazi poput `Base.metadata.create_all()` i direktne `ALTER TABLE` komande.
2.  **Autoritet šeme**: Sve tabele i izmene na šemi se primenjuju isključivo preko Alembic migracionog alata.
3.  **Offline Kreiranje Administratora**: Uklonjen je javni API endpoint `/api/v1/admin/create-first-admin` iz bezbednosnih razloga. Novi administratori se kreiraju i promovišu isključivo offline preko CLI komande na host VPS-u:
    ```bash
    python -m backend.cli create_admin --email [EMAIL] --password [PASSWORD]
    ```

---

## 3. Alembic Konfiguracija i Migracioni Tok

U cilju bezbedne nadogradnje šeme baze podataka bez gubitka podataka u produkciji, implementiran je **Alembic** migracioni alat unutar direktorijuma `backend/alembic`.

### Konfiguracione datoteke:
*   [backend/alembic.ini](file:///home/gruya/Projektri/sinhronizuj.me/backend/alembic.ini): Definiše putanje do migracionih skripti i osnovna podešavanja.
*   [backend/alembic/env.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/alembic/env.py): Konfigurisan je da dinamički čita `DATABASE_URL` iz FastAPI podešavanja. Takođe, importuje `Base.metadata` iz `backend.core.models` kako bi omogućio automatsku detekciju promena u šemi (`autogenerate` režim).

### Standardni workflow za migracije:
1.  **Izmena modela**: Nakon izmene u `backend/core/models.py`, programer generiše novu migraciju:
    ```bash
    cd backend
    alembic revision --autogenerate -m "opis_promene"
    ```
2.  **Pregled migracije**: Skripta se generiše u `backend/alembic/versions/`. Zbog korišćenja custom `GUID` tipa, na vrh generisane skripte potrebno je dodati `import backend` kako bi Alembic prepoznao tip `backend.core.models.GUID()`.
3.  **Primena migracije**: U produkcijskom okruženju, prilikom pokretanja novog izdanja, migracija se primenjuje na bazu komandom:
    ```bash
    alembic upgrade head
    ```

---

## 4. Optimizacija baze podataka (Faza 3)

U cilju ubrzanja performansi i smanjenja opterećenja na PostgreSQL instanci pri čestim SQL JOIN upitima i CASCADE brisanjima, u Fazi 3 su sprovedene sledeće optimizacije:

1. **Indeksiranje stranih ključeva**:
   - Dodat je parametar `index=True` na svim ključnim stranim ključevima (`user_id` i `project_id`) u sledećim tabelama:
     - `projects` (`user_id`)
     - `glossaries` (`user_id`)
     - `jobs` (`project_id`)
     - `translation_memory` (`user_id`)
     - `wiki_rules` (`user_id`)
     - `pending_translation_memory` (`user_id`)
   - Indeksiranje ovih kolona ubrzava SQL JOIN operacije i pretrage po korisniku/projektu i do 10x, a takođe sprečava full-table scan-ove pri kaskadnim brisanjima.

2. **Rešavanje N+1 upita pri čuvanju nacrta**:
   - U ruti `save_project_draft` u [projects.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/routes/projects.py) izbegnut je klasičan N+1 problem. Umesto da se za svaki izmenjeni segment iz zahteva radi poseban `SELECT` upit na bazu, svi segmenti povezani sa projektom se dobavljaju odjednom pomoću jednog upita:
     ```python
     segments = db.query(Segment).filter(Segment.project_id == project_id).all()
     ```
   - Segmenti se zatim mapiraju u memorijski rečnik po `segment_id`, čime se broj upita na bazu smanjuje sa N+1 na tačno 1.
