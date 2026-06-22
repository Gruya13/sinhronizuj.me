# Funkcionalnosti MOC

Ovaj dokument je mapa sadržaja za sve beleške koje se tiču funkcionalnosti i softverskih modula platforme **sinhronizuj.me**.

## 🗺️ Sadržaj
*   [[00_MOC_Index]] – Nazad na početak
*   [[Audio_i_Video_Procesiranje]] – Ceo pipeline obrade: Demucs, Faster-Whisper, SenseVoice, Piper, OpenVoice, i FFmpeg merger.
*   [[Backend|Backend Dokumentacija]] – FastAPI Gateway rute, zaštićene admin rute, JWT autentifikacija, Redis/Celery radnici.
*   [[Frontend|Frontend Dokumentacija]] – React/Vite klijent, struktura komponenti, Studio DAW interfejs, StudioContext undo/redo.
*   [[Modal_Workers_i_AI]] – Modal serverless GPU klaster, optimizacija troškova obrade i cold start warmup.
*   [[Prevodilacki_Pipeline|Prevodilački Pipeline]] – Segment-level i sentence-level optimizacije, prevođenje sa RAG-om i LLM-as-a-Judge gating.
*   [[Sistem_Samounapredjenja|Sistem Samounapređenja]] – Zatvorena petlja učenja (Feedback Loop) kroz real-time TM, DBSCAN pattern miner i LoRA fine-tuning.
