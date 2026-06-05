# 🤖 Detaljna Dokumentacija Compute Plane (Modal.com GPU Workers)

Računarski sloj (Compute Plane) platforme **Sinhronizuj.me** oslanja se na platformu **Modal.com** koja omogućava izvršavanje mašinskih modela na GPU serverless instancama. Modeli se pokreću kao nezavisni microservice-i, koristeći deljene mrežne fajl sisteme (Network File Systems - NFS) za keširanje modela i skladištenje privremenih podataka.

---

## 🛠️ Pregled Modal Resursa i Skaliranja

1.  **Scale-to-Zero**: Kada nema aktivnih projekata, svi Modal kontejneri se gase. Korisnik ne plaća prazan hod GPU resursa.
2.  **Hladni Start (Cold Start)**: Prilikom prvog zahteva nakon dužeg vremena, Modal inicijalizuje kontejner i učitava model u GPU memoriju. Za to vreme backend primenjuje pametan retry mehanizam (do 5 pokušaja sa rastućim kašnjenjem) i obaveštava korisnika kroz UI (`Inicijalizujem Modal radnika...`).
3.  **Mrežni fajl sistemi (NFS)**:
    *   `sinhronizuj-models` i `sinhronizuj-models-nfs` čuvaju snapshot-ove preuzetih modela sa Hugging Face-a kako bi se izbeglo preuzimanje gigabajta podataka pri svakom hladnom startu.

---

## 🎙️ Pojedinačni AI Radnici i Modeli

### 1. Separacija Zvuka (`demucs_worker.py`)
*   **Hardver**: NVIDIA T4 GPU.
*   **Model**: **HTDemucs v4** (Hybrid Transformer Demucs).
*   **Logika obrade**:
    *   Prima Base64 enkapsuliran audio zapis originalnog videa.
    *   Pokreće Demucs sa opcijom `--two-stems vocals`, čime se audio deli isključivo na dve trake: vokale (`vocals.wav`) i instrumental sa šumovima (`no_vocals.wav`). Ovo smanjuje vreme obrade i štedi memoriju u poređenju sa 4-stem separacijom (drum, bass, vocals, other).
    *   Vraća obe trake kodirane u Base64.

### 2. Transkripcija i Pozicioniranje (`stt_worker.py` & `sensevoice_worker.py`)
*   **Hardver**: NVIDIA T4 GPU.
*   **Model**: **Ensemble ASR** koji kombinuje **faster-whisper-large-v3** i **SenseVoice-Small**.
*   **Logika obrade**:
    *   **Whisper** vrši glavnu transkripciju engleskog jezika sa uključenim `word_timestamps=True` parametrom radi dobijanja tačnog početka i kraja svake reči. Koristi se VAD filter (Voice Activity Detection) sa minimalnim trajanjem govora od 250ms i padding-om od 400ms kako bi se izbeglo sečenje reči.
    *   **SenseVoice** vrši paralelnu analizu za bogatu detekciju netipičnih zvukova (uzdasi, smeh, aplauz, muzika) i preciznu interpunkciju.
    *   Sistem vrši arbitražu rezultata, čisti tekst i generiše konačan transkript sa reč-po-reč tajminzima.

### 3. Multimodalni Prevod (`translator_worker.py`)
*   **Hardver**: NVIDIA A10G GPU.
*   **Model**: **Qwen2-VL-7B-Instruct-AWQ** (pokreće se preko `vLLM` v0.6.3 OpenAI API servera radi ekstremne brzine).
*   **Logika obrade**:
    *   Pored engleskog teksta transkripta, prevodilac prima 10 izvučenih ključnih frejmova iz videa u Base64 formatu.
    *   Model koristi vizuelni kontekst da odredi rod govornika (muško/žensko) i vizuelne detalje iz videa kako bi prevod na srpski jezik bio gramatički ispravan (npr. da li reći "video sam" ili "videla sam", u zavisnosti od osobe na ekranu).
    *   Zadržava precizne vremenske prozore segmenata.

### 4. Lektura i Dinamički Glosar (`lektor_worker.py`)
*   **Hardver**: NVIDIA A10G / A100-40GB GPU.
*   **Model**: **Qwen3-32B-AWQ** (vLLM server sa uključenim `enable-prefix-caching` i `enable-chunked-prefill`).
*   **Logika obrade**:
    *   Lektor vrši ekavizaciju, ispravlja gramatičke greške, rešava deklinaciju stranih imena i transformiše rečenice u "ti-formu" obraćanja (prirodan ton za sinhronizaciju).
    *   Primenjuje korisnički i sistemski glosar iz `glossaries.json` za stručne termine (npr. prepoznaje tehničke termine i menja ih adekvatnim srpskim prevodima).
    *   Čisti tekst od dijalektizama i nepoželjnih karaktera.
    *   **Optimizacija dužine konteksta**: Veličina batch-a je ograničena na 10 segmenata po pozivu sa `max_tokens=800` i limitom konteksta od 4096 tokena na Modalu, što sprečava rušenje modela kod dužih promptova.

### 5. Sinteza Govora i Kloniranje Glasa (`tts_openvoice.py`)
Ovo je jedan od najkompleksnijih delova Compute Plane-a:
*   **Hardver**: NVIDIA L4 GPU.
*   **Modeli**: **Piper TTS** (srpski model Marko `sr_Marko_medium`), **OpenVoice V2 ToneColorConverter** i **Resemble Enhance**.
*   **Logika obrade**:
    1.  **Bazna Sinteza**: Piper TTS generiše bazni govor na srpskom jeziku koristeći Marko model. Dobija se čist, ali generički srpski muški glas na 22050Hz.
        *   **Dinamički Piper tempo (`length_scale`)**: Brzina govora se ne menja naknadno FFmpeg filterom (koji stvara metalan prizvuk), već se na osnovu dužine teksta i rezervisanog video vremena računa idealan odnos brzine i šalje Piperu kao parametar `length_scale` (klampovan na `[0.75, 1.25]`). Piper generiše audio direktno u odgovarajućem tempu sa ispravnim trajanjem fonema.
    2.  **Tone Color Conversion**: Ukoliko je odabrano kloniranje glasa (`voice_type == "clone"`), OpenVoice V2 vrši ekstrakciju Speaker Embedding-a (SE) iz referentnog uzorka. Zatim vrši transfer boje glasa (tone color mapping) sa Marko modela na ciljani glas.
        *   **Referentni uzorak (Speaker Embedding)**: Da bi se izbegao metalan šum i fazna izobličenja koja Demucs unosi u izolovane vokale, OpenVoice V2 uzima **originalni audio zapis** videa kao referencu. OpenVoice-ov interni VAD (Voice Activity Detector) uspešno ignoriše pozadinsku muziku i izvlači čist Speaker Embedding.
        *   **Automatsko spajanje referentnih segmenata**: Sistem automatski skuplja više govornih segmenata (ukupno 8+ sekundi govora) i spaja ih u celovitu referencu. Spajanje se vrši sa `fade_in(50)` i `fade_out(50)` (50ms) i `crossfade=100` (100ms) u pydub-u kako bi se sprečilo pucketanje i oštri rezovi signala na spojevima.
    3.  **Poboljšanje Zvuka (Resemble Enhance)**: Sintetizovani i klonirani audio se propušta kroz CFM (Conditional Flow Matching) model koji vrši denoise (uklanjanje šuma) i bandwidth extension (rekonstrukcija visokih frekvencija na 44.1kHz). Korišćeni su CFM parametri: `nfe=64`, `solver="midpoint"`, `lambd=0.9` i `tau=0.3` (smanjena temperatura sa 0.5 na 0.3 radi veće stabilnosti i prirodnosti srpskog govora).
    4.  **Paralelizacija**: Zadatak podržava paralelnu obradu do 8 segmenata istovremeno pomoću `ThreadPoolExecutor`-a.

---

## 🎵 FFmpeg Audio Splicing & Mixer Popravka (`backend/worker/merger.py`)

Tokom audio miksanja i spajanja u gotov video snimak, vokalni segmenti prolaze kroz sledeće faze:
1.  **Visokokvalitetna promena brzine (Rubber Band)**: Kada je potrebno dodatno ubrzanje ili usporavanje, koristi se napredni `rubberband` filter umesto standardnog `atempo` filtera, čime se eliminiše jeka i robotski prizvuk.
2.  **Audio Post-processing lanac**:
    *   **Resampling** na 44100 Hz.
    *   **Highpass filter (80Hz)** za uklanjanje niskofrekventne buke.
    *   **Lowpass filter (12kHz)** za otklanjanje visokofrekventnih artifakata i šuma.
    *   **Dynamic Range Compressor (compand)** za izjednačavanje glasnoće.
    *   **Room Reverb (aecho)** sa minimalnim kašnjenjem od 15ms kako bi se glas prirodno stopio sa pozadinskim zvucima videa.
3.  **Popravka FFmpeg Stream Duplication baga (asplit)**:
    U FFmpeg-u je neispravno koristiti istu audio labelu više puta u istom filter_complex grafikonu bez eksplicitnog splita (npr. i za `sidechaincompress` i za `amix`). To je ranije dovodilo do toga da FFmpeg ignoriše vokalni strim i umesto njega ubaci originalni engleski audio.
    Problem je trajno rešen uvođenjem `asplit` filtera koji vokal deli na dva nezavisna strima:
    ```text
    [vocal_in]asplit=2[voc1][voc2]
    ```
    Strim `[voc1]` se prosleđuje u kompresor za stišavanje pozadinske muzike (ducking), a `[voc2]` se šalje direktno u mikser (`amix`) za spajanje sa instrumentalom.
