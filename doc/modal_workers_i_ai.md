# Veštačka Inteligencija i Modal Radnici (sinhronizuj.me)

Ovaj dokument pruža tehničke detalje o AI infrastrukturi platforme **sinhronizuj.me**, sa fokusom na serverless radnike pokrenute na Modal platformi, izbore modela, optimizaciju performansi i analizu troškova GPU-a.

---

## 1. Zašto Modal?

Modal je izabran kao primarna platforma za izvršavanje AI modela iz sledećih razloga:
1.  **Serverless model (Scale-to-Zero)**: Kontejneri sa teškim modelima i GPU zahtevima se pokreću samo kada postoji aktivan zadatak obrade. Kada nema poslova, resursi se gase, što smanjuje fiksne troškove infrastrukture na nulu.
2.  **Brzo podizanje (Fast Cold Starts)**: Modal poseduje visoko optimizovan sistem za keširanje slojeva kontejnera, što omogućava da se GPU kontejneri podignu za manje od 5-10 sekundi.
3.  **Fleksibilan izbor GPU hardvera**: Moguće je definisati tačan tip GPU-a za svaki pojedinačni zadatak (od jeftinijih Nvidia T4 do moćnih L4 i A10G kartica).

---

## 2. Pregled Modal Radnika i AI Modela

U direktorijumu [modal_workers/](file:///home/gruya/Projektri/sinhronizuj.me/modal_workers) nalaze se definicije serverless kontejnera i koda koji se izvršava na Modalu:

### 2.1. Separacija vokala (`demucs_worker.py`)
*   **Model**: Facebook Demucs v4 (Hybrid Transformer).
*   **GPU zahtev**: Nvidia T4 (16GB VRAM) ili L4.
*   **Funkcija**: Prihvata audio traku i vrši razdvajanje na čiste vokale (`vocals`) i prateću matricu (`no_vocals`).

### 2.2. Prepoznavanje govora (`stt_worker.py` / `sensevoice_worker.py`)
*   **Modeli**: Faster-Whisper (large-v3) na `stt_worker.py` i Alibaba SenseVoice-Small na `sensevoice_worker.py`.
*   **GPU zahtev**: Nvidia T4.
*   **Karakteristike**: Faster-Whisper je primarni ASR model koji generiše transkript sa preciznim vremenskim kodovima na nivou reči (word-level timestamps). SenseVoice-Small je sekundarni ASR model bez vremenskih kodova, koji služi za transkripciju celog vokala i naknadnu LLM arbitražu radi ispravke grešaka.

### 2.3. Prevođenje (`translator_worker.py`)
*   **Model**: Qwen2-VL-7B-Instruct-AWQ (Vision-Language model pokrenut preko vLLM OpenAI API-ja).
*   **GPU zahtev**: Nvidia A10G (24GB VRAM) za vLLM kvantizovani model.
*   **Funkcija**: Prevodi transkribovane segmente na srpski jezik uz očuvanje prirodnog tona govora.

### 2.4. Kloniranje i Sinteza glasa (`tts_openvoice.py` / `tts.py`)
*   **Modeli**: Piper TTS (srpski model Marko) i OpenVoice v2 (razvijen od strane MyShell-a).
*   **GPU zahtev**: Nvidia L4 (24GB VRAM) ili A10G za brzu paralelnu sintezu.
*   **Funkcija**:
    *   `Piper TTS` generiše osnovni srpski govor na osnovu prevedenog teksta (model Marko koji daje prirodan izgovor).
    *   `OpenVoice` uzima kratak uzorak originalnog glasa iz `vocals.wav` (oko 3-5 sekundi je dovoljno), izvlači stil (tone color converter) i primenjuje ga na generisani srpski govor. Krajnji rezultat je klonirani glas na srpskom jeziku koji zadržava jedinstvenu boju glasa originalnog govornika.

### 2.5. Lektura teksta (`lektor_worker.py`)
*   **Funkcija**: Brza provera gramatike i stila prevedenog teksta na srpskom jeziku pre nego što se pošalje na zvučnu sintezu.

### 2.6. LipSync vizuelna sinhronizacija (`wav2lip_worker.py`)
*   **Model**: Wav2Lip.
*   **GPU zahtev**: Nvidia T4 (16GB VRAM) sa NFS skladištem za keširanje modela.
*   **Funkcija**: Ugrađen je serverless radnik koji vrši fotorealističnu sinhronizaciju pokreta usana na osnovu spojenog srpskog govora i originalnog videa, čime se eliminiše potreba za izvođenjem teške Wav2Lip inferencije na lokalnom VPS-u.

---

## 3. Optimizacija Troškova GPU-a po Videu

Na osnovu testiranja obavljenih na platformi, troškovi obrade su izuzetno optimizovani zahvaljujući pažljivom odabiru hardvera za svaki zadatak:

| Zadatak | Hardver (Modal) | Vreme Izvršavanja (5 min video) | Cena po satu | Procenjena Cena po videu (5 min) |
| :--- | :--- | :--- | :--- | :--- |
| **Demucs Separacija** | Nvidia T4 (GPU) | ~30 sekundi | $0.59 / h | ~$0.005 |
| **STT Transkripcija** | Nvidia T4 (GPU) | ~15 sekundi | $0.59 / h | ~$0.003 |
| **Prevođenje** | Nvidia A10G (GPU) | ~10 sekundi | $1.10 / h | ~$0.003 |
| **OpenVoice TTS (Kloniranje)**| Nvidia L4 (GPU) | ~60 sekundi (paralelno) | $1.25 / h | ~$0.021 |
| **Wav2Lip LipSync** | Nvidia T4 (GPU) | ~90 sekundi (selektivno) | $0.59 / h | ~$0.015 |
| **Sklapanje Videa (FFmpeg)** | CPU (Shared na hostu) | ~15 sekundi | - (Host resurs) | $0.000 |
| **Ukupno** | - | **~3.7 minuta** | - | **~$0.047 (oko 5.5 dinara)** |

> [!TIP]
> Prosečna cena obrade 5-minutnog videa iznosi **manje od 0.05 USD (oko 5.5 dinara)**. Čak i pod maksimalnim opterećenjem i dužim hladnim startovima, trošak ne prelazi **0.07 USD** po videu, što platformu sinhronizuj.me čini izuzetno profitabilnom i skalabilnom za masovnu upotrebu.


---

## 4. Upravljanje Hladnim Startom (Cold Start Mitigation)

Kada klijent pošalje zahtev za analizu nakon dužeg perioda neaktivnosti, Modal kontejneri moraju da prođu kroz proces inicijalizacije ("cold start"). To može dodati 10-15 sekundi na početno vreme obrade.

Kako bi se ovo eliminisalo tokom aktivnog rada korisnika, implementirana je **Warmup strategija**:
1.  **Detekcija Aktivnosti**: Čim korisnik uđe u DAW Studio ili Dashboard, frontend šalje asinhroni zahtev na `/api/v1/warmup` endpoint.
2.  **Zagrevanje Radnika**: FastAPI u pozadini poziva Modal i inicira minimalne zahteve prema Demucs i TTS kontejnerima.
3.  **Spremnost**: Kada korisnik završi sa unosom videa ili klikne na generisanje audia, Modal kontejneri su već podignuti i spremni ("warm"), te izvršavaju zadatke u realnom vremenu (sub-sekundni odziv).
4.  **Auto-gašenje**: Ako nema novih zahteva u roku od 5 minuta, Modal automatski gasi kontejnere kako ne bi trošio resurse.
