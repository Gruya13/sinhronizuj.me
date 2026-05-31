# Detaljan Tok Podataka kroz Dvofazni Pipeline (sinhronizuj.me) - Verzija 2

Ovaj dokument detaljno opisuje kako se podaci kreću, transformišu i procesiraju kroz ceo sistem za inteligentnu sinhronizaciju video zapisa sa engleskog na srpski jezik, oslikavajući trenutno dvofazno stanje projekta sa Studio Editorom i AI Lektorom.

---

## 1. Pregled Strukture i Dvofaznog Toka Podataka

Sistem je podeljen na dve nezavisne faze (asinhrona analiza i finalno renderovanje) sa interaktivnim Studio Editorom u sredini koji omogućava korisniku fino podešavanje u realnom vremenu:

```mermaid
flowchart TD
    subgraph Klijent / Studio (Korisnički interfejs)
        UI[Korisnik započinje projekat]
        Studio[Studio Editor: Izmena prevoda, glasa i zvuka]
        MagicShorten[Magic Shorten: AI Lektor skraćivanje]
        Preview[Realtime Preview: Mikser sa cache-buster-om]
        RenderTrigger[Korisnik pokreće Render]
    end

    subgraph Hetzner VPS (FastAPI, Redis, Celery & FFmpeg)
        API[FastAPI API rute]
        Redis[(Redis: project:ID:draft)]
        Task1[Faza 1 Celery Task: analyze_video_task]
        Task2[Faza 2 Celery Task: render_video_task]
        Merger[Merger Modul: merger.py + FFmpeg]
    end

    subgraph Modal.com Serverless (GPU AI Podovi)
        Demucs[Demucs: Separacija zvuka]
        Whisper[ASR: Transkripcija i tajminzi]
        Translator[Translator: Qwen2-VL Multimodal]
        Lektor[Lektor: Qwen 2.5 32B Instruct]
        TTS[TTS Engine: Piper / OpenVoice V2]
    end

    UI -->|1. Upload & Početak| API
    API -->|2. Pokreće Celery Fazu 1| Task1
    
    Task1 -->|3. Separacija| Demucs
    Task1 -->|4. Transkripcija| Whisper
    Task1 -->|5. Multimodalni prevod| Translator
    Task1 -->|6. Lektura & Sažimanje| Lektor
    Task1 -->|7. Upisuje rezultate analize| Redis
    
    Redis -->|8. Učitavanje drafta| Studio
    Studio -->|9. Brzi preview /tts| API
    API -->|10. Brza sinteza / Splicing| TTS
    
    Studio -->|11. Zahtev za AI Lektora| API
    API -->|12. Skraćivanje prevoda| Lektor
    
    Studio -->|13. In-browser realtime mikser| Preview
    
    Studio -->|14. Pokretanje Faze 2| RenderTrigger
    RenderTrigger -->|15. Poziv /render| API
    API -->|16. Pokreće Celery Fazu 2| Task2
    
    Task2 -->|17. Generisanje svih preostalih glasa| TTS
    Task2 -->|18. Dynamic Stretching, Ducking & Spajanje| Merger
    Merger -->|19. Finalni miks & MP4| Task2
    Task2 -->|20. Gotov video| UI
```

---

## 2. Detaljan opis faza i koraka u pipeline-u

### FAZA 1: ASINHRONA ANALIZA VIDEA (`analyze_video_task`)

Ova faza se izvršava odmah nakon uvoza videa. Cilj je da se izvuče audio, transkribuje i pripremi inicijalni prevod koji se čuva kao nacrt (draft).

#### Korak 1: Inicijalizacija Projekta
* **Ulazni podaci:**
  - Video fajl (S3 upload) ili javni URL videa.
* **Proces:**
  1. FastAPI endpoint `/api/v1/sync` prihvata zahtev.
  2. Pokreće se Celery zadatak `analyze_video_task`.
  3. Klijent dobija Task ID i započinje polling statusa preko `/api/v1/status/{task_id}`.

#### Korak 2: Separacija Zvuka (Demucs)
* **Proces:**
  1. Video se šalje na Modal Demucs endpoint.
  2. Audio se deli na `no_vocals.wav` (muzika i efekti) i `vocals.wav` (čist govor).

#### Korak 3: Transkripcija i Tajminzi (Whisper)
* **Proces:**
  1. `vocals.wav` se šalje na Modal Whisper.
  2. Whisper vraća reč-po-reč vremenske oznake koje orkestrator grupiše u segmente sa parametrima `start`, `end`, i `text` (originalni engleski).

#### Korak 4: Vizuelni Kontekst i Multimodalni Prevod (Qwen2-VL)
* **Proces:**
  1. FFmpeg izvlači 10 keyframe frejmova iz videa koji se konvertuju u Base64.
  2. Qwen2-VL model analizira slike i tekst kako bi pravilno utvrdio rod govornika (muški/ženski) i kontekst u srpskom prevodu.

#### Korak 5: Lektura, Sažimanje i Regex Post-Procesiranje
* **Proces:**
  1. Qwen 2.5 Lektor na Modalu sažima i prilagođava rečenice na srpskom kako bi se izgovorile u zadatom trajanju.
  2. Python Regex parser vrši brze determinističke gramatičke korekcije.
  3. Sobi podaci se upisuju u Redis bazu pod ključem `project:{project_id}:draft` sa trajanjem od 7 dana. Faza 1 je završena, a korisniku se otvara Studio interfejs.

---

### MEĐU-KORAK: INTERAKTIVNI STUDIO EDITOR (Rad u realnom vremenu)

Nakon završene Faze 1, korisnik radi u Studiju gde vrši izmene i fino podešavanje:

#### A. Uređivanje i AI Lektor (Čarobni štapić)
* **Proces:**
  1. Korisnik može ručno da edituje prevod u tekstualnom polju.
  2. Ako je srpski prevod duži od originala (indikator svetli crveno na timeline-u), klikom na **Čarobni štapić (`Wand2`)** šalje se zahtev na endpoint `/api/v1/project/{project_id}/segment/{segment_id}/shorten`.
  3. Backend poziva Qwen Lektora na Modalu sa preporučenim limitom karaktera (`duration * 20`) koji skraćuje srpsku rečenicu zadržavajući smisao. Novi skraćeni tekst se upisuje u polje.

#### B. Fino podešavanje zvuka po segmentima
* Za svaki segment korisnik može nezavisno da podešava:
  - **Jačina zvuka (Volume):** od `-20 dB` do `+10 dB`.
  - **Brzina govora (Tempo):** od `0.5x` do `2.0x`.
  - **Visina tona (Pitch):** od `-6` do `+6` semitona.
  - **Jačina pozadinske muzike (Ducking):** prigušivanje originalnog zvuka za taj konkretni segment od `-20 dB` do `+10 dB`.
* **Opcija "Primeni na sve":** Korisnik može jednim klikom da kopira ova zvučna podešavanja na sve segmente u projektu.

#### C. Brza proba glasa i Hot-Patching (Splicing)
* **Proces:**
  1. Klikom na dugme "Regeneriši Probni Glas" šalje se POST na `/tts` endpoint.
  2. Korisnik može izabrati tip glasa: **Piper muški glas (`male`)** ili **OpenVoice V2 klonirani glas (`clone`)**.
  3. *OpenVoice V2* koristi **VAD Fallback** (ako je govorni segment prekratak, isključuje VAD kako bi izbegao grešku) i **All-Segments Reference Audio** (gradi referentni glas spajajući isečke kroz ceo video umesto iz samo jednog segmenta).
  4. Generisani audio prolazi kroz FFmpeg procesor sa `rubberband` filterom za realtime tempo i pitch modifikacije.
  5. **Hot-Patching:** Ako već postoji spojeni sinhronizovani zvučni zapis za ceo video, backend vrši rezanje starog glasa i lepljenje novog u vokalni miks (splicing) pomoću `pydub`, te dodaje cache-buster parametar (`?cb=...`) na URL kako bi klijent bez seckanja reprodukcije čuo novi rezultat.

#### D. Realtime audio mikser na klijentu
* Na frontendu su aktivna **dva nezavisna plejera**: `dubbedAudioRef` (srpski vokali) i `bgAudioRef` (pozadinska muzika bez vokala).
* Tokom reprodukcije videa, klijentska petlja u 50ms intervalu detektuje izmene na slajderima i menja jačinu zvuka i playbackRate na oba plejera u realnom vremenu, čime se promena čuje momentalno i glatko, bez prekidanja reprodukcije.

---

### FAZA 2: RENDEROVANJE VIDEA (`render_video_task`)

Kada je korisnik zadovoljan izmenama u Studiju, on klikom na dugme "Renderuj" pokreće Fazu 2.

#### Korak 1: Pokretanje Renderovanja
* Korisnik šalje POST zahtev na `/api/v1/project/{project_id}/render`.
* API pokreće Celery zadatak `render_video_task`.

#### Korak 2: Batch generisanje glasa i obrada
* **Proces:**
  1. Sistem proverava koje segmente treba generisati i paralelno šalje zahteve na Modal za Piper/OpenVoice V2.
  2. Svi zvučni segmenti se procesiraju kroz FFmpeg `rubberband` i `volume` filtere primenjujući specifična zvučna podešavanja (Volume, Speed, Pitch) koja je korisnik definisao u Studiju.

#### Korak 3: Dinamičko Spajanje i Rastezanje (merger.py)
* **Proces:**
  1. Modul `merger.py` poredi trajanje svakog srpskog zvučnog zapisa sa dužinom njegovog vremenskog slota.
  2. Ako je srpski govor predugačak, video i pozadinska muzika se blago usporavaju (do 1.05x), a ako to nije dovoljno, vokal se ubrzava.
  3. Spajaju se svi vokali u `merged_vocals.wav`.
  4. Pozadinska muzika se prilagođava: primenjuje se globalni `background_vol` u pauzama, dok se u trenucima kada segmenti sviraju primenjuje zbir globalne jačine muzike i segment-specifične `bg_volume` (Ducking) vrednosti.

#### Korak 4: Sinhronizacija usana i Finalni miks (Wav2Lip)
* **Proces:**
  1. Opciono se pokreće Wav2Lip model na GPU za preciznu sinhronizaciju pokreta usana sa novim srpskim glasom.
  2. FFmpeg spaja rastegnuti video, finalne vokale i dinamički prigušeni pozadinski zvuk u jedan MP4 fajl (H264/AAC).
  3. Gotov video se čuva na S3 bucketu, a Celery zadatak dobija status `SUCCESS`.

---

## 3. Monitoring statusa i troškova

Tokom obe asinhronih Celery faza (`analyze_video_task` i `render_video_task`), klijent povlači metapodatke iz Redis baze, prateći napredak u procentima, aktivni GPU na Modalu i live procenjene troškove u dolarima.
