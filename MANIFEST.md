# Projekat: Sinhronizuj.me (Inteligentna AI Sinhronizacija Videa)

**Namena:** Automatizovan sistem za preuzimanje YouTube videa, pametno prevođenje, kloniranje glasa i opcionu vizuelnu sinhronizaciju usana (Lip Sync) na srpski jezik.

## Arhitektura sistema (Pipeline)

### Faza 0: Pametno mapiranje videa (Pre-scan)
- Sistem analizira 1 frejm po sekundi koristeći `MediaPipe`.
- Kreira "Mapu vremena" (Timeline) gde se detektuje prisustvo lica. Ovo sprečava trošenje resursa na Screencast delove videa gde voditelj nije na ekranu.

### Faza 1: Preuzimanje (Download)
- Alat: `yt-dlp`
- Video se obavezno preuzima u HD rezoluciji (do 1080p).
- Sirovi audio se ekstrahuje iz videa.

### Faza 2: AI Separacija Zvuka (Vocal Isolation)
- Alat: `Demucs`
- Zvučna traka se deli na:
  1. Čist ljudski glas (`vocals.wav`).
  2. Pozadinska muzika i efekti (`background.wav`).

### Faza 3: Transkripcija (Speech-to-Text)
- Alat: `faster-whisper`
- Sluša se samo `vocals.wav` kako bi se izbegle halucinacije.
- Generiše se precizan engleski tekst i tajminzi.

### Faza 4: Kontekstualna Analiza i Pametni Prevod (LLM)
- Alat: LLM (npr. Gemini / GPT-4 API)
- Sistem analizira temu videa i ton govornika.
- Pravi se dinamička lista stručnih termina koji se **ne smeju prevoditi** (npr. frontend, framework).
- Generiše se prirodan prevod na srpski jezik.

### Faza 5: Kloniranje Glasa i Sinteza (Text-to-Speech)
- Alat: `XTTS v2`
- Sistem uzima referentni isečak glasa iz `vocals.wav` (5-10 sekundi).
- Klonira se glas originalnog govornika i generiše se srpski izgovor prema tajminzima.

### Faza 6: Opcioni Lip Sync i Izoštravanje lica
- Alat: `Wav2Lip` + `GFPGAN`
- **Pravilo ranog izlaza:** Ako Mapa Lica (Faza 0) pokaže da lice nije na ekranu tokom govora, cela ova faza se **preskače** i modeli se ne učitavaju.
- Ako postoji presek lica i govora, usne se sinhronizuju samo za te kadrove. Usne se izoštravaju koristeći GFPGAN.

### Faza 7: Završni Miks i Generisanje videa
- Alat: `FFmpeg` / `Pydub`
- Srpski glas se meša sa `background.wav` uz primenu "Audio Ducking" efekta.
- Kreira se konačan `.mp4` fajl.

## Hardverske i Softverske Optimizacije
1. **Sekvencijalno učitavanje modela:** Izbegava se preopterećenje VRAM-a; modeli se brišu iz memorije nakon završenog posla.
2. **Multiprocessing:** Paralelna obrada segmentiranih videa (npr. komadi od 1 minut) na raspoloživim radnicima.
3. **Optimizacija detekcije (VAD + Face Map):** Lip Sync se pali samo kada su u preseku ispunjeni i prisustvo lica i prisustvo glasa.

## Procena vremena obrade (Processing Time)
*Za prosečan video od 5 minuta na preporučenom hardveru:*
- **Standardni mod (samo audio dubbing):** ~2 do 4 minuta.
- **Premium mod (uključen Lip Sync lica):** ~6 do 8 minuta (zahvaljujući optimizacijama preskakanja tišine i mapiranju lica).

## Sistemski zahtevi (System Requirements)
- **Minimalno:** 
  - Grafička kartica: NVIDIA GPU sa **8 GB VRAM-a** (npr. RTX 3060)
  - Sistemska memorija: 16 GB RAM
  - Skladište: SSD
- **Preporučeno (za produkciju/brzu obradu):**
  - Grafička kartica: NVIDIA GPU sa **12+ GB VRAM-a** (npr. RTX 3080 / 4070 ili iznajmljeni Cloud GPU)
  - Sistemska memorija: 32 GB RAM
  - Skladište: brzi NVMe M.2 SSD disk
