# Cevovod za Audio i Video Procesiranje

Ovaj dokument pruža detaljan tehnički opis cevovoda (pipeline) za obradu videa i zvuka unutar platforme **sinhronizuj.me**. Obuhvata procese od učitavanja sirovog videa, preko ekstrakcije traka, transkripcije, prevoda, sinteze i na kraju dinamičkog spajanja i renderovanja.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Arhitektura_Sistema]]
*   [[Baza_Podataka]]
*   [[Modal_Workers_i_AI]]
*   [[Backend_Dokumentacija]]

---

## 1. Cevovod Obrade Videa i Zvuka (Pipeline)

Proces obrade je visoko asinhron i podeljen na nekoliko koraka orkestriranih kroz Celery zadatak `analyze_video_task` u [tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py):

```
[Sirovi Video (S3)] 
       │
       ▼ (Preuzimanje na Celery Worker)
[Lokalni .mp4] 
       │
       ├─────────────────────────────────────────┐
       ▼ (Modal Demucs Worker)                   ▼ (Lokalni FFmpeg)
[Vokali (.wav)]  [Muzika/Šum bez vokala (.wav)]  [Vizuelni frejmovi]
       │                       │
       ▼ (Faster-Whisper)      │
       │                       │
       ▼ (Prevod + Lektor)     │
[Srpski Segmenti (Postgres)]   │
       │                       │
       ▼ (Uređivanje u DAW-u)  │
[Snimljeni Parametri]          │
       │                       │
       ▼ (Piper + OpenVoice)   │
[Sintetizovani Srpski Govor]   │
       │                       │
       └───────────────────────┼───────────────┐
                               ▼               ▼
                       [Audio Mikser] ---> [FFmpeg Video Spajanje] ---> [Finalni Video (S3)]
```

---

## 2. Separacija Audio Izvora (Demucs)

Kako bi se izbeglo da pozadinska muzika i zvučni efekti ometaju proces prepoznavanja govora (STT), i kako bi se dobila čista pozadinska matrica za finalni video, koristi se **Facebook Demucs v4 (Hybrid Transformer)** model na Modalu:
*   **Proces**: Celery radnik šalje audio traku izdvojenu iz videa Modal Demucs workeru.
*   **Rezultat**: Dobijaju se dva odvojena audio fajla:
    1.  `vocals.wav` (čist ljudski glas, koji se koristi za STT i kao uzorak za kloniranje glasa).
    2.  `no_vocals.wav` (pozadinski zvuci, muzika i efekti, koji se kasnije koriste kao zvučna podloga).

---

## 3. Transkripcija i Prevođenje sa Glosarima

### 3.1. Faster-Whisper i SenseVoice STT
Za prepoznavanje govora koristi se hibridni pristup na Modalu:
1.  **Faster-Whisper (large-v3)**: Pokreće se na Modalu ([stt_worker.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/stt_worker.py)) i predstavlja primarni ASR model. On generiše transkript sa preciznim vremenskim kodovima na nivou reči (word-level timestamps). Vidi [[Modal_Workers_i_AI]].
2.  **Alibaba SenseVoice-Small**: Pokreće se paralelno na Modalu ([sensevoice_worker.py](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers/sensevoice_worker.py)) i služi kao sekundarni ASR za detekciju interpunkcije, emocija i arbitražu.
3.  **LLM Arbitraža**: Dobijeni transkripti se šalju Modal Lektoru koji vrši korekciju Whisper segmenata na osnovu SenseVoice transkripta.

### 3.2. Prevod i Zamena Glosara
Nakon dobijanja izvornog transkripta, tekst prolazi kroz modul za prevođenje [translator.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/translator.py):
1.  **Mašinsko prevođenje**: Tekst se prevodi na srpski jezik pomoću naprednih LLM modela na Modalu (Qwen2-VL-7B-Instruct).
2.  **Primena Glosara**: Prevod se dodatno procesira kako bi se osigurala konzistentnost terminologije. Sistem čita:
    *   *Sistemski glosar* ([glossaries.json](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/glossaries.json)) za standardne termine.
    *   *Korisnički definisan glosar* iz baze podataka (tabela `glossaries` za trenutnog korisnika). Vidi [[Baza_Podataka]].
    *   Reči se dinamički zamenjuju pre slanja na TTS engine kako bi se izbegli pogrešni prevodi tehničkih ili brendiranih pojmova.

---

## 4. Sinteza Govora i Kloniranje Glasa

Za generisanje srpskog govora koristi se **Piper TTS** i **OpenVoice v2** tehnologija na Modalu:
*   **Kloniranje Glasa (`clone` opcija)**: OpenVoice izdvaja akustički potpis (style embedding) iz originalnog `vocals.wav` fajla za odgovarajući segment. Zatim se taj stil primenjuje na generisani srpski govor generisan preko Piper-a (srpski model Marko). Rezultat je srpski glas koji zvuči slično kao govornik u originalnom videu.
*   **Audio Poboljšanje (Resemble Enhance)**: CFM model (Resemble Enhance) dodatno otklanja šum i podiže frekvenciju na 44.1kHz.
*   **Generički Glasovi**: Korisnik može izabrati i standardne, pre-definisane glasove (npr. muški ili ženski) ukoliko je originalni glas lošeg kvaliteta.
*   **Parametri**: Kroz API se prenose parametri definisani od strane korisnika u DAW-u: jačina zvuka (`volume`), brzina (`speed`) i visina tona (`pitch`). Vidi [[Frontend_Dokumentacija]].

---

## 5. Dinamičko Miksovanje i Sklapanje Videa (`merger.py`)

Glavni izazov u automatskoj sinhronizaciji je činjenica da izgovoreni tekst na srpskom jeziku često ima različito trajanje od originalnog teksta na engleskom (srpski je u proseku 15-20% duži).

U modulu [merger.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/merger.py) implementirana je napredna logika za rešavanje ovog problema kroz funkciju `merge_audio_and_video_dynamic`:

1.  **Analiza Trajanja**: Za svaki segment se meri stvarno trajanje izgenerisanog srpskog audio fajla (`tts_duration`).
2.  **Automatska Kompresija Vremena (`speedup_audio_file`)**:
    Ako je generisani srpski audio duži od raspoloživog vremenskog okvira segmenta (od `start` do `end`), sistem izračunava potreban faktor ubrzanja:
    $$\text{faktor\_brzine} = \frac{\text{tts\_duration}}{\text{end} - \text{start}}$$
    Zatim se poziva FFmpeg filter `rubberband` da se audio ubrza kako bi se savršeno uklopio u zadati vremenski prozor, sprečavajući preklapanje sa narednim segmentima.
3.  **Kreiranje Audio Matrice (Pydub AudioSegment)**:
    *   Inicijalizuje se prazan audio kanal dužine originalnog videa.
    *   Pozadinski zvuk bez vokala (`no_vocals.wav`) se uvozi i na njega se primenjuje globalno podešena jačina zvuka (`background_vol`).
    *   Svi pojedinačni srpski audio segmenti se lepe na svoje tačne vremenske pozicije (`start` * 1000 ms) sa definisanim parametrima jačine (`volume` i prigušenje pozadine `bg_volume`).
4.  **LipSync Sinhronizacija (Wav2Lip)**:
    *   Ukoliko se detektuje dovoljno lica govornika, na Modalu se pokreće **Wav2Lip** model koji modifikuje pokrete usana govornika prema srpskom audio zapisu.
5.  **FFmpeg Video Spajanje**:
    Nakon što je kreirana finalna srpska audio traka, ona se spaja sa video trakom pomoću FFmpeg komande koja kopira video strim (bez rekompresije radi očuvanja kvaliteta i brzine) i mapira novi srpski audio:
    ```bash
    ffmpeg -y -i original_video.mp4 -i dubbed_audio.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k final_output.mp4
    ```
6.  **Otpremanje**: Finalni video se otprema na S3 skladište i dobija ključ `final_video_s3_key`.
