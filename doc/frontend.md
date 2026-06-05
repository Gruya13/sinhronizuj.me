# 🎨 Detaljna Dokumentacija Frontenda (Klijentski Sloj)

Klijentski sloj platforme **Sinhronizuj.me** je izgrađen kao brza i interaktivna Single Page Aplikacija (SPA) zasnovana na **React** frameworku i **Vite** alatu za build-ovanje.

Cilj dizajna je bio stvaranje "wow" efekta kod korisnika kroz premium estetiku inspirisanu profesionalnim audio programima (Digital Audio Workstations - DAW), koristeći tamne tonove, neon efekte (aurora globos), staklene površine (glassmorphic kartice) i fluidne animacije.

---

## 📂 Struktura Izvornog Koda (`frontend/src`)

Projektni fajlovi su organizovani na sledeći način:
- **`App.jsx`**: Glavni ulazni fajl koji upravlja globalnim ruterom, autentifikacijom, dashboard-om i prelazima između stanja.
- **`index.css`**: Centralni CSS sistem koji sadrži sve globalne stilove, varijable boja (sleek dark mode palette), pozadinske efekte i animacije.
- **`context/StudioContext.jsx`**: Centralni React Context za upravljanje stanjem u Studio editoru.
- **`services/api.js`**: Axios klijent sa predefinisanim metodama za pozivanje FastAPI endpointova.
- **`components/`**:
  - **`Auth/LoginRegister.jsx`**: Premium login/register forma sa staklenim efektom i validacijama.
  - **`Dashboard/ProjectList.jsx`**: Lista korisničkih projekata sa statusnim karticama i opcijama za pokretanje analize i brisanje.
  - **`Common/`**:
    - **`Header.jsx`**: Globalni navbar na vrhu ekrana koji sadrži logotip platforme, profil ulogovanog korisnika i "Očisti Redis" dugme.
    - **`Knob.jsx`**: Kružni rotacioni dugmići za kontrolu audio parametara.
    - **`HardwareMonitor.jsx`**: Dashboard widget koji prikazuje status serverskog hardvera i live troškove tokom procesiranja.
  - **`Studio/`**:
    - **`Timeline.jsx`**: Vremenski editor sa talasnim oblicima zvuka.
    - **`SegmentRow.jsx`**: Pojedinačni redovi za prevođenje i editovanje segmenata.

---

## ⚡ Globalni Context (`StudioContext.jsx`)

Glavni provajder stanja za Studio (`StudioContext`) obuhvata:
1. **Upravljanje Stanje Projekta**: Učitava projekat sa API-ja i drži ga u stanju `project`.
2. **Kontrola Audio/Video Reprodukcije**:
   - Upravlja elementima `<video>` (originalni video), `<audio>` (sinhronizovani vokal) i pozadinskim `<audio>` (instrumental).
   - Održava sinhronizaciju između njih prateći `currentTime` i propagirajući ga kroz ceo sistem.
3. **Undo/Redo Stack**:
   - Drži istorijski niz stanja segmenata (do 50 koraka) u `historyStack` i `redoStack`.
   - Svaka promena parametara (teksta, tempa, jačine) pre samog editovanja beleži se pozivom `saveToHistory(segments)`.
4. **Automatsko Polling Stanja**:
   - Ako se video analizira ili renderuje, kontekst periodično poziva endpoint `/api/v1/status/{task_id}` da osveži progres u realnom vremenu.

---

## 🎙️ DAW Studio Komponente

### 1. Vremenski Editor (`Timeline.jsx`)
Ova komponenta pruža vizuelnu vremensku liniju koja podseća na profesionalne miksete.

*   **Wavesurfer.js Integracija**:
    *   Inicijalizuje dva nezavisna `WaveSurfer` objekta: jedan za pozadinsku muziku/instrumental (`no_vocals_url`) i drugi za sinhronizovani srpski glas (`dubbed_audio_url`).
    *   **Stateless S3 učitavanje**: Talasni oblici se učitavaju direktno preko presigned S3 URL-ova (`project.no_vocals_url` i `project.dubbed_audio_url`) umesto starih lokalnih serverskih putanja, sprečavajući 404 greške u produkcijskom stateless okruženju.
    *   **Zabrana modifikacije presigned URL-ova (403 Forbidden Fix)**: Na presigned S3/MinIO URL-ove se **nikada** ne smeju ručno nadovezivati dodatni query parametri poput cache-bustera (`cb=...`). Budući da S3 proverava integritet i računa kriptografski potpis nad celokupnim query stringom, svaka modifikacija na klijentu narušava potpis i MinIO server odbija zahtev sa statusom `403 Forbidden`. URL-ovi moraju biti učitani u izvornom obliku.
    *   **Hvatanje mrežnih izuzetaka (AbortError)**: Pozivi `.load()` funkcije za talasne oblike su zaštićeni sa `.catch()` blokovima koji presreću i ignorišu `AbortError` greške nastale usled uništavanja wavesurfer instanci prilikom promene projekata ili brzih navigacija, čime je očišćena konzola od neuhvaćenih mrežnih obećanja.
    *   Talasni oblici se iscrtavaju direktno unutar svojih traka i sinhronizuju se sa playhead-om (kursorom) u realnom vremenu.
*   **Drag-and-Drop i Promena Vremenskih Ivica**:
    *   Na ivicama segmenata nalaze se nevidljivi ali lako klikabilni kontroleri za promenu početnog (`start`) i krajnjeg (`end`) vremena segmenta.
    *   Pomeranje celog segmenta se vrši prevlačenjem centralnog dela segmenta.
    *   Tokom pomeranja, React ažurira lokalno stanje segmenta u milisekundama, a nakon otpuštanja miša (`mouseup`) automatski šalje izmene na FastAPI backend radi perzistencije u PostgreSQL bazu.
*   **Detekcija Kolizija i Vizuelna Upozorenja**:
    *   Sistem proračunava procenjeno trajanje srpskog govora na osnovu parametra brzine: `estimatedDuration = baseTtsDuration * (1.0 / speed)`.
    *   Ako je procenjeno trajanje duže od vremenskog okvira koji je rezervisan za taj segment na engleskom jeziku, sistem to označava crvenom prugom na ivici segmenta.
    *   Ako se procenjeno trajanje proteže preko početnog vremena sledećeg hronološkog segmenta, detektuje se **Kolizija** i segment dobija žarke crvene ivice sa pulsirajućom senkom (`box-shadow: 0 0 12px #f43f5e`).
    *   **Always on Top Tooltip (Fiksiranje preklapanja)**: Na hover, prikazuje se detaljan premium prozorčić (Tooltip) sa objašnjenjem za koliko tačno sekundi govor probija limit i savetima kako to rešiti. Da bi se sprečilo da drugi elementi iz pozadine (poput crvene linije playhead-a ili natpisa drugih traka) prelaze preko teksta tooltipa, roditeljski segment dinamički dobija `zIndex: isHovered ? 9999 : 2`. Ovo podiže čitav segment na sam vrh stacking konteksta vremenske linije samo tokom prelaženja mišem, čineći tooltip uvek vidljivim i čitljivim.
    *   **Sprečavanje odsecanja na ivicama (Edge-Safe Positioning)**: Kako se tooltip ne bi odsecao sa leve strane na početku videa (0.0s) ili sa desne strane na samom kraju, implementirano je dinamičko poravnavanje. Ako je segment u prvih 15% dužine vremenske linije, tooltip se poravnava uz levu ivicu segmenta (`left: 0px`, `transform: translateY(-10px)`) a njegova strelica se pomera ulevo (`left: 15px`). Ako je segment u poslednjih 15% dužine (left > 85%), tooltip se poravnava uz desnu ivicu (`right: 0px`, `left: auto`) a strelica se pomera udesno (`right: 15px`). U ostalim zonama, tooltip ostaje standardno centriran.
*   **Aktivna Traka i Vizuelno Prigušivanje (Highlight/Dimmed)**:
    *   Segmenti i talasni oblici na vremenskoj liniji se dinamički vizuelno prilagođavaju u zavisnosti od selektovanog izvora zvuka (`activeAudioSource` -> "original" ili "dubbed").
    *   Kada je izabran npr. "Originalni ENG Vokal", segmenti na toj traci su u potpunosti svetli, a njihove selekcije su highlight-ovane (okviri i jače pozadine), dok su segmenti na srpskoj traci (TTS) prigušeni (dimmed) na 20-30% opaciteta i gube zeleni sjaj.
    *   Dugmad za promenu aktivnog audio izvora su premeštena na sam vrh vremenske linije, pored glavnog naslova. Na samim audio trakama se nalaze samo statičke, neklikabilne oznake traka koje vizuelno svetle u aktivnoj boji.
*   **Playhead Scrubbing (Klik i prevlačenje vremenske linije - Optimizovano)**:
    *   Korisnik može kliknuti bilo gde na prazan prostor vremenske linije, skalu sekundi ili direktno na crveni kursor playhead-a, te prevlačenjem (drag) levo-desno vršiti scrubbing (brzo premotavanje) videa i sinhronizovanog audia u realnom vremenu.
    *   **Butter-Smooth 60fps Rendering**: Uveden je lokalni state `localCurrentTime` i `isScrubbingRef` ref kako bi se kursor i wavesurfer oblici pomerali bez ikakvog laga prateći piksel-po-piksel kretanje miša sinhrono.
    *   **Throttling preko requestAnimationFrame**: Kako bi se izbeglo zagušenje pretraživača zbog previše čestog seek-ovanja video/audio elemenata (što zahteva dekodiranje frejmova u pozadini), stvarni seek na video/audio elementima se throttluje i izvršava tek kada je ekran spreman za sledeći iscrtavajući frejm.
    *   **Prevencija nepotrebnog re-renderovanja React-a**: Pomoću `selectedSegmentIdRef` provere, React stanje selekcije segmenta se menja samo u momentu prelaska playhead-a iz jednog segmenta u drugi, a ne pri svakom pomeraju miša, drastično smanjujući procesorsko opterećenje.
*   **Prikazivanje Samo Generisanih Segmenata na Srpskoj Traci**:
    *   Na traci srpskog glasa (TTS) renderuju se isključivo segmenti koji imaju generisan audio (proverava se `seg.tts_path` ili probni audio u `probniAudios`) i koji istovremeno nemaju status `"edited"` ili `"draft"`. Kada korisnik promeni tekst u editoru, segment dobija status `"edited"`, što znači da stari generisani glas više ne odgovara novom tekstu i segment se privremeno uklanja sa trake dok se ne generiše novi.
    *   Time se pruža verodostojan vizuelni prikaz tačne količine i lokacije sinhronizovanog glasa u videu.
*   **Slobodan Izbor Audio Izvora**:
    *   Dugme "Srpski glas (TTS)" na vremenskoj liniji je otključano i nema blokadu alert-om u slučaju da ceo audio još nije spojen u `dubbedAudioUrl`. Korisnik može uvek slobodno prebacivati audio izvor između `"original"` i `"dubbed"` da bi preslušao probne audio zapise na vremenskoj liniji.
*   **Zumiranje Vremenske Linije (Ctrl + Scroll - Bez Praznog Hoda)**:
    *   Korisnici mogu držati taster `Ctrl` i skrolovati točkić miša iznad vremenske linije da bi horizontalno povećali (zoom-in) ili smanjili (zoom-out) širinu timeline-a.
    *   Vrednost zumiranja se kreće između 800px i 6000px i postavlja se kao `minWidth` vremenske linije.
    *   **Trenutni odziv bez praznog hoda**: Pri prvom pokretanju zumiranja na širokim ekranima, stvarna širina kontejnera (`container.clientWidth`) se uzima kao bazična širina ukoliko je `zoomWidth` manji od nje. Ovo sprečava da zumiranje počne sa praznim hodom dok interna promenljiva ne stigne stvarnu širinu ekrana.
    *   **Real-time iscrtavanje talasa (wavesurfer)**: Uklonjena je CSS tranzicija na `min-width` na kontejneru (`timelineRef`) kako bi se izbeglo kašnjenje od 100ms pri promeni veličine. Dodat je `useEffect` hook koji na promenu stanja `zoomWidth` eksplicitno poziva `wavesurfer.redraw()` metodu na svim instancama, čime se talasni oblik iscrtava tečno i trenutno prateći kretanje točkića miša.
    *   Registracija se vrši preko direktnog listenera na `wheel` događaj u `useEffect`-u sa opcijom `{ passive: false }` kako bi se uspešno blokiralo zumiranje celog pretraživača.
*   **Horizontalno Skrolovanje (Točkić Miša)**:
    *   Kada korisnik skroluje točkić miša iznad vremenske linije (bez pritisnutog tastera `Ctrl`), točkić se presreće i vertikalni scroll se prevodi u horizontalno skrolovanje (`container.scrollLeft += e.deltaY`) uz blokiranje podrazumevanog ponašanja pretraživača (`e.preventDefault()`). Ovo omogućava prirodno i intuitivno kretanje kroz vremensku liniju.
*   **Shift + Drag za Pomeranje Vremenske Linije (Drag-Scroll)**:
    *   Držanje tastera `Shift` i prevlačenje miša (drag) preko bilo kog dela vremenske linije (uključujući i segmente) aktivira horizontalno kretanje (pan).
    *   Implementiran je `handleStartDragScroll` koji menja kursor miša u `grabbing` i pomera timeline prateći pomeraj miša. Ova provera je integrisana na samom početku svih resize i drag handlera segmenata, čime se obezbeđuje da se skrolovanje aktivira umesto pomeranja segmenata kada se drži `Shift`.

### 2. Segmenti i AI Lektura (`SegmentRow.jsx`)
Svaki segment govora ima svoj kontrolni panel (Segment Editor) koji je organizovan u tri funkcionalna taba kako bi se rasteretio prostor i poboljšao korisnički doživljaj (UX):
*   **📝 Tekst & Prevod**: Prikazuje originalni engleski tekst i editabilno polje za srpski prevod sa ugrađenim AI Lektorom (Magic Shorten) i brojačem karaktera.
*   **🎙️ Glas & TTS**: Sadrži opcije za generisanje glasa za pojedinačni segment (izbor između "Kloniranja originalnog glasa" i "Muškog glasa Piper Marko"), audio plejer za preslušavanje generisanog probnog TTS-a, i dugme "Generiši / Regeneriši Probni Glas".
*   **🔊 Podešavanja Zvuka**: Sadrži kružne DAW kontrole (Volume, Tempo, Pitch, Ducking) i opciju za globalnu primenu zvučnih parametara na sve segmente.

### 3. Kontrolne Jedinice (`Knob.jsx`)
Umesto generičkih slider-a, za parametre su dizajnirani kružni tasteri (**Knobs**):
*   **Volume**: Podešavanje jačine zvuka tog segmenta od -20dB do +10dB.
*   **Tempo (Speed)**: Brzina govora od 0.7x do 1.4x.
*   **Pitch**: Visina glasa od -5.0 do +5.0 semitona.
*   **Ducking (BG Volume)**: Stepen utišavanja pozadinske muzike (od -30dB do 0dB) u trenucima dok ovaj segment reprodukuje srpski glas.
*   *Implementacija*: Koristi mouse move drag logiku koja prati Y koordinatu miša tokom držanja i rotira CSS element pomoću `transform: rotate(...)` u realnom vremenu, pretvarajući to u brojčanu vrednost.

---

## 📐 Reorganizacija Prostora i Rasporeda (No-Scroll Layout & Ultra-Kompaktni Dizajn)

Kompletna reorganizacija prostora Studio editora stvara kompaktan, DAW interfejs koji staje na jedan ekran (viewport height), eliminišući potrebu za skrolovanjem cele stranice i maksimizujući prostor za video plejer i segment editor.

### 1. Fiksni Layout Visine Ekrana (Full-Screen DAW Režim) i Sužavanje Headera
*   **Sužavanje globalnog Navbar-a**: U `Header.jsx` je padding smanjen sa `16px 24px` na `8px 20px`, čime je oslobođen značajan vertikalni prostor na samom vrhu aplikacije.
*   **Puni Ekran (Full-Screen Studio)**: Glavni kontejner `.glass-container.studio-layout` u `App.jsx` u Studio režimu se širi na 100% širine i visine ekrana (`width: '100vw'`, `height: '100vh'`), bez spoljnih margina, sa oštrim ivicama (`borderRadius: '0'`, `border: 'none'`), čime se maksimizuje radni prostor za video plejer, editor i vremensku liniju.
*   **Stabilizacija Layout-a (Prevencija skakanja i širenja kolona)**:
    *   Dodat je `minWidth: 0` stil na levu kolonu (`.video-preview-card`) i desnu kolonu (`.segment-editor-card`).
    *   Ovo sprečava browser da automatski širi ili skuplja kolone grid layout-a kada se unutrašnji tekstovi prevoda ili opcije dinamički menjaju pri prelasku sa segmenta na segment, garantujući apsolutno fiksiran i stabilan interfejs.
*   **Body Lock**: Preko CSS `:has()` selektora u `index.css`, ukoliko je detektovan `.studio-layout` sa fiksnom visinom, primenjuje se `overflow: hidden` na `body` kako bi se sprečio browser scroll bounce.

### 2. Eliminacija MixerPanel-a i Integracija Globalnih Akcija u Tab Glas & TTS
*   **Uklanjanje MixerPanel-a**: Komponenta `MixerPanel` na dnu ekrana je u potpunosti uklonjena, oslobađajući preko 200px vertikalnog prostora.
*   **Čišćenje zaglavlja aplikacije**: Iz zaglavlja u `App.jsx` su uklonjene globalne opcije glasa i čuvanja kako bi heder ostao maksimalno jednostavan i pregledan. U hederu se sada nalaze samo dropdown za projekte, značka "Studio", dugme "Renderuj Video" (povezano sa `handleRenderProject`) i dugme "Nazad".
*   **Premeštanje Dropdown Menija Projekata**: Meni za prebacivanje i kreiranje projekata (prethodno u `Header.jsx`) premešten je direktno u heder Studio editora (`App.jsx`) na levoj strani pored naziva projekta. Naziv projekta u studiju je sada klikabilno dugme koje otvara listu projekata, omogućava brzo prebacivanje na drugi projekat ili kreiranje novog. Globalni navbar (`Header.jsx`) je očišćen od ovog menija.
*   **Integracija Globalnih Opcija u Segment Editor**: Sve preostale globalne akcije (sa izuzetkom renderovanja videa) su smeštene u tab `🎙️ Glas & TTS` unutar `SegmentRow.jsx`:
    *   **Izbor TTS glasa projekta**: Globalni dropdown meni za prebacivanje podrazumevanog glasa projekta (Klonirani glas OpenVoice V2 ili Muški glas Marko).
    *   **Sačuvaj Nacrt**: Dugme za ručno čuvanje izmena (povezano sa `handleSaveDraft`) sa ugrađenim loaderom.
    *   **Generiši Ceo Glas**: Dugme za pokretanje generisanja glasa na nivou celog videa (povezano sa `handleGenerateAllTTS` u `StudioContext.jsx`) sa ugrađenim loaderom.
    *   **Robusno Ažuriranje i Mapiranje**: Funkcija `handleGenerateAllTTS` je popravljena tako da novi TTS podaci (odnosno putanje `tts_path`) ne prepisuju kompletne objekte segmenata u stanju `project.segments`. Podaci se mapiraju na postojeće objekte segmenata, čuvajući njihovo vreme početka, kraja, status i tekst, čime je sprečeno rušenje layout-a i zamrzavanje vremenske linije. Takođe, spajanje audia je preusmereno na `data.audio_url` (pošto backend vraća `audio_url`, a ne `dubbed_audio_url`).

### 3. Integracija Miksera u Video Plejer
*   **Horizontalni slajderi**: U okviru kontrola video plejera (`.video-player-controls` u `App.jsx`), umesto statičkog saveta, dodata su dva kompaktna horizontalna slajdera za jačinu zvuka:
    *   **Muzika (bgVolume)**: Slajder raspona od -30dB do 10dB sa dinamičkim numeričkim prikazom u realnom vremenu.
    *   **AI Glas (dubVolume)**: Slajder raspona od -15dB do 15dB sa dinamičkim numeričkim prikazom.
*   **Fleksibilan Video Frame**: Uklonjen je fiksni `aspectRatio: '16/9'` sa `.video-frame` diva. Postavljen je fleksibilan režim rada (`flex: '1 1 0%'`, `minHeight: 0`). Plejer se sada skuplja i širi prateći preostalu visinu workspace-a, a video element u njemu se skalira kroz `objectFit: 'contain'`, obezbeđujući maksimalnu veličinu prikaza bez probijanja layout-a.

### 4. Skrolabilni Segment Editor i Timeline
*   **Interni scrollbar**: Kartica `.segment-editor-card` u `SegmentRow.jsx` je zaključana na `height: '100%'` i `overflow: 'hidden'`. Srednji sadržaj tabova je smešten u div sa `flex: '1 1 0%'` i `overflow-y: 'auto'`, čime se skrolovanje aktivira samo za unos prevoda i tonske kontrole, dok naslovi i donje akcije ostaju fiksirani.
*   **DAW Scrollbar stil**: Uveden je tanak ljubičasti neon scrollbar (`width: 6px`) u `index.css` za Segment Editor, i horizontalni ljubičasti scrollbar (`height: 6px`) za vremensku liniju (`.timeline-card`), čime je osigurana potpuna vizuelna ujednačenost.
*   **Timeline (`Timeline.jsx`)**: Smanjeni su padding i margine naslova (na `12px 16px` i `marginBottom: 8px`). Postavljen je `flexShrink: 0` da bi vremenska linija zadržala tačne proporcije i stabilnost.

### 5. "Očisti Redis" Dugme u Zaglavlju
*   U gornjem navbar-u (`hybrid-monitor`) dodat je taster sa ikonicom `Trash2` ("Očisti Redis").
*   Dugme traži eksplicitnu potvrdu od korisnika, a nakon potvrđivanja poziva `POST /api/v1/redis/flush` API endpoint, oslobađa resurse, i poziva lokalnu metodu `resetStudio()` da bi u potpunosti resetovao interfejs za novi, čist proces obrade.
