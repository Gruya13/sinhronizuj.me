# Dokumentacija Frontend Aplikacije (sinhronizuj.me)

Ovaj dokument pruža detaljan pregled klijentskog dela aplikacije **sinhronizuj.me**, koji je implementiran u tehnologiji React sa Vite-om. Dokument pokriva organizaciju komponenti, upravljanje stanjem, mehanizme interakcije u Studiju, dizajn sistem i proces testiranja.

---

## 1. Tehnički Stack i Dizajn Sistem

*   **Jezgro**: React.js 18+ i Vite kao alat za razvoj i build.
*   **Stilizacija**: Vanilla CSS ([frontend/src/index.css](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/index.css)) za maksimalnu kontrolu performansi i responzivnosti.
*   **Aestetika**: Moderni tamni mod sa elementima staklenog dizajna (**glassmorphism**), prelivima boja (gradients), mikro-animacijama pri prelasku mišem (hover effects) i custom stilizovanim skrolovima.
*   **Ikone**: Standardni Unicode emotikoni kako bi se smanjila zavisnost od spoljnih biblioteka i ubrzalo učitavanje.
*   **Audio biblioteke**: HTML5 Audio API integrisan kroz React hook-ove za preciznu reprodukciju, pauziranje i pretragu (seeking) audio segmenata na vremenskoj liniji.

---

## 2. Struktura Komponenti

Frontend je podeljen na modularne komponente grupisane po funkcionalnim oblastima unutar direktorijuma `frontend/src/components/`:

### 2.1. Admin Komponente (`Admin/`)
*   [AdminPanel.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Admin/AdminPanel.jsx): Sveobuhvatan administrativni interfejs koji sadrži:
    *   *Dashboard*: Prikaz sistemskih metrika (ukupni korisnici, waitlist na čekanju, projekti, iskorišćenost CPU/GPU-a).
    *   *Waitlist*: Tabela prijava za zatvorenu betu sa opcijama za odobravanje i odbijanje korisnika.
    *   *Korisnici*: Upravljanje registrovanim korisnicima i dodela administratorskih privilegija.
    *   *Projekti*: Pregled svih projekata u sistemu sa ugrađenom pretragom i detaljnim uvidom u sistemske logove pozadinskih radnika (Celery logovi).

### 2.2. Autentifikacija (`Auth/`)
*   [LoginRegister.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Auth/LoginRegister.jsx): Staklena kartica za prijavu postojećih i preusmeravanje novih korisnika. Klikom na registraciju novog naloga, korisnik se automatski preusmerava na formu za prijavu u zatvorenu betu (waitlist), čime se sprečava nekontrolisana registracija.

### 2.3. Dashboard (`Dashboard/`)
*   [DashboardView.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Dashboard/DashboardView.jsx): Centralni klijentski ekran koji prikazuje listu projekata korisnika, formu za unos novog videa (putem direktnog otpremanja) i modal sa pre-vizuelizacijom pre-procesiranja.
*   [ProjectList.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Dashboard/ProjectList.jsx): Prikazuje kartice sa korisničkim projektima, njihovim statusima (`empty`, `analyzing`, `ready`, `completed`) i opcijama za brisanje ili otvaranje u Studiju.

### 2.4. Studio (`Studio/`)
*   [StudioTimeline.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Studio/StudioTimeline.jsx): Vizuelni editor vremenske linije (timeline) koji crta audio talase originalnog videa i omogućava vizuelnu navigaciju, zumiranje i kontrolu trenutne pozicije reprodukcije.
*   [SegmentEditor.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Studio/SegmentEditor.jsx): Glavni urednički panel u kome korisnik modifikuje prevode, menja tipove glasa i podešava napredne parametre za svaki pojedinačni vremenski segment. Podržava i grupne operacije.
*   [AudioMixer.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Studio/AudioMixer.jsx): Klizači (sliders) za podešavanje jačine originalnog (vocals) i sintetizovanog zvuka (TTS) na globalnom nivou projekta.
*   [MixerPanel.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Studio/MixerPanel.jsx): Vizuelne kontrole i EQ/efekti za napredno miksovanje kanala u realnom vremenu.

### 2.5. Landing Komponente (`Landing/`)
*   [LandingPage.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Landing/LandingPage.jsx): Prezentaciona landing stranica koja upoznaje neprijavljene posetioce sa uslugom, prikazuje ključne funkcionalnosti i preusmerava ih na formu za prijavu/registraciju.

### 2.6. Zajedničke komponente (`Common/`)
*   [Header.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Common/Header.jsx): Glavno stakleno zaglavlje aplikacije sa navigacijom, statusom ulogovanog korisnika i zaštićenim administratorskim tasterom (koji prikazuje i bedž sa brojem waitlist prijava na čekanju).
*   [HardwareMonitor.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Common/HardwareMonitor.jsx): Kompaktna traka koja prikazuje status veze sa Redisom (sa opcijom brzog čišćenja keša za administratore), iskorišćenost resursa VPS servera i opterećenje Modal GPU radnika.
*   [Knob.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Common/Knob.jsx): Rotirajući grafički kontroler (knob) koji služi za fino podešavanje parametara zvuka (npr. pitch, volume, speed) povlačenjem mišem (drag action).

---

## 3. Globalno Upravljanje Stanjem (`StudioContext.jsx`)

Svo globalno stanje aplikacije kontroliše se kroz React Context u [StudioContext.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/context/StudioContext.jsx).

### Ključne funkcionalnosti context-a:
1.  **Praćenje Hardvera**: Pokreće periodični tajmer (svakih 5 sekundi) koji poziva `/api/v1/hw-stats` i `/api/v1/modal-status` kako bi osvežio metriku u `HardwareMonitor` komponenti.
2.  **Admin Stanje**: Sinhronizuje ulogu korisnika i u pozadini osvežava statistiku baze i waitlist-a (`adminStats`).
3.  **Undo / Redo Mehanizam (Istorija Akcija)**:
    U cilju pružanja vrhunskog korisničkog iskustva u DAW okruženju, implementiran je mehanizam za poništavanje i ponavljanje izmena nad segmentima:
    *   **Struktura**: Context čuva `history` (niz prethodnih stanja segmenata) i `historyIndex` (trenutni indeks u steku).
    *   **Snimanje akcije (`saveToHistory(newSegments)`)**: Pre nego što se primeni izmena, trenutno stanje segmenata se dodaje na vrh steka, a sva stanja ispred trenutnog indeksa se brišu (ako je korisnik uradio Undo pa napravio novu izmenu). Maksimalna dubina steka je ograničena na 50 stanja radi očuvanja memorije.
    *   **Undo (`triggerUndo()`)**: Vraća stanje na `historyIndex - 1`.
    *   **Redo (`triggerRedo()`)**: Pomera stanje na `historyIndex + 1`.

---

## 4. Mobilna Responzivnost i Optimizacija Interfejsa

Aplikacija je u potpunosti prilagođena za rad na mobilnim uređajima i malim ekranima pomoću naprednih CSS pravila:

*   **Uklanjanje fiksne visine ekrana**: Na desktopu se koristi `100vh` za monolitni DAW raspored bez spoljnog skrolovanja. Na mobilnim telefonima, CSS klase `.studio-mode-active` i `.studio-mode-inactive` uklanjaju ova ograničenja, omogućavajući prirodno vertikalno skrolovanje stranice.
*   **Responzivni raspored kontrola (`.daw-controls-grid`)**: Knobs i slajderi u editoru segmenata se na telefonima preslažu iz horizontalne linije u kompaktni 2x2 grid.
*   **Selektivno sakrivanje elemenata (`.hide-mobile`)**: Pomoću medijskih upita (`@media (max-width: 600px)`), detaljni tekstualni podaci o statusu servera i Modal radnicima u zaglavlju se sakrivaju, a korisniku se prikazuju samo minimalističke ikonice u boji (zelena/crvena).
*   **Waitlist i Login**: Forme se na telefonima automatski prelamaju u kolone, a margine i padding se smanjuju kako bi se maksimalno iskoristio prostor.

---

## 5. Testiranje Frontenda

Frontend koristi **Vitest** za unit i integraciono testiranje React komponenti.

*   **Test datoteke**: Svi testovi se nalaze u poddirektorijumima `__tests__` (npr. [StudioTimeline.test.jsx](file:///home/gruya/Projektri/sinhronizuj.me/frontend/src/components/Studio/__tests__/StudioTimeline.test.jsx)).
*   **Pokretanje testova**: Uvedena je brza skripta u `package.json` za pokretanje testova na CI/CD platformi bez "watch" režima:
    ```bash
    cd frontend
    npm run test:run
    ```
*   **Playwright integracija**: Konfigurisana je struktura za automatsko E2E testiranje korisničkih scenarija u pretraživačima (Chrome, Firefox, WebKit) na CI workflow-u.
