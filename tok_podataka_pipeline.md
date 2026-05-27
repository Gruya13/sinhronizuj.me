# Detaljan Tok Podataka kroz Pipeline (sinhronizuj.me)

Ovaj dokument detaljno opisuje kako se podaci kreću, transformišu i procesiraju kroz ceo sistem za inteligentnu sinhronizaciju video zapisa sa engleskog na srpski jezik.

---

## 1. Pregled Strukture i Toka Podataka

Sistem je organizovan po principu klijent-server arhitekture sa raspodeljenim asinhronim zadacima:

**React Frontend** (UI) $\rightarrow$ **FastAPI API** (Server) $\rightarrow$ **Celery & Redis** (Red/Zadaci) $\rightarrow$ **Modal.com GPU** (Modeli) $\rightarrow$ **FFmpeg Merger** $\rightarrow$ **Finalni Video**

```mermaid
flowchart TD
    subgraph Klijent / Studio (Korisnički interfejs)
        UI[Korisnik šalje video zahtev]
    end

    subgraph Hetzner VPS (Celery Task Queue & Orchestration)
        Task[Celery Task: run_sync_pipeline]
        Merger[Merger Modul: merger.py]
    end

    subgraph Modal.com Serverless (GPU AI Podovi)
        Demucs[Demucs: Separacija zvuka]
        Whisper[ASR: Transkripcija i tajminzi]
        Translator[Translator: Qwen2-VL Multimodal]
        Lektor[Lektor: Qwen 2.5 32B Instruct]
        TTS[TTS Engine: Piper sr_Marko]
    end

    UI -->|1. Upload & Pokretanje| Task
    Task -->|2. Separacija zvuka| Demucs
    Task -->|3. Transkripcija| Whisper
    Task -->|4. Multimodalni prevod + Slike| Translator
    Task -->|5. Lektura & Sažimanje| Lektor
    Task -->|6. Generisanje glasa| TTS
    
    TTS -->|WAV segmenti| Merger
    Demucs -->|Muzika / Pozadina| Merger
    
    Merger -->|7. Dynamic Stretching & Audio Speedup| Merger
    Merger -->|8. Finalni video sa srpskim vokalom| Task
    Task -->|9. Završeno| UI
```

---

## 2. Detaljan opis svakog koraka u pipeline-u

### Korak 1: Klijentski zahtev i Inicijalizacija (API & Celery)
* **Ulazni podaci:**
  - Video fajl (upload-ovan na Minio S3 bucket) ili javni URL videa.
  - Opcioni parametri (debug mod, itd.).
* **Proces:**
  1. Korisnik klikne na dugme "Sinhronizuj" u React aplikaciji.
  2. React šalje POST zahtev na FastAPI backend endpoint `/api/v1/sync`.
  3. API generiše jedinstveni UUID (Task ID) i pokreće asinhroni Celery zadatak `run_sync_pipeline`.
  4. API odmah vraća Task ID klijentu, koji započinje polling (periodično ispitivanje) statusa na endpointu `/api/v1/status/{task_id}`.
  5. Celery radnik (worker) preuzima zadatak iz Redis reda i započinje izvršavanje pipeline-a.
* **Izlazni podaci:**
  - Task ID i inicijalni status `PENDING` / `PROGRESS`.

---

### Korak 2: Separacija Zvuka (Demucs)
* **Ulazni podaci:**
  - Preuzeti originalni video fajl (lokalno u `temp_workspace`).
* **Proces:**
  1. Video fajl se šalje na Modal.com serverless endpoint gde je podignut Meta Demucs model.
  2. Demucs vrši razdvajanje audio zapisa iz videa na više traka (stems).
  3. Sistem kombinuje i izvozi dve ključne trake u WAV formatu:
     - `no_vocals.wav` (Muzika, zvučni efekti, šumovi okoline).
     - `vocals.wav` (Samo čisti ljudski govor).
* **Izlazni podaci:**
  - Dva audio fajla: `no_vocals.wav` i `vocals.wav`.
  - **Trošak:** Vreme izvršavanja se preračunava po T4 tarifi ($0.00018/s).

---

### Korak 3: Transkripcija i Tajminzi (Whisper)
* **Ulazni podaci:**
  - Vokalna traka `vocals.wav`.
* **Proces:**
  1. `vocals.wav` se šalje na Modal Whisper endpoint.
  2. Model analizira zvuk i vraća tekst sa preciznim reč-po-reč (word-level) vremenskim oznakama.
  3. Orkestrator grupiše reči u logičke rečenice/segmente. Svaki segment dobija:
     - ID segmenta (`[seg-0]`, `[seg-1]`, itd.).
     - Startno vreme u sekundama (`start`).
     - Krajnje vreme u sekundama (`end`).
     - Originalni tekst na engleskom (`text`).
* **Izlazni podaci:**
  - JSON lista segmenata sa tekstom i vremenskim koordinatama.
  - **Trošak:** Vreme rada se računa po T4 tarifi ($0.00018/s).

---

### Korak 4: Generisanje Vizuelnog Konteksta (Ekstrakcija frejmova)
* **Ulazni podaci:**
  - Originalni video fajl.
* **Proces:**
  1. Lokalna FFmpeg skripta izvlači tačno 10 ravnomerno raspoređenih slika (keyframes) iz celog video zapisa.
  2. Slike se konvertuju u Base64 format i komprimuju kako bi se optimizovao mrežni saobraćaj prema LLM-u.
* **Izlazni podaci:**
  - Lista od 10 Base64 kodiranih slika.

---

### Korak 5: Multimodalno Prevođenje (Qwen2-VL)
* **Ulazni podaci:**
  - Lista engleskih segmenata u formatu `[seg-ID] tekst`.
  - 10 Base64 slika iz videa.
* **Proces:**
  1. Podaci se šalju na Modal endpoint gde je pokrenut Qwen2-VL multimodalni vizuelni model (A10G GPU).
  2. Model analizira slike i tekst istovremeno.
  3. Prepoznaje rod govornika sa slika (muški/ženski) i vizuelne objekte kako bi pravilno izabrao gramatički rod i kontekst u prevodu na srpski jezik (ekavica).
  4. Vraća grubu listu prevoda mapiranu po ID-jevima segmenata.
* **Izlazni podaci:**
  - JSON lista segmenata sa grubim prevodom na srpski jezik.
  - **Trošak:** Vreme rada se računa po A10G tarifi ($0.00033/s).

---

### Korak 6: Lektura, Poliranje i Vremensko Sažimanje (Qwen 2.5 32B Lektor)
* **Ulazni podaci:**
  - Originalni engleski tekst i grubi srpski prevod.
  - Tačno trajanje svakog segmenta u sekundama.
* **Proces:**
  1. Podaci se šalju na Modal Lektor endpoint (A100-80GB GPU).
  2. Lektor primenjuje stroga jezička pravila:
     - Fonetska transkripcija stranih imena i pojmova (npr. "Claude" -> "Klod").
     - Zabrana dugih fraza kao što je "veštačka inteligencija" (koristi se "Ej Aj" sa razmakom).
     - Prilagođavanje dužine rečenice: broj reči u segmentu se agresivno sažima tako da ne pređe `trajanje * 3` reči, kako bi govornik mogao prirodno da izgovori tekst u raspoloživom vremenu.
* **Izlazni podaci:**
  - Konačni, lekturisani i vremenski optimizovani srpski tekstovi za sve segmente.
  - **Trošak:** Vreme rada se računa po A100 tarifi ($0.00140/s).

---

### Korak 7: Čišćenje i Korekcija Teksta (Python Regex Post-Processor)
* **Ulazni podaci:**
  - Lekturisani srpski segmenti.
* **Proces:**
  1. Tekst prolazi kroz brzi, deterministički Python Regex parser na Hetzner serveru.
  2. Ispravljaju se česte sistemske greške lektora (npr. pravilan izgovor padeža "o Ej Aju" umesto "o Ej Aj", uklanjanje viška povratnih zamenica "su se postale" -> "su postale", usklađivanje roda množine "koje su popularne" umesto "koji su popularni", itd.).
* **Izlazni podaci:**
  - 100% čist i gramatički ispravan srpski tekst spreman za sintezu.

---

### Korak 8: Sinteza Govora (Piper TTS)
* **Ulazni podaci:**
  - Čist srpski tekst po segmentima.
* **Proces:**
  1. Svaki segment se šalje na Modal Piper TTS endpoint koji koristi model muškog glasa `sr_Marko_medium` (L4 GPU).
  2. Sinhronizacija brzine izgovora:
     - Sistem računa ciljno trajanje govora poredeći dužinu teksta i trajanje originalnog video segmenta.
     - Piperu se šalje dinamički izračunat parametar `length_scale` (između 0.75 i 1.25). Model generiše govor nativno sporije ili brže sa prirodnim fonemama, bez veštačkog FFmpeg ubrzavanja koje kvari kvalitet glasa.
  3. Generišu se pojedinačni WAV fajlovi za svaki segment.
* **Izlazni podaci:**
  - Skup pojedinačnih audio fajlova (po jedan za svaki segment govora).
  - **Trošak:** Vreme rada se računa po L4 tarifi ($0.00025/s).

---

### Korak 9: Dinamičko Spajanje i Rastezanje Videa (Merger & Time Stretching)
* **Ulazni podaci:**
  - Generisani srpski WAV fajlovi.
  - Originalni video fajl.
  - Pozadinska muzika bez vokala (`no_vocals.wav`).
* **Proces:**
  1. Modul `merger.py` poredi trajanje svakog srpskog WAV fajla sa trajanjem njegovog originalnog segmenta.
  2. Ako je srpski audio duži od raspoloživog originalnog prostora:
     - Video i pozadinska muzika se dinamički usporavaju (maksimalno do 1.05x, tj. 5% usporavanja) kako bi se dobilo na vremenu.
     - Ako je audio i dalje predugačak, vrši se precizno ubrzanje glasa (FFmpeg `atempo` filter).
  3. Svi srpski WAV segmenti se spajaju u jedinstvenu vokalnu audio traku (`merged_vocals.wav`), ostavljajući tišine (gaps) na mestima gde nema govora.
  4. Kreira se vremenski modifikovan video fajl (`stretched_video.mp4`) čije se trajanje u potpunosti poklapa sa novim tempom izgovora.
* **Izlazni podaci:**
  - `stretched_video.mp4` (Video bez zvuka, blago rastegnut po potrebi).
  - `merged_vocals.wav` (Kompletna srpska vokalna traka).
  - `stretched_bg.wav` (Rastegnuta pozadinska muzika u savršenom tajmingu sa videom).

---

### Korak 10: Finalni Miks i Generisanje Izlaza
* **Ulazni podaci:**
  - Rastegnuti video `stretched_video.mp4`.
  - Srpska vokalna traka `merged_vocals.wav`.
  - Pozadinska muzika `stretched_bg.wav`.
* **Proces:**
  1. FFmpeg na Hetzner serveru preuzima ove tri komponente.
  2. Miksuje pozadinsku muziku (stišanu za određeni faktor kako bi se glas jasno čuo) i novu srpsku vokalnu traku u jedinstvenu audio traku.
  3. Spaja audio sa videom i enkodira u finalni MP4 format (H264 video kodek, AAC audio kodek za maksimalnu kompatibilnost sa pretraživačima).
  4. Finalni video se čuva u `temp_workspace` direktorijumu.
  5. Celery obeležava zadatak kao `SUCCESS` i upisuje finalnu putanju i ukupne troškove obrade u Redis.
* **Izlazni podaci:**
  - Finalni MP4 video fajl spreman za preuzimanje i reprodukciju na klijentu.
  - JSON objekat sa statusom `SUCCESS` i detaljnim troškovima po fazama.

---

## 3. Monitoring statusa i troškova u realnom vremenu

Tokom celog ovog procesa, React klijent periodično poziva API status rutu:
1. API čita trenutno stanje `progress_metadata` direktno iz Redis baze podataka.
2. API ova dva statusa (`PROGRESS` i `SUCCESS`) dopunjuje objektom `costs` koji sadrži trajanje i cenu za svaku fazu obrade.
3. React klijent na osnovu toga ažurira svoj UI: rendersuje live GPU koji radi u tom trenutku, live procenjeni trošak i na samom kraju tablu sa kompletnim izveštajem.
