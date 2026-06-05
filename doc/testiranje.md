# 🧪 Smernice i Plan Testiranja Sistema

Testiranje platforme **Sinhronizuj.me** obuhvata proveru stabilnosti asinhronog pipeline-a, performansi interaktivnog Studio editora, i integracije između VPS-a (Control Plane) i Modal.com GPU radnika (Compute Plane).

---

## 🛠️ 1. Manuelno Testiranje (Studio DAW & UI)

Manuelno testiranje je ključno za osiguravanje visoke responzivnosti i preciznosti vremenske linije u Studiju.

### Korak po korak scenario za testiranje Studija:
1.  **Učitavanje Vremenske Linije**:
    *   Otvoriti projekat koji je uspešno prošao Fazu 1 (status `ready` / `STUDIO`).
    *   Proveriti da li se učitava originalni video, pozadinska muzika, i da li se segmenti tačno iscrtavaju na vremenskoj osi.
2.  **Drag-and-Drop i Resizing**:
    *   Prevlačiti segmente levo-desno. Proveriti da li se start/end vremena u bazi i Redisu ažuriraju odmah po otpuštanju miša (`mouseup`).
    *   Rastezati ivice segmenata. Proveriti da li je minimalna dužina segmenta ograničena (npr. na 0.2s) i da li se ne može prevući van granica trajanja videa.
3.  **Detekcija Kolizija i Upozorenja**:
    *   Ubaciti predugačak srpski prevod u segment i proveriti da li ivice segmenta postaju crvene i pulsiraju.
    *   Prevući segment tako da se preklapa sa sledećim segmentom. Proveriti da li se detektuje kolizija i da li se na hover prikazuje premium Tooltip sa detaljima o koliziji i savetima.
4.  **Audio Parametri (Knobs)**:
    *   Rotirati Volume, Speed, Pitch i Ducking knob-ove za odabrani segment.
    *   Proveriti da li se vrednosti menjaju fluidno i da li se promenom parametara status segmenta menja u `edited`.
5.  **Zumiranje i Skrolovanje Vremenske Linije**:
    *   Držati `Ctrl` i skrolovati točkić miša iznad timeline-a. Proveriti da li se širina timeline-a fluidno povećava/smanjuje i da li se wavesurfer oblici trenutno iscrtavaju bez laga i bez praznog hoda na početku.
    *   Skrolovati točkić miša bez `Ctrl` i uveriti se da se skala kreće horizontalno.
    *   Držati `Shift` i vući miš preko timeline-a (pan) i uveriti se da se timeline pomera u pravcu kretanja miša.
6.  **Grupne Operacije i Selektovanje**:
    *   Držeći `Ctrl` selektovati 3 segmenta na vremenskoj liniji.
    *   U bočnom panelu promeniti glas (npr. sa `clone` na `male`) i jačinu zvuka. Proveriti da li su promene primenjene na sva 3 segmenta.
7.  **Undo/Redo Istorija**:
    *   Izvršiti 5 promena na segmentima.
    *   Pritisnuti `Ctrl + Z` nekoliko puta i proveriti da li se stanja vraćaju unazad.
    *   Pritisnuti `Ctrl + Y` i proveriti da li se stanja vraćaju unapred.
8.  **Brisanje Redisa preko UI**:
    *   Kliknuti na dugme sa ikonicom kante ("Očisti Redis") u gornjem zaglavlju.
    *   Potvrditi akciju u dijalogu i uveriti se da se studio resetuje, a Redis baza isprazni.

---

## 🌐 2. Testiranje API Rute i Integracija

Testiranje se može vršiti pomoću alata poput Postman-a, curl-a, ili automatizovanih HTTP klijenata.

### Ključni test-scenariji:
1.  **JWT Autentifikacija**:
    *   Pokušati pristup endpoint-u `/api/v1/projects` bez Authorization zaglavlja (očekuje se status `401 Unauthorized`).
    *   Prijaviti se preko `/api/v1/auth/login`, uzeti token i poslati ga kao `Bearer <token>` u Authorization zaglavlju (očekuje se status `200 OK`).
2.  **Presigned URL i MinIO S3**:
    *   Pozvati `/api/v1/storage/upload_url?filename=test.mp4`.
    *   Uzeti dobijeni `upload_url` i poslati `PUT` zahtev sa testnim video fajlom.
    *   Proveriti da li je fajl uspešno skladišten na MinIO S3 i da li je dostupan preko presigned download URL-a.
3.  **Preview i Hot-Patching Splicing**:
    *   Izmeniti tekst segmenta i poslati `POST` zahtev na `/api/v1/project/{project_id}/segment/{segment_id}/tts`.
    *   Izmeriti vreme odgovora (očekuje se < 200ms za keširane modele i fast-adjust, odnosno < 1s ako se vrši nova sinteza).
    *   Preuzeti rezultujući audio sa S3 i preslušati da li je segment uspešno ulepljen u ukupnu traku vokala bez klika i artefakata na spojevima.
4.  **Isključivanje OpenVoice i Resemble Enhance**:
    *   U `.env` postaviti `DISABLE_OPENVOICE=True` ili `DISABLE_ENHANCE=True`.
    *   Pokrenuti sintezu i uveriti se da se na Modal šalju odgovarajući parametri i da se preskaču koraci kloniranja glasa ili zvučnog poboljšanja.
5.  **Polling statusa i live troškovi**:
    *   Pokrenuti render preko `/api/v1/project/{project_id}/render`.
    *   Periodično slati `GET` na `/api/v1/status/{task_id}` i pratiti promenu statusa iz `PENDING` -> `PROGRESS` (sa ažurnim USD troškovima za aktivne GPU mašine) -> `SUCCESS` sa finalnim obračunom troškova.

---

## 🤖 3. Testiranje Modal Serverless Resursa

*   **Testiranje Hladnog Starta**:
    *   Ostaviti sistem neaktivan 30 minuta kako bi se svi Modal kontejneri ugasili.
    *   Pokrenuti novi zadatak i pratiti da li backend uspešno toleriše hladni start (koji može trajati od 15 do 45 sekundi u zavisnosti od modela) i da li se kontejneri podižu ispravno bez bacanja timeout grešaka.
*   **Testiranje GPU Memorije (OOM)**:
    *   Poslati video zapis dužine 10+ minuta na analizu.
    *   Pratiti iskorišćenost memorije na Modal dashboard-u za Qwen2-VL i Qwen3 model. Proveriti da li parametri `--gpu-memory-utilization` i `--max-model-len` sprečavaju Out-Of-Memory (OOM) krahove.

---

## 📈 4. Preporuke za Automatizovane Testove (Budući Razvoj)

Za dugoročnu stabilnost sistema preporučuje se implementacija sledećih test-framework-a:

### 1. Backend Unit & Integracioni Testovi (`pytest`)
*   Koristiti `pytest` i `pytest-asyncio` za asinhrono testiranje FastAPI ruta.
*   Koristiti `testclient` iz FastAPI-ja i mock-ovati spoljne resurse:
    ```python
    # Primer mock-ovanja Modal API poziva u pytest-u
    def test_analyze_video_route(client, mocker):
        mocker.patch("backend.worker.tasks.analyze_video_task.delay")
        response = client.post("/api/v1/process-video", json={"url": "https://youtube.com/watch?v=123", "project_id": "uuid"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"
    ```

### 2. Frontend Unit Testovi (`vitest` + `React Testing Library`)
*   Napisati testove za `StudioContext` kako bi se potvrdilo da se undo/redo stack ispravno ponaša kod višestrukih izmena.
*   Testirati `Knob.jsx` komponentu simuliranjem drag događaja mišem i proverom da li se emituju tačne vrednosti u callback funkcijama.

### 3. End-to-End (E2E) Testovi (`Playwright`)
*   Napisati Playwright skriptu koja simulira kompletan tok korisnika:
    1. Registracija i prijava na platformu.
    2. Kreiranje novog projekta i upload videa.
    3. Čekanje na završetak analize (polling statusa).
    4. Otvaranje Studija, promena teksta jednog segmenta, pomeranje segmenta na vremenskoj liniji.
    5. Klik na "Render", čekanje uspešnog završetka i validacija da je generisan finalni video link dostupan za preuzimanje.
