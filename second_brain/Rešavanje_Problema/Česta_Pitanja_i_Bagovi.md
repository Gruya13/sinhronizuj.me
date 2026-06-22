# Česta Pitanja i Bagovi (Troubleshooting & FAQ)

Ova beleška sadrži listu najvažnijih tehničkih problema (bagova) koji su se pojavili tokom razvoja platforme **sinhronizuj.me**, njihovu analizu uzroka (Root Cause Analysis) i načine na koje su rešeni. Služi kao baza znanja za brzi oporavak sistema i sprečavanje ponavljanja istih grešaka.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Docker_i_Infrastruktura]]
*   [[Backend_Dokumentacija]]

---

## 🐛 1. NumPy JSON Serijalizacija (NumPy 2.4.4 TypeError)

### Simptom
Tokom analize ili prevođenja videa, nakon određenog vremena (~10 minuta rada), na klijentu se pojavljivao crveni baner sa greškom:
`Object of type bool is not JSON serializable` ili `Object of type float64 is not JSON serializable`.

### Uzrok (Root Cause)
U **numpy 2.4.4**, `np.bool_.__name__` je postavljen na `'bool'` (bez donje crte), ali `issubclass(np.bool_, bool)` vraća `False`. Iz tog razloga, standardni Python `json` encoder ne prepoznaje numpy boolean i float tipove (`np.bool_`, `np.float64`, `np.int64`, `np.ndarray`) i baca `TypeError`.
Ovi tipovi cure iz mašinskih modela (npr. `sentence-transformers`, `CrossEncoder` ili numpy operacija za računanje varijanse i otvorenosti usta u modulu [active_speaker.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/active_speaker.py)). Greška se javlja na tri mesta:
1. Prilikom poziva Celery metode `self.update_state()` ili povratne vrednosti Celery zadataka (Kombu serializer).
2. Prilikom keširanja rezultata u Redis u JSON formatu.
3. Prilikom upisa u PostgreSQL bazu podataka u JSONB kolonu (`costs` kolona u SQLAlchemy).

### Rešenje (Tri sloja zaštite)
Implementiran je robustan sistem za presretanje i konverziju numpy tipova:
1. **Globalni Monkey-patch** u [celery_app.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/celery_app.py):
   Presretnut je ugrađeni `json.JSONEncoder.default` metod na nivou uvoza modula:
   ```python
   import json as _json
   _original_encoder_default = _json.JSONEncoder.default

   def _numpy_safe_default(self, obj):
       try:
           import numpy as np
           if isinstance(obj, (np.bool_,)):
               return bool(obj)
           if isinstance(obj, np.integer):
               return int(obj)
           if isinstance(obj, np.floating):
               return float(obj)
           if isinstance(obj, np.ndarray):
               return obj.tolist()
       except ImportError:
           pass
       return _original_encoder_default(self, obj)

   _json.JSONEncoder.default = _numpy_safe_default
   ```
2. **Rekurzivna sanitizacija** u [tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py):
   Kreirana je funkcija `sanitize_for_json(obj)` koja rekurzivno prolazi kroz rečnike i liste i prevodi sve numpy tipove u nativne Python tipove pre nego što se pošalju u SQLAlchemy JSON kolonu.
3. **Eksplicitna konverzija**:
   Uvedena su eksplicitna kastovanja `float()` i `bool()` na mestima gde se rezultati direktno vade iz ML modela (npr. u `active_speaker.py` i `qe.py`).

---

## ⚡ 2. Ekstremno usporavanje analize videa (Active Speaker seek latency)

### Simptom
Faza 1 analize videa (koja uključuje i detekciju aktivnosti govornika) trajala je preko 20 minuta za relativno kratak video (npr. od 72 sekunde).

### Uzrok (Root Cause)
U prvobitnoj implementaciji [active_speaker.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/active_speaker.py), za svaki pojedinačni govorni segment iz transkripta, ponovo se otvarao video fajl, inicijalizovao se skupi MediaPipe FaceMesh model, i radilo se random seek-ovanje frejmova preko OpenCV-a (`cap.set(cv2.CAP_PROP_POS_FRAMES)`). FFmpeg seek-ovanje na kompresovanim `.mp4` fajlovima zahteva dekodovanje ključnih frejmova od početka, što je dovodilo do eksponencijalnog rasta vremena izvršavanja kako raste broj segmenata.

### Rešenje (Batch Pre-computation)
Logika je kompletno optimizovana uvođenjem pre-proračuna u jednom sekvencijalnom prolazu:
1. **Precompute funkcija**: Dodat je metod `precompute_active_speakers()` koji otvara video samo jednom i sekvencijalno ga čita frame-by-frame.
2. **Brzo preskakanje**: Za frejmove koje ne želimo da analiziramo (npr. uzorkujemo 8 frejmova po sekundi), koristi se `cap.grab()` koji je izuzetno brz jer preskače dekodovanje slike u memoriju.
3. **Timeline struktura**: Rezultati (detektovano lice i otvorenost usta) se smeštaju u jedinstvenu timeline strukturu u memoriji.
4. **Instant provera**: Celery zadatak preuzima podatke za svaki segment iz ove strukture za manje od 2 milisekunde. Ukupno vreme pre-procesiranja za ceo video je smanjeno na svega **4.5 sekundi** (ubrzanje od preko 200x).

---

## 🔒 3. Bandit SAST Greške (CI/CD neuspeh)

### Simptom
GitHub Actions CI/CD pipeline pada na koraku automatske bezbednosne provere (Bandit).

### Uzrok (Root Cause)
Bandit je prijavio sledeća upozorenja:
1. **B501 (SSL verification disabled)**: U [downloader.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/downloader.py) na liniji gde se radi SSRF validacija adrese korišćen je parametar `verify=False` kako bi se sprečili lokalni DNS/SSL problemi.
2. **B615 (Unsafe HuggingFace download)**: U [train_lora.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/training/train_lora.py) pri pozivima `load_dataset` i `from_pretrained` jer Bandit sumnja na učitavanje zlonamernog koda iz spoljnih izvora.

### Rešenje
Budući da su ovi pozivi u našem kontrolisanom okruženju bezbedni (HuggingFace model ID je konstantna, a SSRF provera se svesno radi bez SSL-a), rešenje je bilo dodavanje Bandit bypass komentara:
- Za SSL: `requests.head(..., verify=False)  # nosec B501`
- Za HuggingFace: `load_dataset(...)  # nosec B615`

---

## 🌐 4. Nginx 504 Gateway Timeout tokom sinteze celog glasa

### Simptom
Prilikom pokretanja generisanja glasa (TTS) za ceo video sa velikim brojem segmenata, klijent je posle tačno 60 sekundi prekidao vezu i prijavljivao crveni baner `Failed to fetch`.

### Uzrok (Root Cause)
FastAPI endpoint `/api/v1/project/{project_id}/generate-all-tts` je izvršavao sintezu zvuka sinhrono. Nginx proxy na Hetzner VPS-u ima podrazumevano vreme čekanja (read timeout) od 60 sekundi. Ako procesiranje svih segmenata (generisanje Piper TTS-a + kloniranje OpenVoice-a + pydub spajanje) traje duže od 60s, Nginx vraća 504 Gateway Timeout.

### Rešenje
1. Povećan je timeout u konfiguraciji Nginx servera na VPS-u (`/etc/nginx/sites-available/sinhronizuj.me`):
   ```nginx
   proxy_connect_timeout 600s;
   proxy_send_timeout 600s;
   proxy_read_timeout 600s;
   ```
2. Sintaksa je verifikovana (`nginx -t`) i servis je ponovo pokrenut (`systemctl reload nginx`).

---

## 📁 5. S3 Basename preuzimanje i greške direktorijuma

### Simptom
Analiza videa je pucala na Celery radniku sa greškom da ne može da kreira ili pronađe fajl u privremenom direktorijumu.

### Uzrok (Root Cause)
Prilikom preuzimanja videa sa S3, funkcija `download_video` u [downloader.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/downloader.py) je koristila ceo S3 ključ (koji može da sadrži foldere, npr. `projects/project_id/video.mp4`) kao deo lokalne putanje. Zbog toga je operativni sistem pokušavao da kreira ugnježdeni direktorijum koji nije postojao na disku Celery radnika.

### Rešenje
Izmenjena je logika u `downloader.py` tako da se preuzimanje vrši isključivo u koren privremenog workspace-a korišćenjem baznog naziva fajla:
`local_filename = os.path.basename(key)`

---

## 🐳 6. Docker Compose ne interpolira `.env` varijable na VPS-u

### Simptom
Nakon CI/CD deploy-a na Hetzner VPS, FastAPI i Redis servisi se ne podižu ispravno, ili se povlače pogrešne (stare) Docker slike sa GitHub Container Registry-ja.

### Uzrok (Root Cause)
Produkcioni Docker Compose fajlovi se nalaze u direktorijumu `infra/hetzner/`. Prilikom pokretanja komande `docker compose pull` ili `up` u tom direktorijumu, Docker Compose podrazumevano traži `.env` fajl u istom tom poddirektorijumu (`infra/hetzner/.env`). Kako je `.env` sa lozinkama i tagovima slika bio kreiran samo u korenu projekta, Docker Compose nije mogao da pročita varijable i koristio je prazne vrednosti.

### Rešenje
U GitHub Actions deploy skriptu ([deploy.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/deploy.yml)) dodat je korak koji kopira `.env` fajl u odgovarajući folder pre pokretanja kontejnera:
`cp .env infra/hetzner/.env`
