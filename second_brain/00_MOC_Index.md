# 🧠 sinhronizuj.me - Second Brain Index (MOC)

Dobrodošli u centralni trezor znanja (Second Brain) projekta **sinhronizuj.me**. Ovaj wiki služi za beleženje arhitekture, funkcionalnosti, dnevnog napretka i rešavanja tehničkih izazova.

---

## 🧭 Mape Sadržaja (Maps of Content)

### 🏗️ [[Arhitektura_MOC|1. Arhitektura Sistema]]
Sve o tehničkom dizajnu, infrastrukturi, bazi podataka i komunikaciji između komponenti.
*   [[Arhitektura_Sistema]] – Troslojna arhitektura i tok podataka.
*   [[Baza_Podataka]] – SQLAlchemy modeli, UUID ključevi i Alembic migracioni tok.

### ⚙️ [[Funkcionalnosti_MOC|2. Funkcionalnosti & Moduli]]
Detaljni tehnički opisi pojedinačnih delova sistema i AI modela.
*   [[Audio_i_Video_Procesiranje]] – Demucs vokalna izolacija, SenseVoice STT, lektorisanje i FFmpeg audio-video renderovanje.
*   [[Backend_Dokumentacija]] – FastAPI gateway, rute, autentifikacija, Redis i Celery orkestracija.
*   [[Frontend_Dokumentacija]] – React/Vite Studio DAW interfejs, upravljanje stanjem i undo/redo mehanizam.
*   [[Modal_Workers_i_AI]] – Serverless GPU infrastruktura na Modal klasteru i AI modeli.

### 📝 [[Dnevnik_Rada_MOC|3. Dnevnik Rada & Istorija]]
Hronološki zapisi o razvoju i implementacijama.
*   [[Istorija_Izrade_MOC]] – Centralni MOC za sve sesije i promene na projektu.
*   [istorija_izrade.md](file:///home/gruya/Projektri/sinhronizuj.me/istorija_izrade.md) – Glavna datoteka istorije projekta.

### 🛠️ [[Rešavanje_Problema_MOC|4. Rešavanje Problema & DevOps]]
Baza znanja o greškama, rešenjima i uputstvima za razvoj.
*   [[Docker_i_Infrastruktura]] – Docker-compose konfiguracija, environment varijable i deploy proces.
*   [[Česta_Pitanja_i_Bagovi]] – Zapisani bagovi i rešenja (npr. problemi sa video analizom, temp fajlovima).

---

## 🤖 Za AI Agente
Ako ste AI agent koji radi na ovom projektu, **obavezno** pročitajte [[AI_Agent_Guidelines]] pre nego što započnete bilo kakve izmene na kodu ili dokumentaciji.
