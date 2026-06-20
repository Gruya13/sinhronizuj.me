# Sveobuhvatna Tehnička Dokumentacija (sinhronizuj.me)

Dobrodošli u centralni dokument tehničke dokumentacije za platformu **sinhronizuj.me** — napredno rešenje za automatsku sinhronizaciju i kloniranje glasa na video materijalima.

Ovaj dokument objedinjuje sve aspekte sistema, uključujući arhitekturu, bazu podataka, frontend klijent, backend server, cevovode za audio i video obradu, veštačku inteligenciju (AI) i celokupnu DevOps i infrastrukturnu specifikaciju.

---

## Sadržaj i Brzi Linkovi

1.  [Arhitektura Sistema i Baza Podataka](file:///home/gruya/Projektri/sinhronizuj.me/doc/arhitektura_i_baza.md)
2.  [Dokumentacija Frontend Aplikacije](file:///home/gruya/Projektri/sinhronizuj.me/doc/frontend_dokumentacija.md)
3.  [Dokumentacija Backend Sloja](file:///home/gruya/Projektri/sinhronizuj.me/doc/backend_dokumentacija.md)
4.  [Audio i Video Procesiranje](file:///home/gruya/Projektri/sinhronizuj.me/doc/audio_i_video_procesiranje.md)
5.  [Veštačka Inteligencija i Modal Radnici](file:///home/gruya/Projektri/sinhronizuj.me/doc/modal_workers_i_ai.md)
6.  [Infrastruktura i DevOps](file:///home/gruya/Projektri/sinhronizuj.me/doc/infrastruktura_i_devops.md)
7.  [Uputstvo za Backup i Restore](file:///home/gruya/Projektri/sinhronizuj.me/doc/backup_restore_uputstvo.md)

---

## 1. Arhitektura Sistema i Baza Podataka

### 1.1. Troslojni Model
Platforma je strukturisana kroz tri glavna sloja kako bi se postigla visoka skalabilnost i asinhronost rada:
*   **Klijentski Sloj (Vite + React)**: Koristi Vanilla CSS, stakleni dizajn i HTML5 Audio API za upravljanje DAW zvučnim sesijama.
*   **Orkestracioni Sloj (FastAPI + Celery + Redis)**: API gateway i pozadinski radnici na hostu koji kontrolišu i prate dugotrajne poslove, rukuju bazom podataka i spajaju izvozne video/audio strimove.
*   **AI Računarski Sloj (Modal Serverless)**: Dinamički GPU klaster za separaciju vokala, prepoznavanje govora (STT), prevođenje i sintezu/kloniranje glasa (TTS).

### 1.2. PostgreSQL Šema Baze i SQLAlchemy Modeli
Baza koristi PostgreSQL i definisana je preko sledećih SQLAlchemy klasa:
*   **`User`**: Upravljanje registrovanim korisnicima, hešovanim lozinkama i administratorskim statusom (`is_admin`).
*   **`Project`**: Čuva meta-podatke o video fajlovima, statuse obrade (`empty`, `analyzing`, `ready`, `completed`), S3 ključeve i troškove na Modalu.
*   **`Segment`**: Vremenski segmenti sa originalnim transkriptom, srpskim prevodom, izabranim parametrima zvuka (brzina, jačina, pitch) i putanjama do generisanih zvučnih zapisa.
*   **`Glossary`**: Korisnički rečnici za zamenu specifičnih reči prilikom prevođenja.
*   **`Waitlist`**: Evidencija i odobravanje prijava za zatvorenu beta fazu aplikacije.

> [!NOTE]
> Baza je u potpunosti integrisana sa **Alembic** migracionim alatom pod šablonom `autogenerate` koji omogućava automatsku detekciju izmena modela sa host mašine i migraciju bez gubitka podataka u produkciji.

---

## 2. Frontend Aplikacija (React / Vite)

Klijentski deo aplikacije je strukturisan da obezbedi interaktivno DAW (Digital Audio Workstation) iskustvo u realnom vremenu:

### 2.1. Centralne Komponente
*   **`LandingPage`**: Uvodna prezentaciona stranica za neprijavljene posetioce.
*   **`StudioTimeline`**: Crta zvučne talase i omogućava vizuelnu navigaciju kroz video i audio zapise.
*   **`SegmentEditor`**: Editor segmenata u kojem korisnik koriguje prevode i podešava pitch/speed/volume za svaki sintetizovani glas.
*   **`AudioMixer`**: Slajderi za kontrolu nivoa jačine zvuka vokala i pozadinske muzike.
*   **`AdminPanel`**: Administratorski panel za upravljanje waitlistom, korisnicima i praćenje projekata sa live logovima Celery radnika.

### 2.2. Globalno Upravljanje Stanjem i Undo/Redo
Globalno stanje je izolovano unutar `StudioContext.jsx`. Za potrebe Studija implementiran je **Undo/Redo istorijski stek** sa maksimalnim kapacitetom od 50 stanja, čime se omogućava brzo poništavanje grešaka prilikom uređivanja prevoda ili parametara glasa.

### 2.3. Responzivnost za Mobilne Uređaje
Aplikacija je u potpunosti responzivna. Na mobilnim uređajima se fiksne visine DAW interfejsa zamenjuju tekućim rasporedom, kontrole se preslažu u 2x2 grid, a informacije o serverima u zaglavlju se sažimaju u kompaktne statusne ikonice.

---

## 3. Backend Aplikacija (FastAPI)

FastAPI obezbeđuje visokoperformansni API gateway sa naprednim zaštitama i asinhronom komunikacijom:

*   **JWT Autentifikacija**: Autentifikacija korisnika preko bezbednih hešovanih lozinki i tokena sa trajanjem od 60 minuta.
*   **Rate Limiting (SlowAPI)**: Zaštita osetljivih ruta (waitlist, login, registracija) od brute-force napada ograničavanjem broja zahteva po IP adresi.
*   **Celery Integracija**: Preusmeravanje teških poslova obrade u Redis red poruka, osiguravajući da API gateway ostane slobodan i brz za sve korisnike.
*   **Hardware Monitor**: API periodično prikuplja podatke o statusu veze sa Redisom, iskorišćenosti sistemskih resursa hosta i statusu Modal serverless GPU instanci.
*   **Sentry SDK**: Integrisano praćenje grešaka u realnom vremenu za FastAPI i Celery, što omogućava brzu dijagnostiku u produkciji.

---

## 4. Audio i Video Cevovod (Pipeline)

Sistem implementira sledeći tok obrade za svaki video:

1.  **Direct S3 Upload**: Klijent dobija pre-potpisan URL i otprema video direktno na S3.
2.  **Audio Separacija**: Modal Demucs razdvaja zvučni zapis na vokale i pozadinsku muziku/zvučne efekte bez vokala.
3.  **Transkripcija**: **Faster-Whisper (large-v3)** vrši brzu transkripciju vokala sa milisekundnim tajminzima na nivou reči, dok se **SenseVoice-Small** koristi za sekundarnu transkripciju i LLM arbitražu.
4.  **Prevođenje**: Tekst se prevodi na srpski, a pre slanja na TTS automatski se primenjuje sistemski i korisnički glosar za očuvanje terminologije.
5.  **Glasovna Sinteza**: Poziva se **Piper TTS** i Modal **OpenVoice v2** za generisanje srpskog govora sa parametrima jačine, brzine i visine tona, uz kloniranje glasa originalnog govornika.
6.  **Dinamičko Spajanje (`merger.py`)**: FFmpeg i pydub dinamički uklapaju srpski govor. Ukoliko je srpska rečenica duža od originalnog segmenta, ona se automatski ubrzava (`speedup_audio_file`) kako bi se uklopila i sprečila desinhronizaciju. Zatim se na VPS-u vrši **LipSync (Wav2Lip)** ako ima dovoljno lica, video i pozadinska muzika se stišavaju (ducking) i po potrebi se video i muzika blago usporavaju (maksimalno do 1.05x). Sve se miksuje sa pozadinskom muzikom i spaja sa video strimom bez gubitka kvaliteta slike.

---

## 5. Veštačka Inteligencija i Modal Resursi

AI modeli se izvršavaju na serverless Modal platformi, što omogućava nulte troškove u mirovanju (scale-to-zero) i brzo skaliranje:

*   **Faster-Whisper i SenseVoice-Small**: Govor-u-tekst (ASR/STT) modeli za transkripciju i arbitražu.
*   **Demucs v4**: Separacija instrumenata i vokala.
*   **Piper TTS & OpenVoice v2**: Sinteza glasa i prenos stila.
*   **Qwen2-VL-7B-Instruct**: Mašinsko prevođenje.
*   **Qwen Lektor**: Lektura, ekavizacija i arbitraža.

### 5.1. Analiza Troškova i Warmup Strategija
*   **Troškovi**: Ukupna obrada 5 minuta videa (separacija, STT, translacija i klonirani TTS) na Modalu košta **manje od 0.03 USD** (oko 3 dinara), što platformu čini ekonomski izuzetno održivom.
*   **Warmup**: Inicijalni hladni start (cold start) od 10-15 sekundi se eliminiše pozivanjem `/api/v1/warmup` endpointa čim korisnik otvori Studio, čime se kontejneri drže spremnim ("warm") za trenutno izvršavanje.

---

## 6. Infrastruktura i DevOps

Aplikacija se razvija i isporučuje kroz strukturisani DevOps pipeline:

### 6.1. VPS Serveri
*   **Development VPS**: `98.76.54.32` (povezan sa `development` granom na GitHub-u).
*   **Production VPS**: `12.34.56.78` (povezan sa `main` granom).
*   **Sigurnost**: Nginx SSL reverse proxy, Cloudflare proxy zaštita i mrežni UFW firewall.

### 6.2. Docker Compose lokalni servisi i produkcioni kontejneri
Zajedničko pokretanje servisa vrši se kroz kontejnere:
*   `sinhronizuj-db` (Postgres, port 5432)
*   `sinhronizuj-redis` (Redis, port 6379)
*   `sinhronizuj-api` (FastAPI web server, port 8000)
*   `sinhronizuj-celery` (Celery pozadinski radnik)
*   `sinhronizuj-frontend` (Nginx, port 3000 za produkciju, servira kontejnerizovane React/Vite resurse)

### 6.3. CI/CD GitHub Actions Workflows
*   [backend-ci.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/backend-ci.yml): Automatski pokreće Python pytest integracione testove prilikom svakog push-u.
*   [frontend-ci.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/frontend-ci.yml): Instalira zavisnosti i pokreće frontend unit testove (`npm run test:run`).
*   [deploy.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/deploy.yml): Automatski gradi Docker slike nakon prolaska testova, vrši push na GHCR, te na Hetzner VPS-u povlači slike i radi deploy preko SSH.
*   [release.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/release.yml): Automatski kreira GitHub Release sa generisanim beleškama o izmenama na push-u na `main` granu.
*   **Backup**: Cron posao svake noći u 02:00h vrši backup PostgreSQL baze i šalje ga na MinIO S3 bucket sa rotacijom i automatskim brisanjem arhiva starijih od 7 dana.

---

## 7. Uputstvo za Backup i Restore

Za detaljna uputstva o procedurama ručnog backup-ovanja, vraćanja podataka (restore) i rotacije arhiva, pogledajte [Uputstvo za Backup i Restore](file:///home/gruya/Projektri/sinhronizuj.me/doc/backup_restore_uputstvo.md).
