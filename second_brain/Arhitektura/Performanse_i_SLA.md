# Performanse i SLA Standardi

Ovaj dokument definiše standarde performansi (benchmarks) i SLA (Service Level Agreement) vremenske limite za obradu video materijala na platformi **sinhronizuj.me**.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Arhitektura_MOC]]
*   [[Arhitektura_Sistema]]

---

## 1. SLA Vremenski Limiti po Formatu Videa

U zavisnosti od dužine ulaznog video fajla, definisani su sledeći SLA vremenski limiti za kompletan proces obrade (Faza 1 - Analiza + Faza 2 - Render):

| Format Videa | Dužina Videa | Očekivano Vreme Obrade | Maksimalni SLA Limit | Celery Timeout (`time_limit`) |
| :--- | :--- | :--- | :--- | :--- |
| **Kratak video** | do 2 minuta | < 1.5 min | **3 minuta** (180s) | 2400s (zaštita od prekida) |
| **Srednji video** | do 10 minuta | < 6 min | **12 minuta** (720s) | 2400s (zaštita od prekida) |
| **Dug video** | do 30 minuta | < 20 min | **40 minuta** (2400s) | 2400s |

---

## 2. Profilisanje Performansi po Fazama Obrade

Sledeći benchmark rezultati su izmereni nad test videom dužine **72 sekunde** (1.2 minuta):

### Faza 1: Analiza (Pre-processing & Transkripcija)
*   **Demucs (Separacija vokala)**: ~5-10 sekundi (Modal serverless, zavisi od cold start-a).
*   **Active Speaker Precompute**: ~4.5 sekundi (sekvencijalno skeniranje i MediaPipe ekstrakcija).
*   **Diarization & Gender Detection**: ~1.5 sekundi (keširani `pydub` rezovi).
*   **ASR Transkripcija (Whisper/SenseVoice)**: ~5-15 sekundi.
*   **Ukupno vreme Faze 1**: **~30 sekundi** (ispoljeno prema korisniku).

### Faza 2: Sinteza i Render (Prevod, TTS & Wav2Lip)
*   **Hibridni Prevod (RAG + Qwen 32B)**: ~15-25 sekundi (zavisi od broja segmenta i provere kontradiktornosti).
*   **Piper + OpenVoice TTS**: ~10-15 sekundi (Modal serverless).
*   **Wav2Lip LipSync**: ~20-30 sekundi (Modal serverless, procesira samo aktivne segmente selektivno).
*   **FFmpeg video/audio mix**: ~2-3 sekunde.
*   **Ukupno vreme Faze 2**: **~60 sekundi** (ispoljeno prema korisniku).

---

## 3. Celery Timeout Konfiguracija

Celery zadaci u [tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py) su konfigurisani sa maksimalnim limitom od **40 minuta (2400 sekundi)** i mekim limitom od **38.3 minuta (2300 sekundi)**:
*   `analyze_video_task`: `time_limit=2400`, `soft_time_limit=2300`
*   `render_video_task`: `time_limit=2400`, `soft_time_limit=2300`

Ova konfiguracija osigurava da se dugački video fajlovi (do 30 minuta) uspešno završe čak i u slučaju hladnog starta (cold start) više Modal radnika i eventualnih mrežnih retransmisija na S3 skladište, dok istovremeno sprečava beskonačno blokiranje Celery radnika pri fatalnim sistemskim izuzecima.
