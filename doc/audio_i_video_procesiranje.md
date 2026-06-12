# Audio i Video Procesiranje (sinhronizuj.me)

Ovaj dokument pruža detaljan tehnički opis cevovoda (pipeline) za obradu videa i zvuka unutar platforme **sinhronizuj.me**. Obuhvata procese od učitavanja sirovog videa, preko ekstrakcije traka, transkripcije, prevoda, sinteze i na kraju dinamičkog spajanja i renderovanja.

---

## 1. Cevovod Obrade Videa i Zvuka (Pipeline)

Proces obrade je visoko asinhron i podeljen na nekoliko koraka orkestriranih kroz Celery zadatak `analyze_video_task` u [backend/worker/tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py):

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
       ▼ (Modal SenseVoice)    │
[Transkript sa tajminzima]     │
       │                       │
       ▼ (Prevod + Glosari)    │
[Srpski Segmenti (Postgres)]   │
       │                       │
       ▼ (Uređivanje u DAW-u)  │
[Snimljeni Parametri]          │
       │                       │
       ▼ (Modal OpenVoice TTS) │
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

### 3.1. SenseVoice STT
Za prepoznavanje govora koristi se **Alibaba SenseVoice Large** model na Modalu, koji podržava više jezika (engleski, ruski, španski, kineski, itd.) i pruža izuzetno brzu transkripciju sa milisekundnom preciznošću vremenskih kodova za svaki segment rečenice.

### 3.2. Prevod i Zamena Glosara
Nakon dobijanja izvornog transkripta, tekst prolazi kroz modul za prevođenje [backend/worker/translator.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/translator.py):
1.  **Mašinsko prevođenje**: Tekst se prevodi na srpski jezik pomoću naprednih LLM modela na Modalu.
2.  **Primena Glosara**: Prevod se dodatno procesira kako bi se osigurala konzistentnost terminologije. Sistem čita:
    *   *Sistemski glosar* ([backend/worker/glossaries.json](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/glossaries.json)) za standardne termine.
    *   *Korisnički definisan glosar* iz baze podataka (tabela `glossaries` za trenutnog korisnika).
    *   Reči se dinamički zamenjuju pre slanja na TTS engine kako bi se izbegli pogrešni prevodi tehničkih ili brendiranih pojmova.

---

## 4. Sinteza Govora i Kloniranje Glasa

Za generisanje srpskog govora koristi se **OpenVoice v2** i **MeloTTS** tehnologija na Modalu:
*   **Kloniranje Glasa (`clone` opcija)**: OpenVoice izdvaja akustički potpis (style embedding) iz originalnog `vocals.wav` fajla za odgovarajući segment. Zatim se taj stil primenjuje na sintetizovani srpski govor generisan preko MeloTTS-a. Rezultat je srpski glas koji zvuči identično kao govornik u originalnom videu.
*   **Generički Glasovi**: Korisnik može izabrati i standardne, pre-definisane glasove (npr. muški ili ženski) ukoliko je originalni glas lošeg kvaliteta.
*   **Parametri**: Kroz API se prenose parametri definisani od strane korisnika u DAW-u: jačina zvuka (`volume`), brzina (`speed`) i visina tona (`pitch`).

---

## 5. Dinamičko Miksovanje i Sklapanje Videa (`merger.py`)

Glavni izazov u automatskoj sinhronizaciji je činjenica da izgovoreni tekst na srpskom jeziku često ima različito trajanje od originalnog teksta na engleskom (srpski je u proseku 15-20% duži). 

U modulu [backend/worker/merger.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/merger.py) implementirana je napredna logika za rešavanje ovog problema kroz funkciju `merge_audio_and_video_dynamic`:

1.  **Analiza Trajanja**: Za svaki segment se meri stvarno trajanje izgenerisanog srpskog audio fajla (`tts_duration`).
2.  **Automatska Kompresija Vremena (`speedup_audio_file`)**:
    Ako je generisani srpski audio duži od raspoloživog vremenskog okvira segmenta (od `start` do `end`), sistem izračunava potreban faktor ubrzanja:
    $$\text{faktor\_brzine} = \frac{\text{tts\_duration}}{\text{end} - \text{start}}$$
    Zatim se poziva FFmpeg filter `atempo` (ili pydub ekvivalent) da se audio ubrza kako bi se savršeno uklopio u zadati vremenski prozor, sprečavajući preklapanje sa narednim segmentima.
3.  **Kreiranje Audio Matrice (Pydub AudioSegment)**:
    *   Inicijalizuje se prazan audio kanal dužine originalnog videa.
    *   Pozadinski zvuk bez vokala (`no_vocals.wav`) se uvozi i na njega se primenjuje globalno podešena jačina zvuka (`background_vol`).
    *   Svi pojedinačni srpski audio segmenti se lepe na svoje tačne vremenske pozicije (`start` * 1000 ms) sa definisanim parametrima jačine (`volume` i prigušenje pozadine `bg_volume`).
4.  **FFmpeg Video Spajanje**:
    Nakon što je kreirana finalna srpska audio traka, ona se spaja sa video trakom pomoću FFmpeg komande koja kopira video strim (bez rekompresije radi očuvanja kvaliteta i brzine) i mapira novi srpski audio:
    ```bash
    ffmpeg -y -i original_video.mp4 -i dubbed_audio.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k final_output.mp4
    ```
5.  **Otpremanje**: Finalni video se otprema na S3 skladište i dobija ključ `final_video_s3_key`.
