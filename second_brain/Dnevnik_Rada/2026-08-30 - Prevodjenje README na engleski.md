# 2026-08-30 - Prevođenje README dokumentacije na engleski jezik

Glavna `README.md` datoteka repozitorijuma na GitHubu je u potpunosti prevedena sa srpskog jezika na tečan i profesionalan engleski jezik kako bi repozitorijum bio internacionalno dostupan.

## Povezane Beleške
* [[00_MOC_Index]]
* [[Istorija_Izrade_MOC]]
* [README.md](file:///home/gruya/Projektri/sinhronizuj.me/README.md)
* [istorija_izrade.md](file:///home/gruya/Projektri/sinhronizuj.me/istorija_izrade.md)

## Detaljan Opis / Tehnički Detalji
1. **Prevedeni moduli i sekcije**:
   - **Glavni opis**: Pregled hibridne VPS + Modal.com cloud arhitekture.
   - **Ključne karakteristike (Key Features)**: Modularni React DAW Studio, Sentence-level re-segmentacija, Multi-turn critique, LLM-as-a-Judge, Piper TTS + OpenVoice v2 kloniranje glasa, Resemble Enhance i dinamičko uklapanje vremena (`merger.py`).
   - **Mermaid dijagram**: Ažurirani nazivi slojeva i servisa na engleskom (Client Layer, Network & Security, Hetzner VPS, Modal Serverless GPU, CI/CD Pipeline).
   - **Tehnološki stack**: Tabelarni pregled tehnologija i modela (Demucs v4, Faster-Whisper, SenseVoice, Mistral Small 24B, Piper, OpenVoice v2, Wav2Lip).
   - **Struktura repozitorijuma**: Kompletno stablo sa opisima komponenti na engleskom jeziku.
   - **Lokalno pokretanje i testiranje**: Uputstva za Docker, Postgres, Redis, Alembic migracije, FastAPI gateway, Celery worker i Vite frontend.
   - **Konfiguracija (`.env`)**: Primer konfiguracije sa engleskim komentarima za sve parametre.
   - **Plan daljeg razvoja (Roadmap)**: Diarizacija, HD Face Restoration za Wav2Lip i interaktivni waveform timestretch.

2. **CI/CD i linter verifikacija**:
   - Pokrenuti su `pytest` (25 testova uspešno prošlo), `ruff check --select=E9,F63,F7,F82` (0 grešaka) i `bandit -r backend/ -ll` (0 bezbednosnih ranjivosti).

## Istorijat Izmena
* **2026-08-30**: Prevođenje README.md sa srpskog na engleski jezik - [[AI Agent]]
