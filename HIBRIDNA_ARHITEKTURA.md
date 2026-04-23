# Sinhronizuj.me SaaS: Strateški i Tehnički Plan Tranzicije

Ovaj dokument predstavlja detaljnu mapu puta za prelazak "Sinhronizuj.me" (ranije Sinhronizuj.me) platforme iz on-demand prototipa u **produkciono spremnu SaaS aplikaciju visoke skalabilnosti**, koristeći hibridnu cloud arhitekturu.

---

## 🏗️ 1. Pregled Nove Arhitekture (Hybrid Cloud)

Umesto da držimo skupe grafičke kartice upaljene 24/7 za celokupan sistem, razdvajamo sistem na dva dela:

### A) Kontrolni Čvor (Hetzner VPS) - "Mozak"
Ovo je jeftin, uvek dostupan (24/7) server koji obavlja sve što ne zahteva GPU.
*   **Frontend (React/Vite):** Korisnički interfejs dostupan korisnicima non-stop.
*   **Backend (FastAPI):** API za komunikaciju, autentifikaciju i naplatu.
*   **Baza Podataka (PostgreSQL):** Čuvanje korisničkih naloga, istorije projekata i prevoda.
*   **Object Storage (MinIO):** Lokalni S3-kompatibilni storage za čuvanje otpremljenih videa i generisanih audio fajlova. Izbegava skupe AWS cene za prenos podataka.

### B) Računarski Čvorovi (RunPod Serverless) - "Mišići"
Ovo su "radnici" bez stanja (stateless) koji se pale samo kada stigne zadatak.
*   **Serverless Endpointi:** Podižu se po potrebi. Ako 10 korisnika pošalje video u isto vreme, RunPod automatski podiže 10 GPU-ova u pozadini.
*   **Plaćanje po sekundi:** Plaćamo GPU isključivo onoliko sekundi koliko traje izdvajanje vokala, transkripcija i XTTS sinteza.

---

## ✨ 2. Ključne Nove Funkcionalnosti

### A) Direktan Video Upload (Bypass YouTube-a)
Umesto "mačke i miša" sa YouTube blokadama, dodajemo direktan **Drag & Drop Upload**. 
*   **Tehnologija:** Koristi se MinIO **Presigned URL**. React frontend dobija privremeni ključ i otprema fajl *direktno* u bazu, bez opterećivanja Hetzner backenda.
*   **Prednost:** Nula rizika od banovanja IP adresa. Otvaramo tržište za privatne videe (TikTok, Instagram, korporativne prezentacije). YouTube link ostaje samo kao opcija preko sistemskog `cookies.txt` fajla, ali nije primarni fokus.

### B) Google Authentikacija (OAuth2)
Implementacija opcije "Sign in with Google".
*   **Prednost:** Eliminiše potrebu za pravljenjem šifri. Brz onboarding korisnika.
*   **SaaS Potencijal:** Omogućava nam praćenje potrošnje (krediti/minute) po korisniku za buduću komercijalizaciju i naplatu.

---

## 🗺️ 3. Plan Implementacije u 4 Faze

### Faza 1: Laboratorija (Trenutni fokus na On-Demand RunPodu)
Pre selidbe u kompleksan sistem, "srce" AI obrade mora raditi savršeno. Ovu fazu radimo na trenutnom setup-u.
1.  **Dizajniranje Upload UI-a:** Dodavanje "Drag & Drop" polja pored YouTube linka.
2.  **Implementacija privremenog uploada:** Lokalno čuvanje fajla na RunPod server dok ne pređemo na MinIO.
3.  **Usavršavanje Pipeline-a:** Testiranje sa dugim videima. Popravljanje tačnosti prevoda i sinhronizacije XTTS-a usana (lip-sync).
4.  *Cilj:* Pipeline u jednom prolazu dobija video sa računara i vraća savršen lokalizovan video bez ijednog pucanja koda.

### Faza 2: Postavljanje SaaS Temelja (Hetzner)
1.  Zakup Hetzner VPS-a (npr. CX32 ili sličan).
2.  Postavljanje Docker Compose mreže (FastAPI, PostgreSQL, Redis, MinIO).
3.  Implementacija Google OAuth2 na frontendu i backendu.
4.  Implementacija MinIO Presigned URL logike za upload.

### Faza 3: Serverless Migracija (RunPod)
1.  Pakovanje naših Python skripti (`audio_sep.py`, `transcriber.py`, `tts_engine.py`) u jedan masivan Docker Image prilagođen za RunPod Serverless SDK.
2.  Podešavanje handlera koji: skine fajl sa našeg MinIO servera -> provuče kroz AI modele -> vrati obradjen fajl u MinIO bazu.
3.  Kreiranje Serverless Endpointa na RunPod portalu.

### Faza 4: Integracija i Produkcija
1.  Konektovanje Hetzner FastAPI-ja sa RunPod Serverless Endpointom.
2.  Podešavanje domena, SSL sertifikata (HTTPS).
3.  Testiranje sistema na višekorisničko opterećenje.
4.  Lansiranje Alpha verzije sistema.
