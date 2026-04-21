# Istorija izrade projekta Daca Dub

- **2026-04-21 08:05** - Postavljena osnovna arhitektura sistema (Manifest). Završen inicijalni brainstorming, definisane faze obrade videa (yt-dlp, Demucs, Whisper, LLM prevod, XTTS v2) i dogovorene ključne optimizacije performansi uključujući rani izlazak iz opcionog Lip Sync modula. Kreiran `MANIFEST.md`.
- **2026-04-21 08:12** - Inicijalizovan Git repozitorijum sa povezanim origin repozitorijumom (Gruya13/daca_dub). Kreiran `.gitignore` fajl radi zaštite API ključeva. Ažuriran manifest sa hardverskim zahtevima i vremenskim prognozama obrade. Odrađen prvi push na `development` granu.
- **2026-04-21 08:23** - Kreirana osnovna struktura Backend-a. Definisan `requirements.txt` fajl sa osnovnim bibliotekama. Napravljen kostur FastAPI aplikacije (`main.py`) i konfigurisan Celery radnik (`celery_app.py`, `tasks.py`) za upravljanje pozadinskim zadacima.
- **2026-04-21 08:25** - Implementirana **Faza 1**: Kreirana `downloader.py` skripta koristeći `yt-dlp`. Skripta preuzima video u visokoj rezoluciji (do 1080p), automatski ekstrahuje `.wav` fajl i zadržava originalni video u `temp_workspace` folderu. Celery radnik je uspešno povezan sa ovim modulom.
