# Pravna i Etička Usklađenost — Projekat sinhronizuj.me
**Datum:** 20. jun 2026.  
**Faza:** Pre-launch priprema za javno lansiranje (P4)  
**Uloga:** Legal & Ethical Compliance Officer

---

## 1. Uvod i Svrha Analize

Projekat **sinhronizuj.me** je inovativna platforma za automatizovanu video sinhronizaciju sa engleskog na srpski jezik. Kako bi se obezbedio legalan izlazak na tržište i zaštitila intelektualna svojina, privatnost korisnika i reputacija projekta, sprovedena je detaljna pravna i etička analiza. 

Ovaj izveštaj pokriva tri ključna stuba usklađenosti pre javnog lansiranja (P4):
1. **Licence AI modela** koji se koriste u pipeline-u i strategiju za eliminaciju nekomercijalnih licenci.
2. **Zaštitu i kontrolu kloniranja glasa** u cilju sprečavanja zloupotrebe i neovlašćene impersonacije.
3. **Usklađenost sa GDPR-om i EU AI Act-om**, sa posebnim fokusom na transfer biometrijskih i ličnih podataka na serverless GPU platformu Modal (SAD) iz Hetzner (EU) infrastrukture.

---

## 2. Analiza Licenci AI Modela

U sistemu se trenutno koristi sedam ključnih AI modela na kontrolnoj ravni (VPS) i računarskoj ravni (Modal). Ispod je detaljna tabela usklađenosti licenci za komercijalnu upotrebu:

### Tabela Usklađenosti Licenci

| Model | Funkcija u Sistemu | Lokacija Izvršavanja | Zvanična Licenca | Komercijalna Upotreba | Status / Akcija |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **Wav2Lip** | LipSync (Usklađivanje usana) | Lokalni VPS (Docker) | CC BY-NC-SA 4.0 | ❌ **Zabranjeno** | **Kritičan rizik.** Mora se zameniti komercijalno dozvoljenom alternativom. |
| **Demucs v4** | Separacija vokala i muzike | Modal (T4 GPU) | MIT |  **Dozvoljeno** | Potpuno usklađeno. Nema akcije. |
| **Faster-Whisper** | Primarni STT (vremenski kodovi) | Modal (T4 GPU) | MIT (kod i tegovi) |  **Dozvoljeno** | Potpuno usklađeno. Nema akcije. |
| **SenseVoice Small**| Sekundarni ASR (arbitraža) | Modal (T4 GPU) | Apache 2.0 |  **Dozvoljeno** | Potpuno usklađeno. Nema akcije. |
| **Qwen2-VL (7B)** | Vizuelno-jezičko prevođenje | Modal (A10G GPU) | Apache 2.0 |  **Dozvoljeno** | Potpuno usklađeno. Nema akcije. |
| **Piper TTS** | Bazna sinteza govora (Marko) | Modal (L4 GPU) | MIT (kod i većina glasova) |  **Dozvoljeno** | Potpuno usklađeno. Potvrditi licencu izvornog dataset-a za model Marko. |
| **OpenVoice v2** | Kloniranje i prenos boje glasa | Modal (L4 GPU) | MIT (od feb 2024.) |  **Dozvoljeno** | Usklađeno sa stanovišta koda, ali nosi pravne rizike zloupotrebe glasa. |

---

### Detaljna Analiza Kritičnih Modela i Alternative

#### 2.1. Wav2Lip (Kritičan Rizik)
*   **Problem:** Wav2Lip model je razvijen od strane istraživačkog centra IIIT Hyderabad i licenciran je pod *Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International* (CC BY-NC-SA 4.0) licencom. To eksplicitno zabranjuje bilo kakvu komercijalnu eksploataciju modela (naplatu usluga korisnicima, B2B integracije itd.).
*   **Predložene Komercijalno Dozvoljene Alternative:**
    1.  **SadTalker (MIT Licenca):** Generiše 2D animacije lica na osnovu jedne slike i audio fajla. Kod i tegovi su potpuno otvoreni za komercijalnu upotrebu. Odličan je za statične slike ili avatar video sinhronizaciju, ali ima ograničenja kod dinamičnih videa sa pokretima glave.
    2.  **Custom Obučeni Wav2Lip Model:** Sama arhitektura Wav2Lip-a je javno opisana. Može se iskoristiti čista open-source re-implementacija koda (npr. licencirana pod MIT ili Apache 2.0 na GitHub-u), a tegovi modela se mogu obučiti od nule koristeći komercijalno čiste setove podataka (npr. javno dostupni video snimci sa slobodnim licencama, LRS3 dataset pod uslovima akademske dozvole ili sopstveni snimljeni video studio materijali).
    3.  **GeneFace / GeneFace++ (MIT Licenca):** Napredna 3D talking-head tehnologija zasnovana na NeRF-u, koja pruža izuzetan realizam i stabilnost pokreta usana, potpuno pod MIT licencom.
    4.  **Eksterni API Fallback (Tavus / HeyGen API):** Komercijalno rešenje gde se teški render prenosi na licencirane enterprise platforme uz plaćanje po minutu.
*   **Preporuka za sinhronizuj.me:** Kratkoročno onemogućiti automatski Wav2Lip LipSync za komercijalne pakete dok se ne završi obuka sopstvenog modela na komercijalno čistom datasetu, ili ponuditi SadTalker kao alternativni pipeline za avatare.

#### 2.2. OpenVoice v2 (Usklađen, ali Visokorizičan)
*   **Status:** MyShell.ai je u februaru 2024. prebacio OpenVoice v2 pod **MIT licencu**. Sa stanovišta intelektualne svojine na softver, komercijalna upotreba je legalna.
*   **Etički rizik:** Kloniranje nečijeg glasa bez njegove dozvole može prekršiti prava ličnosti, autorska prava i zakone protiv prevara. Zbog toga su neophodne stroge tehničke i administrativne kontrole.

---

## 3. Voice Cloning Kontrole (Sprečavanje Zloupotrebe)

Kloniranje glasa (Voice Cloning) je tehnologija visokog rizika. Kako bismo sprečili neovlašćeno kreiranje deepfake sadržaja i zloupotrebu tuđeg identiteta, definišu se sledeće politike i tehnički mehanizmi kontrole:

### 3.1. Atestacija Prava i Aktivna Verifikacija Pristanka (Active Consent Verification)
Samo štikliranje kućice "Imam dozvolu za korišćenje ovog glasa" nije dovoljno na sudu. Uvodi se troslojni sistem verifikacije:
1.  **Deklarativna atestacija:** Korisnik prilikom otvaranja projekta mora potpisati elektronsku izjavu pod krivičnom i materijalnom odgovornošću da poseduje prava na audio zapis i glas koji se klonira.
2.  **Aktivna verifikacija (za custom glasove):** Ako korisnik želi da klonira sopstveni glas ili glas saradnika za stalnu upotrebu, sistem zahteva **verifikaciju uživo**. Korisnik mora u mikrofon pročitati dinamički generisan, jedinstveni tekst (npr. *"Ja, [Ime], svesno dozvoljavam platformi sinhronizuj.me da klonira moj glas za potrebe prevođenja dana 20.06.2026."*). Sistem upoređuje akustički potpis te izjave sa referentnim videom pre nego što dozvoli kloniranje.
3.  **Arhiviranje metapodataka:** Svaki klonirani glas se trajno povezuje sa ID-em verifikovanog korisnika i njegovim nalogom u bazi podataka.

### 3.2. Anti-Impersonation (Sprečavanje Lažnog Predstavljanja)
1.  **Zabrana javnih ličnosti:** Zabranjeno je kloniranje glasova političara, glumaca, novinara i drugih javnih ličnosti bez pisane autorizacije.
2.  **Baza otisaka (Voice ID Blacklist):** Implementacija laganog klasifikatora koji poredi referentni audio sa bazom poznatih glasova (npr. poznati političari i glumci u Srbiji i regionu). Ako podudaranje prelazi 85%, sistem automatski blokira obradu i šalje projekat na manuelnu reviziju.

### 3.3. Audio Watermarking (Vodeni Žig)
U skladu sa zahtevima EU AI Act-a, svaki audio fajl generisan kroz Piper + OpenVoice v2 mora sadržati **neraskidivi vodeni žig (watermark)**:
*   **Tehnologija:** Implementacija alata poput **AudioSeal** (Meta AI, pod BSD licencom koja dozvoljava komercijalnu upotrebu). AudioSeal ugrađuje steganografski (nečujan za ljudsko uvo) vodeni žig direktno u audio talas.
*   **Otpornost:** Vodeni žig je otporan na kompresiju (MP3), promenu brzine (time stretching) i FFmpeg mešanje sa pozadinskom muzikom.
*   **Svrha:** Omogućava bilo kom trećem licu ili platformi da pomoću jednostavnog javnog detektora potvrdi da je audio generisan na platformi `sinhronizuj.me` i da je reč o sintetičkom glasu.

### 3.4. Takedown Procedura
*   Uspostavljanje stranice `sinhronizuj.me/report` gde bilo koji građanin može prijaviti sumnju na neovlašćeno kloniranje svog glasa.
*   **SLA za uklanjanje:** U roku od maksimalno 24 sata od prijave, sporni projekat se privremeno blokira, a administrator vrši uvid u verifikacione dokumente korisnika. Ako korisnik ne dostavi dokaz o saglasnosti, klonirani model i generisani video se trajno brišu.

---

## 4. Privatnost i GDPR Usklađenost

Kloniranje glasa i modifikacija lica zahtevaju obradu biometrijskih i ličnih podataka. Budući da se podaci prenose iz EU (Hetzner VPS u Nemačkoj/Finskoj) na serverless GPU platformu Modal (SAD), moraju se primeniti stroge mere zaštite.

### 4.1. Pravna Kvalifikacija Podataka
*   **Glasovni snimak (Vocals) i Video lica:** Spadaju u lične podatke. Ukoliko se vrši ekstrakcija jedinstvenih fizioloških i biometrijskih karakteristika (poput *speaker embedding* vektora za kloniranje glasa ili mapiranja tačaka na licu za LipSync), ovi podaci se mogu smatrati **biometrijskim podacima** (Član 9 GDPR-a - posebne kategorije podataka).
*   **Pravni osnov za obradu (Član 6 i Član 9 GDPR):** Primarni pravni osnov je **izričiti pristanak korisnika (Consent)** za obradu njegovih ličnih i biometrijskih podataka u svrhu video sinhronizacije, ili **izvršenje ugovora** (za B2B klijente koji su prethodno pribavili pristanak svojih govornika).

### 4.2. Transfer Podataka na Modal (SAD)
Modal Labs, Inc. je američka kompanija sa serverima primarno u SAD. Prenos podataka na Modal predstavlja transfer u treću zemlju.
*   **Neophodne Pravne Mere:**
    1.  **Data Processing Agreement (DPA):** Potpisivanje ugovora o obradi podataka sa Modal platformom.
    2.  **Standardne Ugovorne Klauzule (SCCs):** Integrisanje najnovijih SCC-ova usvojenih od strane Evropske komisije za transfer kontrolor-obrađivač (Module 2) ili obrađivač-podobrađivač (Module 3).
    3.  **Transfer Impact Assessment (TIA):** Sprovođenje procene uticaja transfera kako bi se osiguralo da zakoni SAD (npr. FISA Član 702) ne ugrožavaju prava građana EU na nivo zaštite ekvivalentan GDPR-u.
*   **Preporučene Tehničke Mere:**
    1.  **Lokalizacija u EU (Modal EU):** Modal omogućava postavljanje radnika u specifičnim cloud regijama. Gde god je moguće, konfigurisati Modal taskove da se vrte na AWS ili GCP serverima lociranim u EU (npr. Frankfurt, Dublin).
    2.  **Minimizacija prenesenih podataka:**
        *   **NE slati kompletan video fajl na Modal.** Video ostaje na Hetzner VPS-u. Na Modal se šalje isključivo ekstraktovani audio zapis (`vocals.wav`) radi separacije i STT-a.
        *   Čak i za prevođenje (Qwen2-VL), na Modal slati samo ključne frejmove (frames) niske rezolucije umesto punog video strima, kako bi se očuvao kontekst a minimizovao prenos vizuelnih podataka ličnosti.
    3.  **Zero-Retention Politika (Politika bez zadržavanja):**
        *   Svi fajlovi preneseni na Modal (putem S3 presigned URL-ova ili direktnog payload-a) moraju se čuvati isključivo u radnoj memoriji (RAM) GPU kontejnera ili u privremenom direktorijumu `/tmp` koji se automatski uništava čim se kontejner ugasi (scale-to-zero).
        *   Modal ne sme vršiti nikakvo trajno keširanje ili skladištenje audio/video materijala naših korisnika na svojim diskovima ili trajnim volumenima.

---

## 5. Usklađenost sa EU AI Act-om

Evropski parlament je usvojio EU AI Act koji reguliše sisteme veštačke inteligencije na osnovu nivoa rizika. **sinhronizuj.me** potpada pod sisteme sa specifičnim rizikom od transparentnosti (sintetički mediji).

### 5.1. Klasifikacija i Obaveze
*   **Tip AI sistema:** Generisanje sintetičkog audio i video sadržaja (Deepfake / Sintetički mediji).
*   **Član 52 (EU AI Act):** Pružaoci AI sistema koji generišu sintetički audio, slikovni ili video sadržaj moraju osigurati da su izlazi sistema označeni u mašinski čitljivom formatu i da se mogu detektovati kao veštački generisani.
*   **Izuzetak:** Ukoliko je sadržaj deo umetničkog, kreativnog ili kinematografskog dela, obaveze transparentnosti se mogu prilagoditi kako ne bi ometale prikazivanje, ali mašinska detektabilnost (vodeni žig) ostaje obavezna.

### 5.2. Konkretne obaveze za lansiranje (P4):
1.  **Vidljiva oznaka (Disklajmer):** Svaki video koji se izveze sa platforme sinhronizuj.me mora imati opcioni vizuelni vodeni žig u uglu (npr. mali logo ili tekst *"Sinhronizovano pomoću sinhronizuj.me AI"*) ili, ako korisnik plati za uklanjanje vodenog žiga, u metapodacima fajla (EXIF/XMP) mora stajati trajno upisan tag da je video generisan veštačkom inteligencijom.
2.  **Nevidljivi audio žig:** Obavezna integracija AudioSeal-a (kao što je opisano u sekciji 3.3).
3.  **Evidencija o proceni rizika:** Dokumentovanje interne procene uticaja sistema na osnovna prava (Fundamental Rights Impact Assessment - FRIA) koja pokazuje da sistem ne služi za manipulaciju ponašanjem korisnika ili širenje dezinformacija.

---

## 6. Akcioni Plan i Preporuke za P4 Lansiranje

Kako bismo u potpunosti pokrili pravne i etičke rizike, preporučuje se implementacija sledećih koraka pre zvaničnog javnog puštanja platforme u rad:

### Korak 1: Rezolucija Wav2Lip Licence (Odmah)
*   **Akcija:** U `backend/worker/lipsync.py` i konfiguracionim fajlovima privremeno onemogućiti Wav2Lip procesiranje za sve komercijalne korisnike. Uvesti fallback na originalni video bez modifikacije usana (ili sa blagim time-stretchingom) dok se ne obuči čist custom model ili ne integriše SadTalker (MIT).
*   **Zadatak za dev tim:** Istražiti prelazak na komercijalno usklađen LipSync pipeline zasnovan na SadTalker-u ili GeneFace++ do kraja P4 faze.

### Korak 2: Integracija Audio Metapodataka i Vodenog Žiga (Srednji rok - tokom P4)
*   **Akcija:** Integrisati biblioteku `audioseal` u Modal worker `tts_openvoice.py`. Svaki generisani segment automatski propustiti kroz AudioSeal generator pre slanja nazad na Hetzner.
*   **Akcija 2:** Pomoću FFmpeg-a, prilikom sklapanja videa (`merger.py`), u metapodatke MP4 kontejnera upisati tag: `comment=Synchronized by AI using sinhronizuj.me`.

### Korak 3: Pravna Dokumentacija i Korisnički Tok (Pre lansiranja)
*   **Akcija:** Na frontend-u (Studio / SegmentEditor) pre pokretanja kloniranja glasa, prikazati pop-up prozor sa jasnim tekstom o autorskim pravima i dugmetom za potvrdu saglasnosti.
*   **Akcija 2:** Sastaviti zvaničnu "Politiku privatnosti i obaveštenje o biometrijskoj obradi" u saradnji sa pravnim savetnikom i postaviti je na sajt.
*   **Akcija 3:** Poslati zvaničan zahtev Modal podršci za potpisivanje standardnog DPA ugovora sa ugrađenim Standardnim ugovornim klauzulama (SCC).

---
*Izveštaj pripremio:*  
**LegalComplianceAgent**  
*Projekat sinhronizuj.me*
