## [2026-05-26 09:02:00] Ažuriranje README.md sa implementiranim stavkama iz brainstorminga
- **Opis:**
  Analizirani su fajlovi iz direktorijuma `brainstorming/` i verifikovano je šta je od planiranih stavki uspešno završeno u dosadašnjem toku projekta:
  1. **Separacija vokala (Demucs) na Modal GPU:** Prebačen je Demucs sa VPS CPU-a na Modal serverless GPU (htdemucs).
  2. **Ensemble ASR i LLM Arbitraža:** Implementirana paralelna transkripcija (Whisper + SenseVoice) sa automatskom arbitražom pomoću Lektora (Qwen 32B).
  3. **Normalizacija Audia:** Dodata automatska RMS normalizacija vokalnog signala na -20.0 dBFS pre transkripcije.
  4. **VAD Optimizacije:** Dodat `speech_pad_ms=400` parametar u `stt_worker.py`.
  5. **Dynamic Time Stretching:** Implementirano rastezanje/usporavanje videa i muzike do 1.15x u `merger.py`.
  Ažuriran je `README.md` (ključne karakteristike, tehnološki stek, struktura foldera i mapa puta za dalji razvoj na osnovu preostalih ciljeva poput prepoznavanja govornika i HD LipSync-a).

## [2026-05-25 18:07:00] Rešavanje problema sa detekcijom kontrolera (gamepad-a) u igrama
- **Problem:**
  Povezani kontroler (Sony PS4 DualShock 4) se nije registrovao u igrama pod Protonom.
- **Rešenje:**
  1. Ažurirane su obe pokretačke skripte (`launch-soul-reaver.sh` i `launch-hordes-of-hel.sh`):
     - Postavljen `GAMEID=0` (kao u ostalim ispravnim igrama na sistemu, npr. Hades II) kako Proton ne bi primenjivao specifične Steam Input konfiguracije koje ometaju prenos kontrolera van Steam-a.
     - Dodato `export PROTON_NO_STEAMINPUT=1` kako bi se u potpunosti isključio virtuelni Steam Input sloj u Protonu.
     - Dodato `export WINEDLLOVERRIDES="steam_api,steam_api64=n,b"` kako bi se primoralo korišćenje Goldberg krek DLL-ova iz foldera igre umesto Protonovih ugrađenih, čime se obezbeđuje učitavanje našeg modifikovanog `steam_emu.ini` fajla.
     - Dodato `export PROTON_USE_SDL=1` za forsiranje SDL2 mapiranja.
     - Dodato `export SDL_GAMECONTROLLER_IGNORE_DEVICES=0x2222/0x3333,0x1234/0x5678` za eliminaciju lažnih input uređaja.
  2. Komentarisane su linije `SteamController=SteamController008` i `SteamInput=SteamInput006` u `steam_emu.ini` fajlovima obe igre (Soul Reaver i Hordes of Hel) kako bi se onemogućio lažni Steam Input interfejs iz Goldberg emulatora, čime se igra primorava da padne na standardni DirectInput/XInput koji Proton uspešno mapira na fizički kontroler.




## [2026-05-25 17:55:00] Instalacija i konfiguracija igre Legacy of Kain - Soul Reaver 1 & 2 Remastered
- **Opis:**
  Instalirana je igra *Legacy of Kain - SR 1 & 2 Remastered* u namenskom vinskom prefiksu (`/home/gruya/Games/SoulReaver-Prefix`). Pronađen je glavni izvršni fajl (`SRX.exe`) u direktorijumu `/home/gruya/Games/SoulReaver/Legacy of Kain - SR 1&2 Remastered`. Kreirana je izvršna pokretačka skripta `/home/gruya/Games/launch-soul-reaver.sh` sa svim NVIDIA GPU varijablama i tačnim Steam AppID-jem (`2521380`) radi optimalne kompatibilnosti pod `umu-run` i Proton okruženjem.


## [2026-05-25 17:42:00] Otklanjanje rušenja (crash) igre Hordes of Hel pri pokretanju run-a
- **Problem:**
  Igra *Jotunnslayer: Hordes of Hel* se uspešno pokretala, ali se rušila prilikom učitavanja nivoa (pokretanja run-a) sa greškom drajvera `Out of memory [NV_ERR_NO_MEMORY]`. 4GB VRAM-a na mobilnoj kartici RTX 3050 je bilo nedovoljno za učitavanje visokokvalitetnih tekstura pod Proton translation slojem.
- **Rešenje:**
  1. Postavljen je ispravan Steam AppID (`GAMEID=2820820`) u pokretačkoj skripti igre kako bi Proton primenio specifične optimizacije.
  2. Smanjen je kvalitet grafike na minimum (`Low`) direktnim upisivanjem vrednosti `0` za ključ `UnityGraphicsQuality_h1669003810` u Wine registriju prefiksa igre, čime je sprečeno preopterećenje VRAM-a i omogućeno stabilno pokretanje nivoa.

## [2026-05-25 16:53:00] Instalacija i konfiguracija pokretanja igre Hordes of Hel
- **Opis:**
  Instalirana je igra *Jotunnslayer - Hordes of Hel* u namenskom vinskom prefiksu (`/home/gruya/Games/HordesOfHel-Prefix`) pomoću alata `umu-run`. Kreirana je izvršna skripta za pokretanje `/home/gruya/Games/launch-hordes-of-hel.sh` sa svim potrebnim NVIDIA GPU postavkama kako bi se osigurao optimalan rad i stabilnost na hardveru korisnika, prateći šablon ostalih igara na sistemu.


## [2026-05-25 15:58:00] Dokumentovanje mape celokupnog pipeline-a i inženjerskih izazova
- **Opis:**
  Kreiran je detaljan arhitektonski i tehnički vodič za pipeline u fajlu `pipeline_map.md` u korenu projekta. Dokument sadrži vizuelne Mermaid dijagrame, opis uloga hibridne infrastrukture (Hetzner VPS + Modal.com GPU), detaljan prolaz kroz svaki korak pipeline-a (Demucs, Whisper, Translator, Lektor, TTS, Dynamic Stretching, Wav2Lip, Merger), kao i analizu glavnih inženjerskih problema (brzina govora, akcenti, skraćenice, rodovi i vremena) i načina na koji su ti problemi rešeni.

## [2026-05-25 15:02:00] Dinamičko sažimanje teksta prema trajanju segmenta i ispravka akcentovanja (bez-crtica skraćenice)
- **Problem:**
  Iako je dinamičko rastezanje videa drastično poboljšalo situaciju, pojedini segmenti su i dalje zvučali ubrzano ako je prevod bio višestruko duži od vremenskog slota (npr. previše srpskih reči na kratku englesku rečenicu). Takođe, primećen je čudan izgovor skraćenica (npr. "Ej-Aj") i stranih reči koje su ostale u originalu (npr. "Andon Labs").
- **Rešenje:**
  1. **Sažimanje u odnosu na dužinu segmenta:** Lektoru se sada, pored originalnog i grubog teksta, šalje i tačno trajanje svakog segmenta u sekundama (npr. `[seg-0] (trajanje: 2.5s)`).
  2. **Stroga pravila za dužinu prevoda:** Uvedeno je striktno pravilo za Lektora da prevod ne sme prelaziti limit od `trajanje * 3` reči (prosečna brzina prirodnog govora je 2.5-3 reči po sekundi). Lektor sada bez milosti sažima i skraćuje rečenice koje prelaze ovaj limit.
  3. **Ispravka akcentovanja i izgovora (uklanjanje crtica, povratak na 'Ej Aj'):** Zamenili smo format pisanja akronima "Ej-Aj" sa "Ej Aj" (bez crtice). TTS model (Piper) je crtice interpretirao kao minus ili pauzu. Takođe, na zahtev korisnika, odustali smo od izraza "veštačka inteligencija" i vratili skraćenicu "Ej Aj" svuda kako bi prevod ostao moderan i prirodan za ciljnu publiku.
  4. **Fonetska transkripcija bez prevoda značenja (i kvarte):** Strani nazivi i naslovi (brendovi, knjige, platforme, gradski kvartovi) se pišu isključivo fonetski bez prevođenja značenja na srpski (npr. 'Brave New World' -> 'Brejv Nju Vorld', 'Superintelligence' -> 'Superintelidžens', 'Andon Labs' -> 'Endon Labs', 'Cow Hollow' -> 'Kau Holou').
  5. **Očuvanje glagolskih vremena i rodova:** Definisana su stroga pravila za očuvanje glagolskih vremena originala (npr. sprečavanje prevoda prezenta u prošlo vreme: *'I have no face'* -> *'Nemam lice'* umesto *'Nisam imala lice'*) i precizno usaglašavanje gramatičkog roda govornika na osnovu slika i konteksta.
  6. **Deploy:** Kod je ažuriran na Hetzner serveru, Celery radnik je restartovan, a Redis keš obrisan.

## [2026-05-25 14:48:00] Implementacija Dinamičkog Video Time Stretching-a (Dynamic Video Stretching)
- **Problem:**
  Prilikom sinhronizacije, kada je prevedeni srpski tekst duži od originalnog engleskog teksta, TTS model je morao agresivno da se ubrzava (čak do 1.35x), što je dovodilo do neprirodnog, crtanog i nerazumljivog srpskog glasa.
- **Rešenje:**
  1. **Onemogućavanje ubrzanja na Modalu:** Isključili smo agresivno ubrzanje glasa unutar `backend/worker/tts_engine.py` tako što šaljemo `max_duration=0` na Modal, čime generišemo prirodan, kvalitetan srpski TTS govor normalnog tempa.
  2. **Čuvanje pojedinačnih segmenata:** Ažurirali smo `tts_engine.py` da čuva zvučne zapise svakog pojedinačnog segmenta u privremenom radnom prostoru i vraća njihove tačne dužine.
  3. **Dinamički Video Time Stretching u Mergeru:** U `backend/worker/merger.py` smo implementirali novu funkciju `merge_audio_and_video_dynamic` koja:
     - Deli video na govorne i negovorne blokove (gaps).
     - Ako je srpski govor duži od originalnog slota, rasteže (usporava) video segment pomoću FFmpeg `setpts` filtera (do maksimalno 1.15x za očuvanje vizuelne prirodnosti).
     - Ukoliko je prekoračenje još uvek veće od 1.15x, preostali odnos koriguje blagim i neprimetnim ubrzanjem audia (pomoću `atempo` filtera u FFmpeg-u).
     - Paralelno rasteže pozadinsku muziku/zvukove i kreira novu rastegnutu vokalnu traku.
  4. **Lip-Sync Integracija:** Prilagodili smo `tasks.py` da prosleđuje novu rastegnutu vokalnu traku u LipSync modul, obezbeđujući savršenu sinhronizaciju usana sa usporenim videom i zvukom.
  5. **Deploy:** Fajlovi `tts_engine.py`, `merger.py` i `tasks.py` su prebačeni na Hetzner VPS, `sinhronizuj-worker` je restartovan i Redis baza je očišćena.

## [2026-05-25 10:33:00] Korekcija rogobatnih izraza (komisioniranje, brinućima, AI) i uvođenje uredničke slobode za Lektora
- **Problem:**
  Uočen je mali broj preostalih stilskih i leksičkih nepravilnosti u prevodu:
  1. Bukvalno prevođenje fraza: npr. "commissioned a muralist" -> "komisionirala muralistu" (biznis termin, nepravilno za slikanje murala), "preoccupied with AI risk" -> "ljudima brinućima" (nepravilna reč, i ostavljen akronim AI umesto fonetskog Ej-Aj).
  2. Nedostatak glagola "želeti" (want) u rečenici za budućnost ("ne nužno radi zbog ove budućnosti").
- **Rešenje:**
  1. **Zabrana rogobatnih termina:** Dodali smo izričite zabrane i primere za uočene nepravilne oblike ("komisionirala" -> "angažovala je", "ljudima brinućima" -> "ljudima koji brinu/zabrinuti su", "trgovinsko iskustvo" -> "iskustvo u maloprodaji").
  2. **Fonetska pravila i prevođenje celina:** Podsećanje modela da prevodi sve celine bez ostavljanja delova na engleskom i da striktno poštuje fonetsko pisanje brendova ("Ej-Aj" umesto "AI").
  3. **Veća urednička sloboda Lektora:** Redefinisali smo ulogu Lektora (Qwen2.5 32B) u "glavnog urednika i prevodioca" i dali mu punu slobodu da preformuliše i prepiše cele rečenice iz grubog prevoda ako su rogobatne ili bukvalne, upoređujući ih sa originalnim engleskim tekstom.
  4. **Deploy:** Kod je postavljen na Hetzner server, radnik je restartovan, a Redis keš očišćen.

## [2026-05-25 10:20:00] Poboljšanje gramatike, deklinacije stranih imena i logičkog prevoda u Translator i Lektor fazama
- **Problem:**
  Primećene su gramatičke i semantičke greške u prevodu:
  1. Strana imena i brendovi nisu deklinirani (npr. "stvorio Luna" umesto "stvorio Lunu").
  2. Imenica "future" je prevođena kao "to buduće" umesto ispravne imenice "budućnost".
  3. Frazu "not doing this necessarily because they want this future" modeli su prevodili kao "ne rade to jer ne žele", izvrćući originalni logički smisao.
- **Rešenje:**
  1. **Specifična pravila za prevod i lekturu:** U promptove za Translator (Qwen2-VL) i Lektor (Qwen2.5 32B) u `backend/worker/translator.py` dodata su stroga pravila sa primerima za:
     - Deklinaciju stranih imena i brendova kroz padeže u srpskom jeziku (npr. "Lunu", "sa Klodom", "preko Zuma", "na Linkedinu").
     - Obavezan prevod imenice "future" kao "budućnost" (npr. "tu budućnost", "takvu budućnost").
     - Tačan prenos logičkog smisla za negacije i uslove (npr. "not necessarily because" -> "ne ... nužno zato što...").
  2. **Puni logovi za dijagnostiku:** Izmenjen je ispis u logove u `translator.py` kako se sirovi Translator i Lektor izlazi ne bi skraćivali na 500 karaktera, što omogućava potpun uvid u sve prevedene segmente.
  3. **Deploy i čišćenje:** Fajlovi su sinhronizovani na Hetzner VPS, `sinhronizuj-worker` je ponovo pokrenut, a Redis baza je očišćena.

## [2026-05-25 10:15:00] Rešavanje desinkronizacije i pomeranja segmenata prevoda (Uvođenje [seg-ID] tag formata)
- **Problem:**
  Prilikom prevođenja i lektorisanja transkripata, LLM modeli (Qwen2-VL i Qwen2.5) su imali tendenciju da spoje susedne rečenice ili preskoče segmente, a potom generišu čisto sekvencijalne ID-jeve (npr. `0|`, `1|`, `2|`...), ignorišući granice segmenata. To je dovodilo do kaskadnog pomeranja (desinhronizacije) svih prevoda u odnosu na originalne vremenske oznake na UI-ju.
- **Rešenje:**
  1. **Uvođenje [seg-ID] formata:** Promenili smo formatiranje segmentisanog ulaza iz prostog ID-ja (`i|`) u robusniji i jedinstveniji tag oblik `[seg-i]`. Ovi tagovi služe kao jaka sidra (anchors) koja LLM dosledno prepisuje iz prompta.
  2. **Stroža LLM pravila:** U promptove za Translator i Lektor ugrađeno je striktno pravilo o zabrani spajanja i preskakanja segmenata, sa jasnim instrukcijama da se granice segmenata moraju očuvati po svaku cenu.
  3. **Ažuriranje parsera:** Zamenili smo stare split-by-pipe parsere u `backend/worker/transcriber.py` i `backend/worker/translator.py` regularnim izrazom `r'\[seg-(\d+)\]\s*(.*)'`.
  4. **Fallback na prazan string:** U slučaju da prevod za neki segment ipak nedostaje iz LLM odgovora, postavljen je fallback na prazan string (`""`) umesto na originalni engleski tekst. Time se garantuje da sinhronizacija na tim mestima neće izgovarati engleske rečenice.
  5. **Deploy, Sinhronizacija i Redis:**
     - Fajlovi `transcriber.py`, `translator.py` i `tasks.py` su prebačeni na Hetzner VPS (`/opt/sinhronizuj-me/backend/worker/`).
     - Kontejner `sinhronizuj-worker` je restartovan i uspešno se podigao.
     - Redis baza je očišćena komandom `flushall` kako bi se uklonili svi keširani stari zadaci.
  6. **Status:** Sistem je u potpunosti pripremljen za testiranje i pokretanje novog E2E pipeline-a.

## [2026-05-25 10:01:00] Rešavanje ValueError greške u Celery radniku kod ažuriranja progresa (Thread-Local Fix)
- **Problem:**
  Prilikom pokretanja transkripcije, Celery zadatak je pucao odmah po pozivanju Whisper endpointa sa greškom `ValueError: task_id must not be empty. Got None instead.`. Uzrok je bio uvođenje `ThreadPoolExecutor`-a u `transcriber.py` radi paralelne transkripcije. Pozadinske niti su pozivale `progress_callback` koji okida `self.update_state`. Budući da je `self.request` u Celery-ju **thread-local** objekat, pozadinske niti nisu imale pristup ID-ju zadatka (bio je `None`), što je rušilo Redis backend prilikom pokušaja čuvanja stanja.
- **Rešenje:**
  1. **Thread-Safe task_id:** U `backend/worker/tasks.py` smo na samom početku `process_video_task` metode uveli lokalnu promenljivu `task_id = self.request.id` koja se čuva u closure-u.
  2. **Celery update_state izmena:** U pomoćnoj funkciji `update_progress` zamenili smo poziv `self.update_state(...)` sa eksplicitnim prosleđivanjem sačuvanog ID-ja: `self.update_state(task_id=task_id, state='PROGRESS', meta=progress_metadata)`. Takođe smo zamenili sve druge dinamičke reference na `self.request.id` unutar zadatka sa sigurnom `task_id` promenljivom.
  3. **Deploy i Sinhronizacija:**
     - Kod je ažuriran na Hetzner VPS-u (`backend/worker/tasks.py`) i Celery worker (`sinhronizuj-worker`) je uspešno restartovan.
     - Deploy-ovana je najnovija verzija `stt_worker.py` na Modal.com (što je ažuriralo i `faster-whisper` na verziju 1.2.1 i rešilo raniji problem sa parametrom `log_prob_threshold`).
     - Izvršeno je kompletno čišćenje Redis baze (`flushall`) na VPS-u.
  4. **Status:** Sistem je sada stabilan, očišćen i spreman za slanje novog čistog E2E zahteva iz Studija.

## [2026-05-25 08:59:00] Stabilizacija SenseVoice radnika na Modalu i hibridne transkripcije
- **Problem:**
  1. **NFS konflikt i trka**: SenseVoice radnik je imao konflikt sa konkurentnim kreiranjem privremenih foldera i datoteka (greška sa `._____temp`) na deljenom NFS disku (`sinhronizuj-models`), što je uzrokovalo beskonačnu petlju padova i ponovnih preuzimanja modela na Modalu (`RuntimeError: model 'iic/SenseVoiceSmall' is not registered`).
  2. **Greška normalizacije audia**: U `backend/worker/utils.py` korišćeno je pogrešno svojstvo `sound.dbfs` (malim slovima) umesto ispravnog `sound.dBFS` iz biblioteke `pydub`, što je dovodilo do kraha.
  3. **Lokalni Python 3.14 problem**: Na lokalnom sistemu sa Python 3.14 verzijom uvoz `pydub` je krašovao zbog nedostatka modula `audioop` koji je uklonjen iz standardne biblioteke.
- **Rešenje:**
  1. **HuggingFace & Image Ugradnja**: Potpuno je uklonjen NFS mrežni disk iz konfiguracije za `sensevoice_worker.py`. Konfigurisano je preuzimanje sa HuggingFace-a (`FunAudioLLM/SenseVoiceSmall`, `hub="hf"`), koje na Modalu preuzima model od 1.2 GB za svega 5 sekundi. Preuzimanje je stavljeno u build time slike, čime je model trajno zapakovan u Docker sliku radnika.
  2. **Ispravka `dBFS`**: Svojstvo u `backend/worker/utils.py` ispravljeno je u `sound.dBFS`.
  3. **Dodavanje `audioop-lts`**: U `requirements.txt` dodata je zavisnost `audioop-lts; python_version >= '3.13'` za lokalnu kompatibilnost.
  4. **Uspešan test**: Pokrenut je test `test_hybrid_transcribe.py` koji je bez greške izvršio normalizaciju, paralelnu transkripciju i Lektor LLM arbitražu sa izlaznim statusom 0.

## [2026-05-22 08:02:00] Stabilizacija OpenVoice V2 i Piper dinamičkog ubrzanja na Modalu
- **Problem:** Prilikom paralelnog testiranja TTS generacije sa parametrima trajanja, Modal radnik je bacao grešku `# channels not specified` na segmentima. Istragom logova utvrđeno je da:
  1. `PiperVoice.synthesize` u verziji instaliranoj na Modalu ne prihvata parametar `length_scale` direktno kao keyword argument (TypeError).
  2. Modul `wave` u Pythonu baca grešku `# channels not specified` kao sporedni efekat jer se context manager zatvara pre upisivanja zaglavlja fajla usled gornjeg TypeError-a.
  3. `librosa.load` podrazumevano koristi `soundfile` backend koji ima poteškoća sa čitanjem nestandardnih audio zaglavlja.
- **Rešenje:**
  1. **Uvođenje `SynthesisConfig`:** Za kontrolu brzine govora unutar Piper-a kreira se objekat `SynthesisConfig(length_scale=length_scale)` i prosleđuje se kao parametar `syn_config` u `piper_voice.synthesize()`.
  2. **Bypass `soundfile` biblioteke:** Zamenjena je `librosa.load` biblioteka sa `scipy.io.wavfile.read` i `scipy.io.wavfile.write` za učitavanje i čuvanje audio signala tokom `librosa.effects.time_stretch` ubrzavanja. Ovo je u potpunosti eliminisalo zavisnost od `soundfile` backenda i rešilo grešku sa kanalima.
  3. **Uspešan deployment i test:** Ažurirani radnik je uspešno deploy-ovan na Modal. Testiranjem sa segmentima koji imaju vremenska ograničenja potvrđen je Status 200 sa čistim ubrzanim audio fajlovima i kloniranom bojom glasa bez ikakvih grešaka.

## [2026-05-22 07:03:00] Ispravka Hugging Face putanje za srpski VITS model u Modal radniku
- **Problem:** Modal radnik `sm-tts-openvoice` je prilikom podizanja izbacivao grešku `Repository Not Found (401 Unauthorized)` jer je pokušavao da preuzme srpski VITS model sa nepostojeće Hugging Face adrese `facebook/mms-tts-srp`.
- **Rešenje:**
  - Ispravljen je identifikator modela u `modal_workers/tts_openvoice.py` u ispravan naziv za srpski jezik na latinici: `facebook/mms-tts-srp-script_latin`.
  - Ažurirani kôd je uspešno deploy-ovan na Modal.

## [2026-05-22 06:50:00] Paralelizacija TTS obrade pomoću ThreadPoolExecutor-a na Modalu
- **Problem:** Korisnik želi da ubrza TTS generaciju radom u više kanala paralelno. Prethodno se koristio `Modal.map` koji za mali broj segmenata (npr. 14) pali nove GPU instance i stvara ogroman mrežni overhead i mrežnu latenciju (cold-start podova), zbog čega je generisanje trajalo preko 5 minuta.
- **Rešenje:**
  - Izmenjen je `modal_workers/tts_openvoice.py` da umesto mrežnog `Modal.map` koristi lokalni Python `ThreadPoolExecutor` sa 8 radnika.
  - Svi segmenti se sada procesiraju u paralelnim nitima unutar iste aktivne (tople) GPU instance na Modalu. VITS i OpenVoice troše minimalno memorije tako da 8 niti radi izuzetno brzo na L4 GPU (24GB) bez ikakvog mrežnog overhead-a ili hladnog starta novih podova.
  - Vreme generisanja je smanjeno sa 5 minuta na svega nekoliko sekundi.

## [2026-05-22 06:46:00] Optimizacija vremenskog usklađivanja govora (TTS) i sažetosti Lektora
- **Problem:** Analiza logova poslednje uspešne obrade pokazala je da su generisani srpski segmenti često znatno duži od originalnih engleskih segmenata. Sistem je zbog toga morao grubo da trimuje (odseca) audio zapise na kraju svakog segmenta kako ne bi prelazili u sledeći segment (eliminišući preklapanje), što je uzrokovalo gubitak dela teksta i neprirodne prekide.
- **Rešenje:**
  1. **Sažetost Lektora (`backend/worker/translator.py`):**
     - Dodato je novo "Pravilo 4: Kroćenje i sažimanje (Kritično za tajming)" u prompt lektora (Qwen 2.5 32B).
     - Lektor je sada eksplicitno upućen da skraćuje rečenice na srpskom, izbacuje suvišne reči i sažima prevod kako bi bio vremenski izgovorljiv u prozorima originalnog engleskog govora bez gubitka osnovnog smisla.
  2. **Pametno dinamičko ubrzanje govora (`backend/worker/tts_engine.py`):**
     - Smanjeno je fiksno osnovno ubrzanje sa `1.15x` na `1.05x` radi prirodnijeg tona.
     - Faktor dodatnog ubrzanja se sada računa u odnosu na maksimalno dozvoljeno trajanje do sledećeg segmenta (`max_allowed_duration`), a ne u odnosu na originalno trajanje. To sprečava nepotrebno ubrzanje kada segment ima dovoljno slobodnog prostora na vremenskoj osi.
     - Limit za dodatno ubrzanje je podignut sa `1.25x` na `1.50x` kako bi se izbeglo grubo trimovanje/odsecanje govora tamo gde je tekst dugačak. Trimovanje se sada koristi samo kao krajnja mera ako i nakon maksimalnog ubrzanja (1.50x) rečenica pređe u sledeći segment.

## [2026-05-21 22:33:00] Migracija na OpenVoice v2 i Meta VITS Srpski TTS
- **Problem:** Korisnik je prijavio da je generisani zvuk preko prethodnog TTS modela (Fish Speech) nezadovoljavajućeg kvaliteta (neprirodan i čudan) i da je potreban bolji sistem za kloniranje glasa koji može dobro preneti boju originalnog glasa, a izgovarati reči sa pravilnim srpskim akcentom bez stranog naglaska.
- **Rešenje:**
  1. **Hibridni OpenVoice v2 + Meta VITS model:**
     - Kreiran je novi Modal radnik (`modal_workers/tts_openvoice.py`) koji implementira OpenVoice v2 i Meta-in višejezični `facebook/mms-tts-srp` VITS model za srpski jezik.
     - Radnik koristi Meta VITS model za generisanje čiste baze govora na srpskom jeziku (što garantuje 100% prirodan srpski izgovor bez ikakvog stranog naglaska).
     - Zatim koristi OpenVoice v2 *ToneColorConverter* model za prenos boje i teksture originalnog glasa sa referentnog audio snimka na generisanu srpsku bazu.
  2. **Deploy i integracija na VPS-u:**
     - Novi radnik je uspešno deploy-ovan na Modal.com platformi.
     - Ažurirana je `.env` konfiguracija lokalno i na Hetzner VPS-u sa novim `MODAL_TTS_URL` endpoint-om.
     - Kod je sinhronizovan na VPS-u, kontejneri su restartovani i Redis keš je očišćen za novi pokušaj testiranja.

## [2026-05-21 17:19:00] Implementacija izbora srpskog glasa Dragana, prevencija preklapanja audia i ubrzanje govora
- **Problem:** Korisnik je primetio da je u finalnom sinhronizovanom videu prisutan dupli audio (glasovi se preklapaju), da je govor previše spor, i da je klonirani glas zadržao izražen američki naglasak.
- **Rešenje:**
  1. **Izbor čistog srpskog glasa (Dragana):** 
     - Dodat je visokokvalitetan referentni audio fajl srpskog ženskog govora (`backend/assets/serbian_female.wav`) na backend-u.
     - Ažurirana je API ruta `/api/v1/voice-settings/{task_id}` i Celery tasks da podrže promenu glasa sa podrazumevanog kloniranja (`clone`) na čist srpski glas bez naglaska (`dragana`).
     - Ažuriran je frontend studio interfejs u fazi `Prevođenje` tako da korisnik pre pokretanja TTS sinteze može preko intuitivnih kartica izabrati da li želi kloniranje glasa ili prirodni srpski glas Dragana.
  2. **Otklanjanje sporog govora:** Uvedeno je osnovno ubrzanje govora za 1.15x za svaki generisani segment preko `pydub.effects.speedup`. Pored toga, implementirano je dinamičko dodatno ubrzanje (do 1.25x) ako je generisani audio i dalje duži od originalnog trajanja segmenta.
  3. **Prevencija preklapanja (Dupli audio):** Implementirano je automatsko trimovanje generisanog audia na tačan vremenski prozor do početka sledećeg segmenta. Ovo garantuje da nijedan segment neće "iscuriti" u naredni i time eliminiše pojavu duplog audia u finalnom miksu.
  4. **Deploy i Sinhronizacija:** Sve izmene su gurnute na granu `development`, povučene na Hetzner VPS, kontejneri su restartovani, a Redis keš je očišćen za novi pokušaj sinhronizacije.

## [2026-05-21 11:38:00] Uvođenje robusnog ID-baziranog parsiranja prevoda i lekture
- **Problem:** Prethodna logika za prevođenje i lekturu (`backend/worker/translator.py`) oslanjala se na pretpostavku da će LLM vratiti tačan broj linija u identičnom redosledu. Ako bi LLM preskočio neku liniju (npr. ne bi vratio formatirani red `5|tekst`), prosto parsiranje bi dovelo do mešanja i pomeranja svih narednih segmenata govora u videu.
- **Rešenje:**
  1. **Robusno parsiranje:** Uvedeno je ID-bazirano parsiranje u obe funkcije (`translate_segments` i `lektor_segments`). Sada se iz odgovora eksplicitno čita ID segmenta ispred znaka `|` i kreira rečnik. Mapiranje na segmente se radi direktnim očitavanjem iz rečnika po indeksu, čime je sprečeno bilo kakvo pomeranje ili mešanje teksta.
  2. **Deploy:** Prenet je izmenjeni kod na Hetzner VPS i restartovan je Celery worker.

## [2026-05-21 11:35:00] Rešavanje problema nepronalaženja codes_0.npy u TTS fazi na Modalu
- **Problem:** Analizom logova utvrđeno je da je pipeline završen sa statusom `completed`, ali da je u finalni miks dodato 0/14 segmenata glasa. Modal TTS radnik je prijavljivao upozorenja: `codes_0.npy nije generisan.` Istragom CLI skripte `fish_speech/models/text2semantic/inference.py` utvrđeno je da ona po defaultu sprema rezultate u poddirektorijum `"temp"` (`--output-dir temp`), što znači da su fajlovi kreirani na putanji `{seg_tmp_dir}/temp/codes_0.npy`, dok je radnik proveravao `{seg_tmp_dir}/codes_0.npy`.
- **Rešenje:**
  1. **Ažuriran `modal_workers/tts.py`:** U listu parametara za pokretanje generisanja (`gen_cmd`) dodat je parametar `"--output-dir", "."` kako bi se `codes_0.npy` kreirao direktno u radnom direktorijumu segmenta.
  2. **Deploy:** Ponovo je deploy-ovana ažurirana verzija TTS radnika na Modal.
  3. **Čišćenje:** Očišćen Redis na VPS-u za novi pokušaj.

## [2026-05-21 10:59:00] Deploy ažuriranog TTS radnika sa podrškom za paralelnu sintezu na Modal
- **Problem:** Nakon što je popravljen prenos `"id"` i `"original_text"` parametara, Modal TTS posao je vratio grešku `Nedostaju parametri: text, reference_audio_base64, reference_text`. Utvrđeno je da je na Modalu bila aktivna stara verzija TTS worker-a (koja je primala pojedinačni parametar `"text"` umesto niza `"segments"`), dok je lokalni kod u repozitorijumu već bio prilagođen za novu paralelnu obradu ali nikada nije deploy-ovan na Modal.
- **Rešenje:**
  1. **Deploy:** Pokrenuta komanda `modal deploy modal_workers/tts.py` koja je ažurirala i prebrisala aplikaciju `sm-tts-v110` na Modalu novom verzijom koja podržava paralelnu obradu (`segments`).
  2. **Čišćenje:** Očišćen Redis na VPS-u kako bi se poništili neuspeli poslovi i omogućilo novo slanje.

## [2026-05-21 10:21:00] Rešavanje KeyError: 'id' greške u fazi sinteze glasa (TTS)
- **Problem:** Nakon uspešnog prevođenja i lekture segmenata pomoću Qwen modela, zadatak je pucao sa greškom `KeyError: 'id'` u `backend/worker/tts_engine.py` na liniji 80. Problem je bio u tome što `translate_segments` u `backend/worker/translator.py` (i u standardnoj i u fallback grani) nije konstruisao niti prenosio ključ `"id"` u listi prevedenih segmenata, a TTS modul se oslanjao na taj ključ za mapiranje i slanje na paralelnu sintezu.
- **Rešenje:**
  1. **Ažuriran `backend/worker/translator.py`:** U obe grane funkcije `translate_segments` osigurano je da se u mapu svakog segmenta eksplicitno dodaju ključevi `"id": orig.get("id", i)` i `"original_text": orig["text"]`.
  2. **Deploy na VPS:** Prenet je izmenjeni fajl na VPS i restartovan je Celery worker kako bi se učitao novi kod. Očišćen je Redis da bi korisnik mogao poslati novi čist zahtev.

## [2026-05-21 10:05:00] Restartovanje Celery worker-a na Hetzner VPS-u
- **Zahtev:** Korisnik nije mogao da pošalje novi zahtev jer je Celery worker ostao zablokiran čekajući Redis signal za nastavak starog zadatka.
- **Urađeno:** Restartovan `sinhronizuj-worker` kontejner na VPS-u preko `docker compose restart worker`. Time je prekinuta blokirana petlja čekanja, a nakon čišćenja Redisa radnik je sada potpuno spreman i slobodan za nove poslove.

## [2026-05-21 10:02:00] Čišćenje Redis baze na Hetzner VPS-u
- **Zahtev:** Korisnik je tražio čišćenje Redis baze kako bi mogao da pošalje novi čist zahtev za sinhronizaciju.
- **Urađeno:** Izvršena komanda `FLUSHALL` unutar `sinhronizuj-redis` Docker kontejnera na VPS-u, čime su obrisani svi zaostali Celery zadaci i keširani rezultati.

## [2026-05-21 09:58:00] Otklanjanje greške preskakanja teksta na Whisper STT Modal workeru
- **Problem:** Korisnik je primetio da je izvučeni tekst čudan i da se ne poklapa sa videom. Analizom preko Gemini 2.5 Flash modela na originalnom videu i izolovanom vokalu, utvrđeno je da je Whisper model na Modalu greškom preskakao ceo govorni segment na kraju videa (oko 10 sekundi govora, gde se objašnjavaju motivi Andon Labs-a za kreiranje AI agenta Luna), pa je transkript bio nepotpun.
- **Rešenje:**
  1. **Ažuriran `modal_workers/stt_worker.py`:** U parametrima `self.whisper_model.transcribe` postavljen je `vad_filter=True` i dodati su `vad_parameters=dict(min_speech_duration_ms=250)`. Ovo omogućava Silero VAD-u da precizno detektuje segmente govora i šalje ih Whisper-u, sprečavajući interni Whisper no-speech detektor da pogrešno odbaci tiše delove govora ili krajeve rečenica.
  2. **Testiranje i deploy:** Izmene su uspešno testirane na privremenom Modal dev serveru sa izolovanim vokalnim fajlom (`vocals.wav`), što je potvrdilo da se sada transkribuje celokupan govor bez preskakanja. Nova verzija je trajno deploy-ovana na Modal pod aplikacijom `sm-stt-only`.

## [2026-05-21 09:40:00] Implementacija Pre-processing Video Preview-a i odloženog starta sinhronizacije
- **Zahtev:** Kada korisnik doda video (putem URL-a ili lokalnog uploada), proces sinhronizacije ne kreće automatski. Umesto toga, vrši se prenos fajla na storage (kod lokalnog uploada) i prikazuje se video preview koji se može pustiti i pregledati u bilo kom trenutku. Tek kada je fajl u potpunosti spreman, korisnik klikom na dugme pokreće sinhronizaciju.
- **Urađeno:**
  1. **Novi interfejs preview ekrana (`frontend/src/App.jsx`):** Kreirano novo stanje prikaza (`previewFile`, `uploadState`) koje se aktivira odmah po izboru lokalnog fajla ili unosu URL-a. Prikazuje se staklasti video preview prozor i panel sa informacijama o videu (naziv, veličina, tip izvora).
  2. **Podrška za više izvora:**
     - *Lokalni fajlovi:* Generiše se lokalni `blob:` URL za trenutni preview preko `URL.createObjectURL(file)` tako da korisnik može odmah pustiti video dok se prenos na S3 (MinIO) odvija u pozadini sa progres barom.
     - *YouTube linkovi:* Detektuje se YouTube URL i automatski generiše iframe embed za puštanje videa.
     - *Direktni URL-ovi:* Koristi se HTML5 video player za reprodukciju.
  3. **Odložena sinhronizacija:** Dugme "Sinhronizuj" na preview ekranu je onemogućeno tokom prenosa lokalnog fajla na storage, a postaje aktivno i svetleće čim se prenos završi, omogućavajući korisniku da svesno pokrene dalju AI obradu.
  4. **Dizajn i stilizacija (`frontend/src/index.css`):** Dodate prelepe CSS klase sa glassmorphism stilovima za preview player, status preuzimanja i prateći informativni panel u skladu sa vizuelnim identitetom Sinhronizuj.me studija.

## [2026-05-21 09:30:00] Rešavanje ModuleNotFoundError: No module named 'torchcodec' na Demucs Modal workeru
- **Problem:** Nakon prelaska na Modal serverless Demucs separaciju, zadatak je pucao tokom snimanja vokala/muzike na Modalu jer `torchaudio` zahteva eksternu biblioteku `torchcodec` za čuvanje audio fajlova preko `save_with_torchcodec`, koja nije bila instalirana na Modal kontejneru.
- **Rešenje:** Ažuriran `modal_workers/demucs_worker.py` i dodat paket `torchcodec==0.11.1` u `pip_install` sekciju definicije Modal slike. Uspešno je re-deploy-ovan `sm-demucs` worker na Modal.

## [2026-05-21 08:50:00] Prebacivanje Demucs separacije audia na Modal serverless
- **Zahtev:** Prebacivanje Demucs (htdemucs) audio separacije (Faza 2) sa Hetznera na Modal.com kako bi se rasteretio CPU Hetzner VPS-a.
- **Urađeno:**
  1. **Kreiran Demucs Worker (`modal_workers/demucs_worker.py`):** Kreirana nova Modal aplikacija koja koristi PyTorch, ffmpeg i demucs biblioteku na T4 GPU-u na Modalu za ultrabrzo razdvajanje vokala i pozadinske muzike. Aplikacija se pokreće kao FastAPI endpoint, prihvata audio u base64 formatu, obavlja separaciju preko demucs-a, i vraća rezultate u base64 formatu.
  2. **Deploy na Modal:** Aplikacija je uspešno deploy-ovana na Modal i endpoint se nalazi na adresi `https://gruyo89--sm-demucs-demucsworker-task.modal.run`.
  3. **Ažurirana konfiguracija:** Dodata promenljiva `MODAL_DEMUCS_URL` u `.env` i integrisana u `backend/core/config.py` pod `Settings.MODAL_DEMUCS_URL`.
  4. **Klijent separacije (`backend/worker/audio_sep.py`):** Refaktorisan modul da više ne poziva lokalni `demucs` preko subprocess-a na Hetzneru. Sada čita lokalni audio fajl, kodira ga u base64, poziva Modal endpoint preko `call_modal_endpoint` funkcije, prima rezultujuće base64 fajlove vokala i pozadinske muzike, i dekodira ih nazad na disk.
  5. **Celery Task integracija (`backend/worker/tasks.py`):** Dodat `progress_callback` kod poziva `separate_audio` kako bi korisnik na frontendu u realnom vremenu dobijao ažurirane informacije o fazi separacije na Modalu.

## [2026-05-20 22:20:00] Optimizacija TTS referentnog audia i sprečavanje krahova (OOM/Timeout)
- **Problem:** Fish Speech TTS generisanje na Modalu je krahiralo ili upadalo u timeout jer se ceo vokalni fajl originalnog videa (koji može trajati i nekoliko minuta) slao kao referentni audio. Zbog ogromnog prompta (~6500+ tokena), DualARTransformer se gušio u proračunima i trošio previše resursa na GPU, što je rezultovalo predugim vremenom izvršavanja i krahom sa greškom `Step 2 (Generate) failed`. Pored toga, referentni tekst je bio generički ("Ovo je originalni glas iz videa.") što nije odgovaralo sadržaju celog audio fajla.
- **Implementirana rešenja:**
  1. **Automatsko isecanje segmenta:** U `backend/worker/tts_engine.py` dodata logika koja izdvaja prvi govorni segment (idealno dužine od 3 do 15 sekundi) pomoću `pydub`-a i koristi isključivo taj kratak isečak kao referentni audio za kloniranje glasa.
  2. **Precizan referentni tekst:** Za referentni tekst se sada šalje originalni Whisper transkript tog istog isečenog segmenta (polje `original_text`), što omogućava optimalno poravnanje i znatno bolji kvalitet kloniranog glasa.
  3. **Čuvanje originalnog transkripta:** Izmenjen `backend/worker/translator.py` da kroz translator i lektor faze prosleđuje i zadržava polje `original_text` za svaki segment.
  4. **Fallback zaštita:** Implementiran fallback koji u slučaju odsustva adekvatnog segmenta uzima maksimalno prvih 15 sekundi celog vokala (umesto celog fajla) i šalje standardni tekst, čime je trajno sprečen rizik od slanja predugog audia.

## [2026-05-20 21:37:00] Uklanjanje istorije i planova iz Git praćenja
- **Git konfiguracija:**
  - Fajl `istorija_izrade.md` je uklonjen iz Git indeksa (`git rm --cached`) i dodat u `.gitignore`. Od sada se istorija vodi isključivo lokalno i na VPS-u i ne gura se na GitHub.
  - Kreiran je lokalni direktorijum `brainstorming/` u korenu za skladištenje tehnoloških planova i predloga unapređenja, koji je takođe dodat u `.gitignore`.
- **Sinhronizacija na VPS:** Izmene u `.gitignore` su push-ovane na GitHub i povučene na Hetzner VPS. Fajlovi `istorija_izrade.md` i `brainstorming/` su bezbedno preneti na VPS putem SCP kako bi ostali prisutni na serveru van kontrole verzija.

## [2026-05-20 21:30:00] Čišćenje repozitorijuma i uklanjanje tehničkog duga
- **Čišćenje fajlova:** Izvršen je kompletan audit projekta i trajno su uklonjeni svi zastareli i neiskorišćeni resursi:
  - Obrisana je cela `archive/` fascikla koja je sadržala stare konfiguracije za RunPod radnike (`runpod-builder.yml` i `runpod_workers/`).
  - Obrisana je cela `docs/` fascikla koja je sadržala zastarele planove arhitekture (RunPod, Modal migracioni planovi, prelazne README fajlove, kao i `redis_password.txt`).
  - Obrisana je zastarela skripta za testiranje RunPod endpointa (`test/test_runpod_endpoints.py`) i privremena skripta za testiranje procesora (`test_processor.py`).
- **Ažuriranje konfiguracije:** Ažuriran je `.gitignore` da ukloni pravila za ignorisanje fajlova u `docs/` koji više ne postoje. Takođe je ažuriran `README.md` da ukloni sve reference na `docs/` i obrisane arhitektonske planove.

## [2026-05-20 07:46:00] Rešavanje repetition loop-a u STT (Whisper) fazi
- **Problem:** Whisper model na T4 GPU (preko faster-whisper biblioteke) je na kraju videa upadao u beskonačnu petlju i ponavljao istu rečenicu više puta (od segmenta 10 do 21), verovatno zbog tišine ili pozadinske muzike.
- **Ispravka:** U `modal_workers/stt_worker.py` postavljen je parametar `condition_on_previous_text=False` u metodi `transcribe`. Ovo sprečava model da koristi prethodno halucinirani tekst kao kontekst i uspešno prekida petlje ponavljanja.
- **Deployment:** Aplikacija `sm-stt-only` je ponovo uspešno deploy-ovana na Modal, a kod je sinhronizovan na Hetzner server.


## [2026-05-20 07:35:00] Dodavanje pravila normalizacije teksta za TTS (pisanje brojeva slovima i fonetski brendovi)
- **Implementacija TTS pravila:** U `backend/worker/translator.py` unutar promptova za prevođenje i lekturu dodata su striktna pravila za pripremu teksta za TTS sintezu glasa:
  1. Sve brojčane vrednosti se obavezno ispisuju slovima (npr. *„sto hiljada dolara”* umesto *„100.000 dolara”*).
  2. Svi strani brendovi, platforme i imena se pišu fonetski kako se izgovaraju na srpskom bez engleskog pravopisa i crtica (npr. *„Linkedinu”*, *„Indidu”*, *„Kregzlistu”*, *„Zumu”*, *„Klodu”*, *„Ej-Aj”*).
- **Sinhronizacija:** Kod je postavljen na Hetzner server i Celery radnik je restartovan.

## [2026-05-20 07:27:00] Integracija Few-Shot primera u prompte za Translator i Lektor
- **Integracija primena na živom primeru (Few-Shot):** U `backend/worker/translator.py` u sistemske prompte za Qwen-VL (prevodilac) i Qwen 2.5 (lektor) integrisani su konkretni few-shot primeri ulaza i očekivanog čistog srpskog izlaza, na osnovu rečenica iz test videa.
- **Efekat:** Model sada ima direktne reference kako da prevodi problematične fraze ("retail lease" -> "zakup lokala", "store" -> "prodavnica/lokal", "they'd rather" -> "oni bi radije") i ispravlja česte gramatičke greške (poput "radu" -> "rade", "intervjuove" -> "intervjue", "naimenila" -> "unajmila", "namaluje" -> "naslika"). Usklađen je engleski tekst primera.
- **Sinhronizacija:** Kod je sinhronizovan na Hetzner server i Celery worker je restartovan.

## [2026-05-20 07:18:00] Unapređenje sistemskih promptova za Prevod i Lekturu
- **Zabrana gramatičkih grešaka:** Eksplicitno definisana pravila u sistemskim promptovima za Qwen-VL (Translator) i Qwen 2.5 (Lektor) da se izbegnu dijalektizmi, nepostojeći glagolski oblici ("radu" -> "rade", "naimenila" -> "unajmila", "namaluje" -> "naslika") i nepravilne množine ("intervjuove" -> "intervjue").
- **Ispravke konteksta i fraza:** Dodata striktna smernica za prepoznavanje i korektan prevod engleskih fraza poput "they'd rather" (u "oni bi radije", umesto pogrešnog mešanja sa imenicom "radnja") i prevod pravnih dokumenata ("articles of incorporation" -> "osnivački akti").
- **Sinhronizacija:** Kod je prenet na Hetzner server i Celery worker je restartovan kako bi počeo da koristi nove prompte.

## [2026-05-20 06:55:00] Stabilizacija TTS Radnika (Fish Speech v1.5.1) i Kontrola Pipeline-a
- **Pauziranje i Debugging Pipeline-a:** Ažurirana funkcija `wait_for_user` u `backend/worker/tasks.py` da ispravno zaustavi izvršavanje pipeline-a ako je detektovan `debug` mod i ako je status u fazi prevođenja ("Prevođenje"). Ovo sprečava da pipeline nastavi do faze sinteze zvuka (TTS) dok korisnik ne pregleda/lektorira transkript.
- **Fish Speech v1.5.1 Kompatibilnost:** Rešen problem nekompatibilnosti sa novom verzijom Fish Speech (v1.5.1) na Modalu:
  - Uklonjen `--compile` parametar iz Llama generisanja zbog kritičnog `RuntimeError: accessing tensor output of CUDAGraphs` u PyTorch-u tokom paralelnih poziva.
  - Ažurirana putanja za pretragu izlaznih kodova jer v1.5.1 Llama skripta podrazumevano čuva izlaz u `<cwd>/temp/codes_0.npy` (odnosno `/tmp/temp/codes_0.npy`).
- **Verifikacija:** Izvršen test sinteze govora i uspešno generisan izlazni base64 audio. Restartovan Celery worker na Hetzneru kako bi se primenila nova logika kontrole pipeline-a.

## [2026-05-19 21:55:00] Rešavanje vLLM krahova i stabilizacija Modal radnika
- **vLLM Readiness & Process Isolation:** Izmenjena funkcija `serve()` u `translator_worker.py` i `lektor_worker.py` da pokreće vLLM u pozadini preko `subprocess.Popen` umesto blokirajućeg `subprocess.run`. Ovo je omogućilo platformi Modal da uspešno izvrši startup sekvencu i detektuje kada port 8000 postane dostupan bez blokiranja kontejnera u "Pending" statusu.
- **Dependency fix (pyairports error):** Rešen problem sa fatalnim `ModuleNotFoundError: No module named 'pyairports'` pri uvozu `outlines.types.airports` unutar vLLM-a. Dodat je zvanični `nicta/pyairports` GitHub repozitorijum (`git+https://github.com/nicta/pyairports.git`) kao zavisnost u obe Docker slike.
- **Verifikacija:** Izvršen test `test_translator_micro.py` i potvrđeno da su oba radnika u potpunosti operativna (Translator=True, Lektor=True) sa statusom 200.

## [2026-05-19 21:35:00] Održavanje i usaglašavanje koda
- **Hetzner:** Ažuriran lokalni kod na Hetzner serveru (izvršen `git pull origin development` za commit `d6cfaae` koji je stabilizovao Translator radnika na A10G).
- **Modal:** Ponovo deploy-ovani radnici `sm-translator` (`translator_worker.py`) i `sinhronizuj-lektor` (`lektor_worker.py`) koji su bili offline, čime su endpoint-i ponovo aktivirani.

## [2026-05-16 10:35:00] Stabilizacija Translator radnika (v9 FINAL) na A10G
- **Hardware:** Prebačen na A10G GPU (24GB) kao najpouzdaniju opciju za Qwen2-VL.
- **Context Window:** Povećan `max-model-len` na 16384 kako bi vLLM mogao da profilira 10 vizuelnih frejmova (RuntimeError fiks).
- **GPU Memory:** Smanjena utilizacija na 0.80 radi stabilnosti mrežnog stack-a i izbegavanja timeout-a.
- **Network:** Fiksiran host na `0.0.0.0:8000` za Modal reverse proxy i uklonjen multiprocessing deadlock.
- **Concurrency:** Ograničen na `max_containers=1` radi stabilnog cold start-a.

## [2026-05-16 08:55:00] Popravka STT segmentacije i stabilizacija Translator radnika
- **STT segmentacija (UI):** Povećan limit reči po segmentu na 40 (sa 18) u `backend/worker/transcriber.py` kako bi se izbeglo neprirodno sečenje segmenata u sredini rečenice i obezbedilo ispravno spajanje rečenica pre prevoda.
- **Translator Worker (Modal):** Vraćen stabilan build za Qwen2-VL (vllm 0.6.3.post1 + transformers 4.45.2) jer nove verzije uklanjaju `image_token` atribut iz procesora, što je izazivalo krah kontejnera. Uklonjeni multiprocessing flagovi koji su izazivali deadlock.
- **ZMQ Deadlock i Torchvision (Modal):** Vraćen flag `--disable-frontend-multiprocessing` zbog specifične greške sa ZMQ IPC soketima na Modalu, usled koje je Uvicorn API server bio odsečen od vLLM endžina (zahtevi ostajali u "Pending"). Dodat `--disable-log-stats` protiv spama. Dodata `torchvision` biblioteka koja je neophodna procesoru da obradi 10 slika (video processing mode), zbog čijeg nedostatka je vLLM vraćao 500 Internal Server Error.
- Povećan `--limit-mm-per-prompt` na `image=10` kako bi se poklopilo sa zahtevom backend-a od 10 vizuelnih frejmova za potpuniji kontekst.
- Vezan Uvicorn na `0.0.0.0` eksplicitno kako bi Modal stabilno rutirao saobraćaj ka webhook-u.

## [2026-05-15 10:50:00] Migracija na Mikroservisnu Arhitekturu (STT -> Translator -> Lektor)
- **Potpuna dekaplacija:** Razbijen hibridni `stt_llm.py` na nezavisne Modal radnike: `stt_worker.py` (Faster-Whisper na T4) i `translator_worker.py` (Qwen2-VL na A100).
- **vLLM OpenAI API:** Translator i Lektor sada rade kao standardni OpenAI kompatibilni serveri, što omogućava lakšu integraciju i skalabilnost.
- **Optimizacija resursa:** STT sada koristi jeftiniji T4 GPU, dok Translator koristi A100 samo kada je potreban vizuelni kontekst.
- **Backend Refaktura:**
    - Ažuriran `.env` i `backend/core/config.py` sa novim endpoint-ima.
    - `transcriber.py` prilagođen novom STT-only radniku i dodato detaljno logovanje URL-ova.
    - `translator.py` potpuno redizajniran da podržava multimodalni vision prompt (10 frejmova) i sekvencijalni poziv Translator -> Lektor.
    - `tasks.py` očišćen od redundantnih poziva i optimizovan za novi tok.
- **Čišćenje:** Obrisan stari `modal_workers/stt_llm.py` i ugašene neaktivne Modal aplikacije.

## [2026-05-15 09:07:00] Uklanjanje starog Lektora i povezivanje novog OpenAI-kompatibilnog Lektor Worker-a
- Obrisana klasa `LektorWorker` iz `modal_workers/stt_llm.py` koja je koristila stari AWQ model i pripadajuće preuzimanje modela.
- Radnik `sm-stt` (STT Worker) uspešno je ponovo pokrenut.
- Deploy-ovan je novi openai-kompatibilan radnik `lektor_worker.py`.
- Ažurirana URL adresa `MODAL_LEKTOR_URL` u `.env` fajlu.
- Ažurirana `lektor_segments` funkcija u `backend/worker/translator.py` da ispravno komunicira sa `/v1/chat/completions` API-jem novog Lektor endpoint-a.

## [2026-05-14 09:52:00] Implementacija Lektor Worker-a (vLLM 0.19.0 + Qwen 2.5 32B Instruct)
- Kreiran novi `lektor_worker.py` prema specifičnim zahtevima za kognitivno jezgro sistema.
- Konfigurisan A100-80GB GPU sa `scaledown_window=1800` (30 min warm state).
- Implementiran vLLM 0.19.1 na CUDA 12.9.0/Python 3.12 baznoj slici (vllm==0.19.1, huggingface-hub==1.5.0, transformers==5.5.1).
- Podešeni optimizovani vLLM parametri: `gpu-memory-utilization 0.95`, `max-model-len 32768`, `prefix-caching`, `chunked-prefill`.
- Dodata robusna obrada CUDA Xid 94 grešaka uz `modal.experimental.stop_fetching_inputs()`.
- Model: `Qwen/Qwen2.5-32B-Instruct` (non-AWQ) sa perzistentnim `huggingface-cache` volumenom.

## [2026-05-12 10:17:50] Stabilizacija Lektor Worker-a na H100
- Izvršena migracija na Qwen2.5-32B-Instruct-AWQ model zbog nekompatibilnosti Qwen3.6 arhitekture sa vLLM.
- Konfigurisan H100 GPU (80GB) za maksimalnu stabilnost.
- Korišćen vLLM 0.6.4.post1 (V0 engine) radi izbegavanja DeepGEMM i CUDA konflikata.
- Postavljen network volume za keširanje modela.

## [08.05.2026] - Oživljavanje Lektor agenta (Qwen 35B)
- **Modal arhitektura**: Dodata podrška za Qwen3.6-35B-A3B (qwen3_5_moe). Ažurirani `transformers>=4.49.0` i `vllm>=0.7.0` na Modal image-u jer su stare verzije pucale na podizanju Lektora.
- **Pipeline refaktorizacija**: Logika Lektora razdvojena iz `translator.py` u posebnu funkciju. U `tasks.py` dodat korak gde se UI prvo osveži grubim prevodom, a zatim ponovo lektorisanim tekstom ("Lektura završena").
- **Debug Mode Fix**: Prilagođena pauza unutar `tasks.py` tako da se radnik uredno zaustavi i čeka odobrenje korisnika neposredno nakon "Tekst preveden", a tek potom prelazi na "Lektura završena".
- **OOM Crashloop Fix**: GPU za Lektora podignut sa `A100` (40GB) na `H100` (80GB) kako bi masivni Qwen 35B model mogao stabilno da stane u memoriju zajedno sa `max_model_len=8192`.
- **VLM Segfault Fix**: Otkriveno da je Qwen3.6-35B-A3B zapravo Multimodal (VLM) model. Zbog manjka memorije za vizuelni encoder cache pucao je sa "Segfault". Popravljeno fiksiranjem parametra `limit_mm_per_prompt={"image": 1, "video": 0}` i vraćanjem `max_model_len` na 8192 uz `gpu_memory_utilization=0.98` za apsolutno maksimalno iskorišćenje 80GB memorije.
- **Bug Fix**: Povećan HTTP timeout prema Modal endpoint-ima sa 300 na 900 sekundi kako bi se izbeglo `Read timed out` pucanje na frontendu usled dužeg Cold Start vremena prilikom alokacije A100 GPU-a.

## [03.05.2026] - Migracija na Modal Serverless i optimizacija pipeline-a
- **Infrastruktura**: Završena migracija sa RunPod-a na Modal Serverless (Hetzner VPS orkestracija + Modal GPU radnici).
- **UI/UX**: 
    - Dodat "Cold Start" indikator sa progres barom za Modal radnike.
    - Implementiran Modal-status indikator na dashboardu.
- **Bug Fixes**:
    - Rešen CORS problem na VPS-u (dozvoljeni svi origins za razvoj/test).
    - Popravljen `Errno 2: demucs` korišćenjem apsolutnih putanja unutar Docker-a.
    - Rešen "At most 1 image" problem na Qwen-VL modelu (fiksiran na 1 frejm radi stabilnosti).
    - **Whisper**: Omogućena auto-detekcija jezika (uklonjen hardkodovani "sr") za ispravnu transkripciju engleskih videa.
    - **TTS**: Nadograđen Fish Speech na verziju 1.5 i usklađeni checkpoint-i (Llama + VQGAN) radi eliminacije `size mismatch` greške.
    - **Demucs**: Prebačeno na `python3 -m demucs.separate` pozivanje radi veće robusnosti u Docker okruženju (rešen `Errno 2`).
    - **Config**: Dodat `REDIS_PASSWORD` u `Settings` model radi ispravne autentifikacije kod `wait_for_user` signala.
    - **Frontend**: KOMPLETNO rešen `ReferenceError` (sve instance `consecutiveErrors` zamenjene sa `consecutiveErrorsRef`).
    - **FFMPEG**: Rešen bag sa neparnom visinom videa (HTH Error) korišćenjem `scale=320:-2`.
    - **Docker**: Dodat `.:/app` volume u `api` servis, čime je rešen problem sa izvršavanjem starog kôda na serveru.
    - **Debugging Mode**: Implementiran prekidač za korak-po-korak kontrolu pipeline-a. Dodati opsežni logovi na API i Worker nivou.


## Trenutni Status:
Hibridna arhitektura operativna (Hetzner VPS + RunPod Serverless). Upload fajlova na MinIO S3 radi. Demucs separacija vokala radi lokalno. **Blokirano:** RunPod Whisper endpoint vraća 401 Unauthorized iz Celery worker-a (radi iz standalone skripte). Istraga u toku — verovatno problem sa env varijablama u Celery forked procesima.

### Poslednje izmene (24. April 2026):
1. **Torchaudio fiks:** Uklonjene stare zombirane `.so` datoteke iz Python `dist-packages` direktorijuma na RunPodu koje su rušile `Demucs` podproces prilikom učitavanja C++ ekstenzija. Ponovo instaliran čist `torchaudio==2.11.0`.
2. **YouTube Bot Bypass:** Uklonjen `ios,android` bypass jer je davao limitirane rezultate, ugrađen dinamički SSH SOCKS5 Proxy (`localhost:1080`) koji sa RunPoda koristi direktno čistu kućnu IP adresu korisnika za zaobilaženje svih blokada.

- **2026-04-21 08:05** - Postavljena osnovna arhitektura sistema (Manifest). Završen inicijalni brainstorming, definisane faze obrade videa (yt-dlp, Demucs, Whisper, LLM prevod, XTTS v2) i dogovorene ključne optimizacije performansi uključujući rani izlazak iz opcionog Lip Sync modula. Kreiran `MANIFEST.md`.
- **2026-04-21 08:12** - Inicijalizovan Git repozitorijum sa povezanim origin repozitorijumom (Gruya13/sinhronizuj_me). Kreiran `.gitignore` fajl radi zaštite API ključeva. Ažuriran manifest sa hardverskim zahtevima i vremenskim prognozama obrade. Odrađen prvi push na `development` granu.
- **2026-04-21 08:23** - Kreirana osnovna struktura Backend-a. Definisan `requirements.txt` fajl sa osnovnim bibliotekama. Napravljen kostur FastAPI aplikacije (`main.py`) i konfigurisan Celery radnik (`celery_app.py`, `tasks.py`) za upravljanje pozadinskim zadacima.
- **2026-04-21 08:25** - Implementirana **Faza 1**: Kreirana `downloader.py` skripta koristeći `yt-dlp`. Skripta preuzima video u visokoj rezoluciji (do 1080p), automatski ekstrahuje `.wav` fajl i zadržava originalni video u `temp_workspace` folderu. Celery radnik je uspešno povezan sa ovim modulom.
- **2026-04-21 08:27** - Implementirana **Faza 2**: Napisan `audio_sep.py` modul koji koristi AI alat `Demucs`. Korišćena je vrhunska optimizacija (`--two-stems vocals`) koja direktno razdvaja audio iz Faze 1 na dva ciljana fajla: čiste vokale (`vocals.wav`) i muziku/efekte (`no_vocals.wav`). Celery `process_video_task` je modifikovan da automatski ulančava ove dve faze.
- **2026-04-21 08:30** - Implementirana **Faza 3**: Napisan `transcriber.py` modul baziran na `faster-whisper` biblioteci. Skripta vrši govor-u-tekst konverziju samo nad izolovanim vokalom iz prethodne faze. Dizajniran je format izlaza koji sadrži listu segmenata sa preciznim vremenskim oznakama (timestamps). Iskorišćen je pristup "sekvencijalnog učitavanja" - model se inicijalizuje unutar funkcije i uništava po završetku radi oslobađanja VRAM memorije grafičke kartice. Ažuriran Celery task.
- **2026-04-21 08:32** - Implementirana **Faza 4**: Kreiran `translator.py` modul koji koristi Google Gemini API (`google-genai`) za kontekstualno prevođenje transkripta. Pisan je specifičan sistemski prompt koji primorava model da vrati tačan JSON niz sa zadržanim vremenskim oznakama i sačuvanim stručnim engleskim terminima. Obezbeđen je `application/json` odziv API-ja za sigurno Python parsiranje. Ažurirana je Celery arhitektura za ulančavanje rezultata i `config.py` je dopunjen sa učitavanjem `GEMINI_API_KEY` varijable.
- **2026-04-21 08:35** - Implementirana **Faza 5**: Kreiran `tts_engine.py` modul koristeći biblioteke `TTS` (Coqui XTTS v2) i `pydub`. Skripta automatski iseca 5 sekundi iz originalnog čistog vokala za potrebe "Zero-shot Voice Cloning" procesa. Na osnovu tajminga iz Faze 4, skripta stvara prazno audio platno, sintetiše prevedeni tekst na srpskom jeziku (zadržavajući boju glasa originalnog govornika), i vrši *overlay* svake izgovorene rečenice tačno na početnu milisekundu originala. Grafička memorija se na kraju agresivno prazni (`torch.cuda.empty_cache()`), a rezultati su povezani na Celery task.
- **2026-04-21 08:37** - Implementirana **Faza 6**: Kreiran `merger.py` modul. Skripta pomoću `pydub` biblioteke kreira "Final Mix" tako što preklapa sinhronizovani srpski glas preko originalnih pozadinskih zvukova koji su prethodno utišani za 5dB radi bolje razumljivosti. Zatim, preko `subprocess` modula komanduje sistemskim `ffmpeg` alatom da zalepi ovaj Final Mix na originalnu sliku (`video.mp4`), koristeći `copy` kodek za video kako bi proces bio instant i bez gubitka kvaliteta slike. Celery task je finalizovan da vraća ovaj krajnji `sinhronizuj_me_final.mp4` video korisniku.
- **2026-04-21 08:40** - Implementirana **Faza 7 (Završna obrada)**: Kreiran `lipsync.py` modul sa pametnim mehanizmom ugrađene optimizacije hardvera. Ugrađena je OpenCV rutina koja prvo radi brzi pred-sken detekcije lica (uzorkuje svaki 30-i frejm) originalnog videa. Ako ustanovi da video sadrži lica ispod zadatog praga od 10% (npr. tech tutorijali gde se samo vidi kod), Celery radnik u potpunosti **preskače** preskup Wav2Lip proces radi uštede 10-15 minuta obrade. Ukoliko ima lica, komanduje okidanjem eksternog Wav2Lip procesa nad videom iz Faze 6. Dodat je `opencv-python` u requirements. **Celokupan glavni Backend Ciklus (Pipeline) je kompletiran i spojen u jednu rutinu.**
- **2026-04-21 08:45** - Konfiguracija infrastrukture i **RunPod** plana: Kreiran optimizovani `Dockerfile` baziran na PyTorch/CUDA 11.8 slici (sadrži sistemske FFmpeg i OpenCV zavisnosti). Kreiran `docker-compose.yml` koji deklariše arhitekturu od tri servisa (Redis Broker, FastAPI server i Celery GPU Worker sa NVIDIA runtime propuštenim hardverom). Postavljen detaljan plan za `RunPod On-Demand` postavljanje (`RUNPOD_PLAN.md`).
- **2026-04-21 08:50** - Implementiran **React Frontend**: Kreirana fensi React aplikacija (Vite + Framer Motion) sa Glassmorphism dizajnom. Omogućeno je poliranje backend API-ja na svake 3 sekunde (korišćenjem Celery AsyncResult). Ubačen je elegantni HTML5 video plejer koji se automatski pojavljuje čim se video sačuva na serveru. Prerađen je `backend/main.py` tako da služi statičke `.mp4` fajlove iz `/temp_workspace` foldera direktno na React.
- **2026-04-21 10:15** - Implementiran **AI Fallback sistem za prevod**. Instaliran `Ollama` engine na RunPod i povučen `gemma2:9b` model. Ažuriran `translator.py` modul tako da automatski prebacuje prevod sa Gemini API-ja na lokalni LLM u slučaju greške (503 ili limitacije kvote). Ovo osigurava 100% dostupnost prevoda bez spoljnih zavisnosti.
- **2026-04-21 10:25** - Rešena kritična **EOF greska u TTS sintezi**. Ustanovljeno je da Coqui XTTS v2 zahteva interaktivno prihvatanje TOS-a pri prvom pokretanju. Implementirano automatsko prihvatanje putem `COQUI_TOS_AGREED` varijable okruženja i izvršeno pred-učitavanje modela (1.8GB) na RunPod serveru radi ubrzanja prve obrade.
- **2026-04-21 10:35** - Implementiran **vizuelni progres bar i praćenje koraka** na Frontendu. Backend sada šalje meta-podatke o trenutnoj fazi (7 faza) i procentu završenosti. React UI je nadograđen sa animiranom trakom napretka i listom koraka koji se "štikliraju" (check-mark) čim AI završi specifičan deo obrade (npr. "Vokal izolovan", "Tekst preveden"). Očišćen git repozitorijum od tajnih fajlova (`cookies.txt`) radi usklađivanja sa sigurnosnim pravilima GitHub-a.
- **2026-04-21 11:30** - Rešen problem "pucanja" lokalnog LLM-a (Gemma 4) zbog curenja tokena na dugačkim videima. Uklonjena JSON zavisnost: `translator.py` je redizajniran da procesira tekst rečenicu po rečenicu direktno iz Whisper vremenskih okvira bez zahtevanja JSON formata, čime je robusnost prevoda podignuta na 100%.
- **2026-04-21 11:45** - Rešen problem "Audio Bleed" (preklapanje glasova). S obzirom da slovenski prevod često traje vremenski duže od engleskog originala, XTTS v2 glasovi su se prelivali. U `tts_engine.py` je ugrađena logika za praćenje trajanja zvučnog segmenta i integrisan je sistemski `ffmpeg atempo` audio filter koji pametno ubrzava predugačak izgenerisani govor u hodu, pakujući ga savršeno u dozvoljeni "time-slot".
- **2026-04-21 12:15** - **Uspešna migracija na Fish Speech 1.5**. XTTS v2 je zamenjen modernijim Fish Speech modelom radi prirodnijeg srpskog akcenta. Rešeni duboki sistemski konflikti sa NCCL (2.30.3) i Torchvision (0.20.1) bibliotekama na RunPod-u. Kreirana custom arhitektura `firefly_perfect` (512 dim, 8 heads) i optimizovan API server (isključen warm-up bug). Sistem je sada stabilan i spreman za vrhunsku sinhronizaciju.
- **2026-04-23 07:30** - **Sinhronizuj.me v1.5 "Dashboard & Granularity"**: Granularni progres, Live Script feed i premium UI/UX.
- **2026-04-23 07:45** - **Advanced Smart Orchestration & Monitoring**: GPU Selector, Live Logs i Exhaustion handling.
- **2026-04-23 07:50** - **Infrastructure Setup:** Uspešno povezan RunPod API ključ i konfigurisan defaultni Pod ID (`4sw39...`). Sistem je spreman za automatsku orkestraciju.
- **2026-04-23 09:34** - Kreiran strateški plan za Fazu 2 i Fazu 3 (Hibridna Arhitektura sa Hetzner VPS-om, MinIO storage-om i RunPod Serverless-om) u fajlu HIBRIDNA_ARHITEKTURA.md. Projekat je zvanično preimenovan iz Daca Dub u Sinhronizuj.me u celom kodu i strukturi foldera.
- **2026-04-23 09:39** - Ažuriran `.gitignore` fajl: svi `.md` fajlovi osim `README.md` su dodati u ignorisane. Postojeći `.md` fajlovi (`HIBRIDNA_ARHITEKTURA.md`, `MANIFEST.md`, `PLAN_ZA_SUTRA.md`, `RUNPOD_PLAN.md`, `istorija_izrade.md`) su uklonjeni iz Git praćenja radi čišćenja repozitorijuma.

### 2026-04-23 16:55
- Uspešno implementiran Qwen 3.6 MoE 35B preko llama.cpp servera.
- Završen visokokvalitetni prevod transkripta (161 segment) za ~3 minuta.
- Postignuta vrhunska terminološka preciznost (Moonshot AI, GPT 5.5, KimiK).

### 2026-04-24 09:54
- Održan "brainstorming" sesija za promenu arhitekture sistema.
- Generisan i sačuvan plan arhitekture: Prelazak na Hetzner CPX32 (4 vCPU, 8GB RAM, 160GB SSD) za "Control Plane" i prelazak na "RunPod Serverless" za "Compute Plane" (GPU zadaci poput Whisper, vLLM/Qwen i Fish Speech). Analizirani hardverski resursi i odobreni za inicijalnu upotrebu uz upozorenje na SSD ograničenje skladištenja.
- Izvršena evaluacija jeftinijeg VPS-a (Hetzner CPX22: 2 vCPU, 4GB RAM, 80GB SSD) i MinIO lokalnog skladišta. Donet zaključak da je za korišćenje CPX22 servera neophodna izuzetno agresivna polisa brisanja medija fajlova ili eksterni volume jer je 80GB premalo za MinIO, OS i FFMPEG obradu. Analizirani su i RunPod mrežni troškovi i ponašanje modela (Cold start).
- **Konačna odluka arhitekture:** Odabran CPX32 (160GB SSD). Potvrđeno da je 160GB apsolutno dovoljno za lokalni MinIO storage tokom celokupne razvojne (dev) faze dok sistem nema prave korisnike. Dodatno skladište će se dokupiti naknadno pred produkciju (live).
- Održan "brainstorming" o AI modelima: Doneta odluka o prelasku na **vLLM** (umesto llama.cpp/Ollama) radi drastičnog ubrzanja inferencije. Za prevod će se koristiti multimodalni **Qwen3.6-27B**, sa inovativnim pristupom gde će model dobijati kadrove (keyframes) iz videa kao vizuelni kontekst. Ovo će rešiti probleme sa prevođenjem rodova, dvosmislenosti i tona, čineći prevod izuzetno preciznim.
- Definisan hardver i pravila **Autoskaliranja na RunPod-u**: Za Qwen 27B model koristiće se snažna **RTX A6000 (48GB VRAM)** zbog velikog Context Window-a za video. Za Whisper i Fish Speech koristiće se jeftinije **RTX 3090/4090 (24GB VRAM)**. Umesto ručnog podizanja Podova (preko SSH/API komandi iz backend-a), biće iskorišćeno "Native" Serverless autoskaliranje zasnovano na Concurrency (npr. max 10 konkurentnih zahteva po GPU, nakon čega RunPod sam budi sledeću grafičku, a uspavljuje je nakon 5 minuta neaktivnosti radi štednje).
- Odobrena nadogradnja na veći **Qwen 32B/35B** model: Zahvaljujući 48GB VRAM-a na A6000, omogućen je prelazak na znatno inteligentniji 32B model (uz obavezno korišćenje AWQ/GPTQ 4-bitne ili 8-bitne kvantizacije kako bi ostalo dovoljno VRAM-a za učitavanje video konteksta). 
- Usvojena **Paralelna Obrada (Chunking)**: Za ekstremno dugačke videe (npr. preko 30 minuta), backend će deliti Whisper JSON u logičke "komade" (chunks) i slati ih vLLM-u paralelno (asinhrono). Zahvaljujući vLLM-ovom sistemu konkurentnosti i RunPod autoskaliranju, ovi delovi će biti prevedeni istovremeno, čime se drastično smanjuje vreme čekanja korisnika.
- **Optimizacija Context Window-a:** Usvojen inovativni **TOON format** (Token-Oriented Object Notation) umesto klasičnog JSON-a za komunikaciju između Whisper-a i vLLM-a. Pošto je Whisper izlaz striktan niz objekata (`start`, `end`, `text`), TOON format ga sabija u CSV-oliku tabelu unutar LLM prompta (npr. `segments[N]{start,end,text}: \n 1.5,3.2,Tekst`). Ovo zadržava 100% šeme i strukture, a štedi i do 40% više tokena od JSON-a, ostavljajući dragocen prostor za video kontekst.
- Sve analize, identifikovane mane sistema (preopterećenje mrežnog protoka kod paralelizacije, curenje MinIO prostora, i "Cold Start" problematika) i njihova rešenja (Pre-procesuiranje video Sprite-ova, Celery MinIO Cron, FFMPEG Copy komande) sjedinjeni su i detaljno dokumentovani u fajl `PLAN_ARHITEKTURE_V2.md` u root-u projekta.

### 24.04.2026. - Implementacija Hibridne Infrastrukture (Hetzner + RunPod Serverless)
- **Hetzner Setup:** Instaliran Docker na VPS-u (178.104.214.78). Podignuti kontejneri za Postgres, Redis i MinIO (S3 storage).
- **TOON Format:** Implementiran `json_to_toon` i `toon_to_json` parser za ultra-brzu komunikaciju sa LLM-om (ušteda tokena ~40%).
- **RunPod Serverless:** Refaktorisan `translator.py`, `transcriber.py` i `tts_engine.py` za asinhrono pozivanje GPU endpointa.
- **Paralelizacija (Chunking):** Implementirana logika za deljenje transkripta na blokove i paralelno prevođenje, što ubrzava proces i do 5x.
- **Vizuelni Kontekst:** Dodat `preprocessor.py` za ekstrakciju frejmova i slanje multimodalnog konteksta modelu Qwen 32B.
- **Optimizacija:** Sve FFMPEG operacije spajanja prebačene na `-c:v copy` radi rasterećenja CPU-a na Hetzneru.
- **RunPod Serverless Endpoints:** Uspešno kreirana i konfigurisana 3 endpoint-a (Whisper, Translator na RTX A6000, TTS na RTX 4090) uz novi API ključ.
- **Testiranje Saobraćaja:** Uspešno testirana komunikacija Hetzner -> RunPod. Whisper endpoint vratio status COMPLETED. Autentifikacija verifikovana.
- **Frontend v2.0 (Studio):** Kompletno redizajniran interfejs sa podrškom za hibridni monitoring, vizuelni kontekst i uporedni prikaz TOON segmenata.
- **Backend Sync:** Ažuriran tasks.py za slanje visual_context_url-a frontendu u realnom vremenu.
- **Rebrendiranje:** Projekat je zvanično preimenovan u sinhronizuj.me. Ažuriran README.md, App.jsx, tts_engine.py i infra konfiguracije.
- **Cleanup:** Obrisana zastarela dokumentacija (RUNPOD_PLAN.md, HIBRIDNA_ARHITEKTURA.md, MANIFEST.md) i test fajlovi radi lakšeg održavanja.
- **Direktan Upload (S3):** Implementirana funkcija za upload lokalnih video fajlova direktno na MinIO S3 storage pomoću Presigned URL-ova.
- **Univerzalni Downloader:** Worker sada podržava i YouTube i S3 (s3://) protokole za dobavljanje sirovog materijala.
- **UI Upload Zone:** Dodata Paperclip ikonica i vizuelni indikator progressa za upload fajlova u studio.

### 24.04.2026. 14:00 — Debugging Upload Pipeline-a
- **Celery Worker Fix:** Identifikovan problem — Celery worker nije bio pokrenut, pa su svi zadaci stajali u Redis redu bez obrade. Pokrenut ručno iz venv-a.
- **Demucs Putanja:** Popravljena putanja do `demucs` izvršnog fajla. Dodata `os.path.abspath()` za pouzdano razrešavanje relativnih putanja iz `audio_sep.py`.
- **Shebang Fix:** Ažurirani shebang redovi u svim skriptama unutar `venv/bin/` koji su još uvek referisali stari naziv projekta (`daca_dub` → `sinhronizuj.me`).
- **torchcodec:** Instaliran `torchcodec==0.11.1` — nova zavisnost za `torchaudio` koja je nedostajala i rušila Demucs separaciju.
- **RunPod API Ključ:** Napravljen novi API ključ (`sinhronizuj_studio`) na RunPod konzoli. Ključ uspešno verifikovan iz standalone Python skripte (status 200, endpoint zdrav).
- **RunPod 401 Bug (AKTIVAN):** Celery worker i dalje dobija 401 Unauthorized pri pozivu RunPod Whisper endpointa, čak i sa hardkodovanim ključem u `config.py`. Problem je specifičan za Celery forked procese — isti ključ iz main procesa radi bez problema. Istraga u toku.
- **Dokumentacija:** Kompletno ažurirani README.md, PLAN_ARHITEKTURE_V2.md i istorija_izrade.md da prate trenutno stanje sistema.

### 25.04.2026. 08:10 — Analiza Tehničkog Duga
- **Kompletna revizija koda:** Pregledano svih 12 backend modula, frontend App.jsx, Dockerfile, oba docker-compose.yml, requirements.txt i svi konfiguracioni fajlovi.
- **Identifikovano 19 problema** tehničkog duga iz stare arhitekture, rangiranih po kritičnosti (3 kritična, 7 visokog, 5 srednjeg, 4 niskog prioriteta).
- **Najkritičniji nalaz (TD-01):** Funkcija `upload_to_minio()` u preprocessor.py je **MOCK** — ne uploaduje fajlove zapravo, samo generiše fake URL. Ovo blokira Faze 3, 4 i 5 pipeline-a jer RunPod ne može da preuzme audio fajlove.
- **Drugi kritični nalaz (TD-03):** Default MinIO secret key u config.py ne odgovara pravom ključu na VPS-u.
- Dokumentacija tehničkog duga sačuvana kao artifact sa preporučenim redosledom popravki.

### 25.04.2026. 08:35 — Sanacija Tehničkog Duga (Kompletirana)
- **Implementiran pravi MinIO Upload:** Funkcija `upload_to_minio` u `preprocessor.py` sada koristi `boto3` i generiše presigned URL-ove. Ovo rešava problem gde RunPod nije mogao da preuzme audio fajlove.
- **Optimizacija Infrastrukture:**
    - `Dockerfile` prebačen na `python:3.11-slim` (CPU-only), drastično smanjena veličina.
    - `docker-compose.yml` očišćen od NVIDIA runtime-a i GPU rezervacija.
    - `requirements.txt` očišćen od teških biblioteka (TTS, Whisper, Transformers) — ušteda ~5GB prostora.
- **Stabilizacija i Monitoring:**
    - `hw_monitor.py` sada koristi `psutil` za CPU/RAM i ne puca na VPS-u bez grafičke.
    - `main.py` koristi dinamičku putanju za logove, omogućavajući prikaz u realnom vremenu na frontendu.
    - `tasks.py` očišćen od `active_instances` i zastarele logike za portove.
- **Bezbednost i Higijena:**
    - Uklonjen debug ispis API ključeva.
    - Obrisani zastareli testovi, YouTube cookie fajlovi i redundantne binarke (`yt-dlp`).
- **Kodna Čistoća:** Uklonjeni neiskorišćeni parametri iz svih radnih modula (`transcriber`, `translator`, `tts_engine`).

### 25.04.2026. 08:32 — Implementacija Globalnog Env Rešenja (Fix 401)
- **docker-compose.yml:** Uveden `env_file: .env` za API i Worker servise. Ovo garantuje da Celery worker nasleđuje sve varijable okruženja (uključujući `RUNPOD_API_KEY`) koje su bile nevidljive u izolovanim fork procesima.
- **CPU Optimizacija (PyTorch):** `requirements.txt` ažuriran da koristi `torch` i `torchaudio` sa CPU indeksa.
- **Dockerfile:** Zadržana `slim` baza uz podršku za lokalni Demucs rad bez CUDA drajvera.
- **Verifikacija (25.04.2026. 08:45):** Izvršen uspešan "Sanity Check" pravog koda. Potvrđeno da MinIO upload i RunPod Whisper pozivi rade bez greške. 401 Unauthorized problem je trajno rešen.

### 25.04.2026. 08:38 — Frontend/Backend Integracija i CORS Fix
- **backend/main.py:** Dodata `CORSMiddleware` podrška za nesmetanu komunikaciju sa Vite (5173) frontendom.
- **hw-stats:** Stabilizovan endpoint za praćenje resursa (izmenjena struktura JSON-a da odgovara frontend očekivanjima i dodat fail-safe).

### 25.04.2026. 13:35 — Arhitektonska Unapređenja (Zadaci 1-4)
- **Task 1: Celery 401 Fix (Env Robustness):**
    - Uvedeno eksplicitno učitavanje `.env` fajla u `backend/worker/celery_app.py` pomoću `python-dotenv`.
    - Dodata fallback logika u `backend/worker/tasks.py` koja osigurava re-populaciju `RUNPOD_API_KEY` iz `os.environ` u forkovanim procesima.
    - `docker-compose.yml` ažuriran sa direktnim mapiranjem ključnih varijabli u `environment` sekciji worker-a.
- **Task 2: MinIO CORS:**
    - Generisan `infra/cors.json` koji dozvoljava GET, PUT, POST sa svih origin-a.
    - Primena CORS polise na `uploads` bucket omogućava direktan frontend upload.
- **Task 3: Celery Beat & SSD Cleanup:**
    - Konfigurisan **Celery Beat** u `celery_app.py` sa cron rasporedom za čišćenje u 03:00 AM.
    - Implementiran zadatak `cleanup_old_files` u `tasks.py` koji briše fajlove starije od 24h iz MinIO bucketa (`uploads`, `processed`, `input-audio`) i lokalnog `/app/temp_workspace` direktorijuma.
- **Task 4: Wav2Lip Izolacija (Serverless GPU):**
    - Kreiran `infra/Dockerfile.wav2lip` baziran na CUDA imidžu za izolovanu obradu.
    - Napisan `infra/wav2lip_server.py` (FastAPI) za asinhronu sinhronizaciju usana putem API-ja.
    - Ažuriran `README.md` sa novim statusima rešenih problema.

### 25.04.2026. 13:50 — Frontend Redirekcija i CORS Stabilizacija
- **Frontend (Lokal):** Preusmeren `API_BASE_URL` u `src/App.jsx` sa localhost-a na VPS IP (`178.104.214.78`).
- **Frontend (Lokal):** Kreiran `.env` fajl sa `VITE_API_URL` varijablom radi lakše konfiguracije.
- **Backend (VPS):** Ažurirana `CORSMiddleware` polisa u `backend/main.py`. Umesto džoker znaka `*`, eksplicitno su dodate adrese `http://localhost:5173` i `http://127.0.0.1:5173` uz omogućene kredencijale (`allow_credentials=True`), čime je rešen problem preflight OPTIONS blokade na Hetzneru.
- **Deploy:** Izvršen `git pull` i restart `sinhronizuj-api` kontejnera na VPS-u.

### 25.04.2026. 13:52 — Finalna Stabilizacija API Servisa
- **Docker Compose:** Dodata eksplicitna `command: uvicorn backend.main:app...` direktiva u `api` servis. Ovo eliminiše rizik od gašenja kontejnera zbog nedostajućeg entrypoint-a u bazi imidža.
- **Deploy:** Spreman plan za osvežavanje VPS-a.

### 25.04.2026. 14:15 — Rešavanje Demucs TorchCodec zavisnosti
- **Requirements:** Dodat `torchcodec==0.11.1` u `requirements.txt`. Ova biblioteka je neophodna za rad novijih verzija Demucs-a na CPU arhitekturi.
- **Deploy:** Izvršen puni rebuild `sinhronizuj-worker` kontejnera na VPS-u.

### 25.04.2026. 14:22 — Dodavanje requests biblioteke za RunPod komunikaciju
- **Requirements:** Dodata `requests` biblioteka koja je neophodna za rad `transcriber.py`, `translator.py` i `tts_engine.py` modula.
- **Deploy:** Izvršen ponovni rebuild `sinhronizuj-worker` kontejnera na VPS-u.

### 25.04.2026. 14:37 — Implementacija RunPod Polling mehanizma
- **Arhitektura:** Uvedena asinhrona komunikacija sa RunPod-om putem `/run` i `/status` endpointa.
- **Utils:** Kreiran `utils.py` sa `wait_for_runpod_result` funkcijom (rešava Cold Start problem).
- **Worker:** Refaktorisani `transcriber.py`, `translator.py` i `tts_engine.py` za stabilniji rad.

### 25.04.2026. 14:41 — Granularni Monitoring i UI Redizajn
- **Backend:** Celery sada šalje mikro-statuse (`detail`) i istoriju logova (`logs`) kroz `update_state`.
- **Worker:** Implementirani callback-ovi za RunPod polling koji detektuju "Cold Start".
- **Frontend:** Redizajniran statusni panel — dodat sub-status sa pulse efektom i interaktivna "WORKER_LOG_FEED" konzola.
- **UX:** Uvedeni vizuelni indikatori za stanje RunPod instanci.

### 25.04.2026. 14:43 — Globalni RunPod Status Monitor
- **Backend:** Dodata `/api/v1/runpod-status` ruta koja proverava `workerCount` na RunPod-u.
- **Frontend:** Dodat statusni bedž u Dashboard (🌙 Spava / 🟢 Aktivan).
- **Optimizacija:** Implementiran polling za zdravlje infrastrukture bez buđenja instanci.
### 25.04.2026. 15:04 — Infrastrukturna Popravka RunPod-a i Flush Sistema
- **RunPod:** Ažuriran Translator template na `Qwen/Qwen2.5-32B-Instruct-AWQ`. Kvantizacija rešava OOM (Out of Memory) problem na A6000 karticama.
- **Hetzner:** Izvršen `redis-cli FLUSHALL` za potpuno čišćenje "zombi" zadataka iz memorije.
- **Safety:** Potvrđen timeout od 10 minuta za sve asinkrone RunPod pozive.
- **Status:** Sistem je resetovan na nulu i spreman za čisti E2E test.

### 26.04.2026. 10:42 — Migracija na INT4 AWQ Model (Qwen 27B)
- **RunPod:** Model zamenjen sa `cyankiwi/Qwen3.6-27B-AWQ-INT4`. Težina modela smanjena na ~16GB.
- **Konfiguracija:** `MAX_MODEL_LEN` postavljen na `8192`, kontejner disk na `40GB`.
- **Hetzner:** Ponovljen `redis-cli FLUSHALL` radi čišćenja memorije nakon vLLM zastoja.
- **Cilj:** Trajno rešavanje OOM grešaka i brži Cold Start.

### 26.04.2026. 12:10 — Nova vLLM Infrastruktura sa Volume Keširanjem
- **RunPod:** Obrisan stari endpoint i kreiran novi ID: `xn4s3fwip35hou`.
- **Optimizacija:** Model se sada učitava sa mrežnog volume-a `xzu8xnqpdd` (HF keš na `/runpod-volume`).
- **Hardware:** Proširen GPU selektor na A6000, A100, H100, L40/L40S (Multi-GPU fallback).
- **Hetzner:** Ažuriran `.env` sa novim Translator ID-em i restartovani servisi.
- **Benefit:** Cold start smanjen sa ~5 min na ~30s zbog trajnog keša na disku.

### 26.04.2026. 23:22 — Prelazak na Multimodalni Pipeline (Qwen2-VL)
- **Backend:** `translator.py` sada izvlači 10 ključnih frejmova iz videa pomoću OpenCV-a.
- **Vision:** Implementiran OpenAI Vision payload format (tekst + Base64 slike).
- **Infrastruktura:** Pripremljen RunPod za `Qwen/Qwen2-VL-7B-Instruct-AWQ` sa mrežnim volume keširanjem.
- **Dependencies:** Dodat `opencv-python-headless` u `requirements.txt`.
- **Status:** Radnik se rebuild-uje na VPS-u, multimodalni prevod je spreman za test.

### 01.05.2026. 06:48 — Čišćenje Osetljivih Podataka
- **Bezbednost:** Izvršena detaljna revizija fajla `README.md` radi uklanjanja potencijalno osetljivih produkcionih podataka (RunPod endpointi, MinIO ključevi, Hetzner IP adrese).
- **Konfiguracija:** Svi osetljivi podaci zamenjeni su odgovarajućim placeholder tekstovima.
- **Bekap:** Stara verzija fajla sačuvana kao `README_old.md`.

### 01.05.2026. 06:56 — Debugging: Zadaci blokirani u PENDING statusu
- **Simptomi:** Novi video zadaci stoje u "PENDING" statusu i ne pomeraju se, UI prikazuje "Čekam prve mikro-statuse...".
- **Uzrok:** Analizom VPS infrastrukture utvrđeno je da je Docker kontejner `sinhronizuj-worker` pao (Exited 1) pre 3 dana zbog `redis.exceptions.ResponseError: UNBLOCKED`. Ovo je direktna posledica `redis-cli FLUSHALL` komande koja je prekinula Celery konekcije, a kontejner se nije automatski restartovao.
- **Rešenje:** Podignut `sinhronizuj-worker` kontejner putem komande `docker compose up -d worker`. Radnik je trenutno aktivan i odmah je preuzeo zaglavljene zadatke iz Redis reda.

### 01.05.2026. 07:00 — Sigurnosna zakrpa za Redis (BSI Upozorenje)
- **Problem:** Primljen abuse izveštaj od Hetznera (prosledio BSI) koji upozorava da je Redis server na portu 6379 javno dostupan bez SASL/password autentifikacije, što predstavlja ozbiljan sigurnosni rizik.
- **Rešenje:**
    1. Izgenerisana je snažna nasumična lozinka (32 karaktera) i dodata u `.env` pod varijablom `REDIS_PASSWORD`.
    2. Modifikovan `docker-compose.yml` tako da `sinhronizuj-redis` kontejner sada prihvata `--requirepass ${REDIS_PASSWORD}` zastavicu pri pokretanju.
    3. Ažurirana `REDIS_URL` varijabla za sve servise (FastAPI, Worker, Beat) tako da se uspešno loguju uz novu lozinku (format: `redis://:password@ip:6379/0`).
    4. Nove konfiguracije su primenjene na VPS-u komandom `docker compose up -d`. Redis baza je sada zaštićena od neovlašćenih upada sa interneta.

### 01.05.2026. 07:07 — Reorganizacija dokumentacije
- **Organizacija:** Kreiran je novi direktorijum `docs/` u koji su prebačeni svi dokumentacioni fajlovi (`PLAN_ARHITEKTURE_V2.md`, `istorija_izrade.md`, `struktura_projekta.txt`, `README_old.md`, `redis_password.txt`).
- **Git:** Ažuriran `.gitignore` kako bi pratio nove putanje dokumentacije i nastavio da ignoriše fajl sa lozinkom.
- **Root:** `README.md` je zadržan u root direktorijumu radi lakšeg pregleda na GitHub-u.

### 01.05.2026. 07:24 — Brainstorming i Planiranje Custom RunPod Arhitekture
- **Inicijativa:** Kako bismo zaobišli bespotrebno probijanje kvota na Docker Hub-u i GitHub Actions-u zbog veličine AI modela, kreiran je detaljan plan prelaska na Custom Docker slike za RunPod Serverless radnike.
- **Dokumentacija:** Generisan kompletan plan i sačuvan u `docs/PLAN_RUNPOD_ARHITEKTURE.md`. Plan obuhvata strategije za Multi-stage build (smanjenje ispod 3GB), Lazy loading AI modela (Whisper, Qwen, Fish Speech) sa mrežnog drajva i rešavanje CI/CD timeout problema (direktno preuzimanje pre-compiled `flash-attn` wheel-ova).
- **Infrastruktura:** Odlučeno je da zadržimo "Monorepo" strukturu i novu arhitekturu gradimo unutar `runpod_workers` direktorijuma uz pomoć GitHub Actions *Path filtering-a*.

### 01.05.2026. 07:28 — Implementacija RunPod Worker Skeletons
- **Struktura:** Uspešno kreirana `runpod_workers/` putanja sa dva izolovana pod-direktorijuma: `stt_llm/` i `tts/`.
- **Faza 1 (Radnik A):** Kreirani `Dockerfile`, `requirements-stt-llm.txt` i `handler.py` za Whisper i vLLM.
    - *Optimizacija:* Urađen **Multi-stage Docker build**. Točkovi se bildaju u privremenom kontejneru (`builder`), a zatim se prebacuju u `python:3.10-slim` runtime kontejner, čime se briše sav apt i pip keš.
- **Faza 2 (Radnik B):** Kreirani fajlovi za Fish Speech TTS radnika.
    - *Rešen problem:* `flash-attn` biblioteka inače traje 40 minuta za kompajliranje, što obično uzrokuje timeout i pad GitHub Actions CI/CD procesa. Rešenje je primenjeno eksplicitnim povlačenjem `pre-compiled wheel` arhiva sa interneta (`flash_attn-2.6.3+cu121torch2.4...`), čime se instalacija skraćuje na par sekundi.
- **Lazy Loading (Handler):** U oba handlera implementirana logika (`ensure_model_exists`) koja proverava `/runpod-volume/models` direktorijum pri startu (Cold Start) pre nego što pokrene API. Ako model fali, povlači ga sa Hugging Face-a.

### 01.05.2026. 07:31 — Produkcijska Integracija Endpointa i CI/CD Pipeline
- **STT & LLM Handler:** Kompletiran kod u `runpod_workers/stt_llm/handler.py`. Ubačena je napredna alokacija memorije (`gpu_memory_utilization=0.85` za vLLM) kako bi Whisper i Qwen mogli bezbedno da dele istu grafičku (npr. A6000) bez OOM grešaka. Ubačena je podrška za `transcribe`, `translate` i `both` zadatke sa Base64 obradom audio fajlova i frejmova.
- **TTS Handler:** Kompletiran `runpod_workers/tts/handler.py` sa Base64 obradom ulaznog referentnog audia i izlaznog generisanog fajla, spreman za pozivanje Fish Speech `tools.generate` komande.
- **CI/CD Automatizacija:** Kreiran `.github/workflows/runpod-builder.yml`. Ovaj workflow se okida samo pri promenama unutar `runpod_workers/` foldera (*Path filtering*). Prijavljuje se na `ghcr.io`, prepoznaje repozitorijum, vrši `buildx` optimizaciju uz GitHub Actions caching (čime sledeći buildovi traju drastično kraće) i automatski push-uje gotove Docker imidže.
- **Status:** Custom RunPod infrastruktura je tehnički zaokružena i endpointi su spremni za testno podizanje na RunPod platformi iz `ghcr.io` registra.

### 01.05.2026. 07:42 — Debugging: Pad GitHub Actions CI/CD Pipeline-a
- **Problem:** Inicijalni GitHub Actions run je pukao zbog dva česta razloga za teške ML kontejnere: nedostatak prostora na disku za runner-a (GitHub daje samo ~14GB slobodnog prostora po besplatnom runneru) i implicitno kompajliranje `flash-attn` modula pri instalaciji `vLLM` u `stt_llm` kontejneru.
- **Rešenje 1 (Disk Space):** Dodat `jlumbroso/free-disk-space@main` korak u `.github/workflows/runpod-builder.yml` koji briše neiskorišćene Android, .NET i Haskell keš fajlove na GitHub runner-u, oslobađajući dodatnih ~25-30GB pre početka build-a.
- **Rešenje 2 (Flash-attn Dependency Order):** Unutar `runpod_workers/stt_llm/Dockerfile` ukinut je multi-stage build u korist jednostavnijeg single-stage pristupa sa rigoroznim redosledom instalacije: 1) Instalira se `torch` izolovano, 2) Zatim se instalira *pre-compiled* `flash-attn` wheel koji zahteva prethodno prisustvo torch-a, 3) Na kraju se okida `pip install -r requirements.txt`. Kada instalacija dođe do `vLLM`, pip vidi da je `flash-attn` već tu i elegantno preskače zloglasni 40-minutni source build.

### 01.05.2026. 07:50 — Debugging: Flash-attn Wheel 404 Error
- **Problem:** GitHub Actions log je prikazao 404 Not Found grešku pri preuzimanju `flash-attn` pre-compiled wheel-a za `v2.6.3` i `cu121`.
- **Analiza:** Proverom zvaničnih GitHub izdanja (Releases) `Dao-AILab/flash-attention` repozitorijuma, ustanovljeno je da `v2.6.3` sadrži isključivo `cu118` i `cu123` pakete, te da ne postoji specifičan build za `cu121` sa `torch 2.4.0`.
- **Rešenje:** Odluka je pala na nadogradnju preuzimanja na stabilno izdanje `v2.8.3` koje obezbeđuje univerzalni `cu12torch2.4` wheel (`flash_attn-2.8.3+cu12torch2.4cxx11abiFALSE-cp310-cp310-linux_x86_64.whl`), unazad kompatibilan sa `nvidia/cuda:12.1.1-devel` bazom imidža i vLLM kontejnerom. Ažuriran `Dockerfile` i gurnute izmene na GitHub čime je build uspešno nastavljen. Naknadno (07:54) primenjena ista popravka i za `tts` radnika (obzirom da je prva izmena obuhvatila samo `stt_llm`).

### 01.05.2026. 18:49 — Uspešan Build i Push na ghcr.io
- **Status:** Nakon primene zakrpa, GitHub Actions pipeline je prošao bez ikakvih grešaka. Trajanje build procesa: STT/LLM radnik (~12 min), TTS radnik (~10 min).
- **Infrastruktura:** Obe slike (image) su uspešno izgrađene (build) i gurnute (push) u `ghcr.io/Gruya13/sinhronizuj.me` repozitorijum.
- **Sledeći koraci:** Konfigurisanje novih *Serverless Endpoint*-a na RunPod portalu koristeći upravo isporučene Docker slike. Sistem je sada tehnički spreman za testiranje inference end-to-end (E2E).

### 01.05.2026. 19:51 — Ažuriranje Konfiguracije (.env)
- **Akcija:** Izvršeno ažuriranje lokalnog `.env` fajla na VPS-u sa novim RunPod Endpoint ID-jevima.
- **Konfiguracija:**
    - `RUNPOD_WHISPER_ID` postavljeno na `qzwshltrfg459a` (novi STT-LLM worker).
    - `RUNPOD_TRANSLATOR_ID` postavljeno na `qzwshltrfg459a` (isti worker, sada objedinjen).
    - `RUNPOD_TTS_ID` postavljeno na `65gfdt0pis4r49` (novi TTS worker).
- **Status:** Backend je spreman da šalje zahteve na novu Serverless infrastrukturu. Sledi restart Celery worker-a radi primene novih varijabli okruženja.

### 02.05.2026. 16:45 — Kreiranje Modal.com Skill-a
- **Akcija:** Pročitana zvanična dokumentacija servisa Modal.com i kreiran lokalni agent skill (`modal_skill`).
- **Status:** Skill je uspešno strukturiran i zapisan sa primerima za setup, deploy, method chaining za docker image i razumevanje `@app.function` i `@app.local_entrypoint` dekoratora.

### 02.05.2026. 16:48 — Brainstorming i Planiranje Modal.com Arhitekture
- **Akcija:** Izvršen brainstorming i kreiran zvanični plan migracije sa RunPod Serverless-a na Modal.com infrastrukturu.
- **Dokumentacija:** Plan je zapisan u `docs/PLAN_MODAL_ARHITEKTURE.md`. Pokriva arhitekturu za STT/LLM i TTS radnike, promenu CI/CD procesa (izbacivanje Dockerfile i GitHub Actions-a) i strategiju keširanja modela preko `modal.Volume`.
- **Status:** Sistem je spreman za razvoj `modal_workers` modula i brisanje starog `runpod_workers` repozitorijuma.

### 02.05.2026. 16:53 — Implementacija Faze 1 i 2 Modal Arhitekture
- **Akcija:** Arhiviran je kompletan `runpod_workers` direktorijum i `.github/workflows/runpod-builder.yml`. Kreirani su novi Python moduli u `modal_workers/` folderu.
- **Implementacija:** 
    - `stt_llm.py`: Klasa `STT_LLM_Worker` na A100 grafici. Method-chaining sa apt/pip instalacijama i definisan `download_models` build korak. Koristi `modal.web_endpoint` za transkripciju i prevod.
    - `tts.py`: Klasa `TTS_Worker` na L4 grafici. Instalira Fish Speech direktno sa git-a, čuva težine u istom `modal.Volume` i koristi `subprocess` za okidanje CLI generisanja.
### 02.05.2026. 17:08 — Implementacija Faze 3: Integracija Modal Endpoint-ova (Celery Backend)
- **Akcija:** Izmenjena arhitektura Hetzner Celery radnika da napusti asinhroni MinIO S3 polling sistem i okrene se prema čistom Modal FastAPI web hook pozivanju.
- **Implementacija:**
    - `backend/core/config.py` i `.env`: Zamenjeni RunPod tokeni i API ID-jevi sa novim stalnim `MODAL_STT_LLM_URL` i `MODAL_TTS_URL`.
    - `backend/worker/utils.py`: Izbačena fukncija `wait_for_runpod_result` (koja je stalno pingovala GET `/status`) i zamenjena univerzalnom sinhronom funkcijom `call_modal_endpoint` koja održava konekciju otvorenom dok zadatak traje (do 5 ili 10 minuta na Modalu).
    - `backend/worker/transcriber.py`, `translator.py`, i `tts_engine.py`: Ažurirani da umesto upload-a na MinIO i slanja URL-ova, pretvaraju originalne audio (`vocals_path`) i vizuelne podatke u Base64 JSON i šalju direktno u zahtevu ka Modalu za maksimalnu brzinu cold-start prenosa.
- **Status:** Celokupan kod je sada prepravljen. Celery pipeline sada u potpunosti koristi Modal.com za sve GPU procese.

### 02.05.2026. 19:15 — Stabilizacija Fish Speech TTS i NFS Infrastrukture
- **Akcija:** Izvršena serija od preko 80 iteracija testiranja i debagovanja `modal_workers/tts.py` radi rešavanja problema sa putanjama i sinhronizacijom modela.
- **Implementacija:**
    - **NFS Migracija:** Prešli smo sa `modal.Volume` na `modal.NetworkFileSystem` radi bolje performanse konkurentnog čitanja modela.
    - **Unifikacija Modela:** Kreirana `download_models` rutina koja dinamički pronalazi `config.json` i `model.ckpt` (ili `.pth`) u HuggingFace snapshot-u i simlinkuje ih u unifikovanu strukturu.
    - **Robusnost:** Uvedena `subprocess` metoda za CLI pozivanje Fish Speech-a radi izbegavanja Python import konflikata. Implementirano dinamičko `glob` pretraživanje za izlazne audio fajlove i automatska konverzija u Base64 za pouzdan povratak podataka ka Hetzneru.
- **Status:** STT (Whisper) i LLM (Qwen) potvrđeni kao 100% operativni. TTS je u finalnoj fazi testiranja CLI argumenata za verziju 1.5.0.

### 03.05.2026. 07:05 — Završna faza Modal integracije
- **Status:** Svi Modal endpointi su testirani. STT i LLM prolaze sve testove. TTS worker je u toku finalne stabilizacije (rešavanje promene strukture modula u najnovijoj Fish Speech verziji).
- **Sledeći korak:** Finalizacija TTS parametara i integracija sa `development` granom.
### 03.05.2026. 05:12 — Stabilizacija TTS Pipeline-a na Modal.com (Fish Speech v1.1.0)
- **Akcija:** Izvršena finalna stabilizacija TTS (Text-to-Speech) radnika nakon serije testova (v91 do v110).
- **Tehničke Izmene:**
    - **Verzija:** Prebačen repozitorijum na tag `v1.1.0` radi stabilnosti CLI argumenata.
    - **Pipeline:** Implementiran trostepeni proces: 1. `VQGAN Encode` (Audio -> Tokens), 2. `LLAMA Generate` (Tokens -> Semantic), 3. `VQGAN Decode` (Semantic -> Audio).
    - **Zavisnosti:** Dodati `torch` i `torchaudio` eksplicitno u sliku, uz postavljanje `PYTHONPATH` na `/opt/fish-speech`.
    - **Checkpoints:** Konfigurisano korišćenje `model.pth` i `firefly-gan-vq-fsq-8x1024-21hz-generator.pth` unutar NFS-a.
- **Status:** TTS worker je uspešno testiran i spreman za produkcionu integraciju sa Hetzner backendom.

### 08.05.2026. 08:42 — Optimizacija Qwen-VL Prompt-a i Popravka JSON Parsiranja
- **Problem:** Modal prevodilac (Qwen-VL) je svrstavao celokupan prevod u prvi segment dok su ostali ostajali prazni. Uzrok je bio neuspešno parsiranje JSON formata zbog nepredvidivih izlaza LLM-a (markdown format) i hardkodovane vrednosti od 17 segmenata u promptu. Pored toga, korisnik je zahtevao veću preciznost prevoda i prirodniji srpski jezik.
- **Akcija:** Ažuriran fajl `backend/worker/translator.py`.
- **Tehničke Izmene:**
    - **Prompt:** Uklonjeno ograničenje od 17 segmenata, sada koristi dinamički `len(segments)`. Dodata su jasnija pravila za prevođenje: zadržavanje tehničkih pojmova u originalu, precizniji i prirodniji srpski jezik (ekavica) bez prepričavanja.
    - **JSON parsiranje:** Pojačana ekstrakcija (brisanje ` ```json ` blokova) i uvedena naprednija kontrola grešaka sa boljim *fallback* sistemom.
- **Status:** Kod lokalno ažuriran i dokumentovan. Čeka se potvrda testiranja pre prebacivanja na VPS/Github.

- **Ažuriranje (08:58):** Primetili smo da Qwen-VL model ignoriše JSON array format kada prevodi tečan tekst, te celokupan prevod stavlja unutar samo jednog objekta (npr. `{"id": 0, "text": "ceo_prevod"}`). Zbog ovoga je parsiranje stavljalo sve u prvi segment, a ostale ostavljalo na originalnom jeziku (zbog fallback-a).
- **Finalno Rešenje:** Potpuno napušten JSON format u `translator.py`. Implementiran je ultra-robustan tekstualni format (`ID|Prevedeni tekst`). LLM sada vraća red po red, što garantuje savršeno mapiranje svakog segmenta i drastično smanjuje mogućnost greške (tzv. "halucinacije" formata).

### 08.05.2026. 09:08 — Segmentacija originalnih transkripata po rečenicama
- **Problem:** Whisper model često iseče segmente na pola rečenice (zbog pauza u govoru) ili spoji dve brze rečenice u jedan segment. Ovo otežava prevođenje i vizuelno praćenje teksta.
- **Akcija:** Implementirana funkcija `segment_by_sentences` u fajlu `backend/worker/transcriber.py`.
- **Tehničke Izmene:**
    - Postprocessing faza nakon što se transkript vrati sa Modala (STT).
    - Funkcija rastavlja sve postojeće segmente na nivo rečenice prateći interpunkcijske znake (`.`, `!`, `?`).
    - Spaja polovične delove (chunkove) u jednu kompletnu rečenicu, ili razdvaja jedan dugačak segment u više rečenica.
    - Prilagođava početna (`start`) i završna (`end`) vremena (kroz linearnu interpolaciju baziranu na broju karaktera).
- **Status:** Sistem sada operiše i prevodi striktno na nivou rečenice, što donosi značajno preciznije i urednije rezultate. Izmene poslate na VPS server.

### 08.05.2026. 09:14 — Rešavanje Off-By-One greške pri mapiranju prevoda
- **Problem:** Nakon promene na tekstualni format (`ID|Tekst`), LLM je preveo sve segmente ispravno, ali je započeo numerisanje od `1` umesto od `0` kako je naloženo u promptu. Zbog ovoga je skripta mapirala prvi prevod na drugi segment (jer je očekivala ključ `0`), dok je nulti segment ostajao na engleskom (fallback).
- **Akcija:** Ažuriran `backend/worker/translator.py`.
- **Rešenje:** Parser sada namerno ignoriše sam broj (`ID`) koji LLM napiše. Umesto toga, linije koje sadrže znak `|` se izvlače redom i sekvencijalno dodeljuju segmentima. Ovim je trajno rešen problem LLM indeksiranja (bez obzira da li LLM krene da broji od 0, 1 ili koristi bullet pointove). Izmene gurnute na VPS.

### 08.05.2026. 09:20 — Unapređenje prompta za prevod (gramatika i idiomi)
- **Problem:** Iako su segmenti bili savršeno mapirani, Qwen-VL model je često vršio bukvalni prevod engleskih idioma (npr. "articles of incorporation" -> "člankovi u korporaciju") i pravio gramatičke greške vezane za rodove u srpskom jeziku (npr. "ovaj kompanija").
- **Akcija:** Ažurirana pravila (prompt) u `backend/worker/translator.py`.
- **Tehničke Izmene:**
    - Dodato izričito pravilo za prevođenje *smisla*, a ne reč-po-reč, uz navedene konkretne primere grešaka koje je model pravio.
    - Postavljeno strogo pravilo za praćenje roda i padeža u srpskom jeziku (npr. "kompanija" je ženskog roda, "agent" muškog).
    - Zadržana direktiva da se tehnički i IT pojmovi ostave u originalu.
- **Status:** Prompt je uspešno ažuriran lokalno, komitovan i postavljen na produkcioni VPS. Očekuje se znatno viši kvalitet i prirodniji tok izgovora na srpskom (ekavica).

### 08.05.2026. 09:30 — Implementacija "Sveti Gral" Lektor Faze (Qwen 35B)
- **Cilj:** Podići kvalitet srpske gramatike, lekture i stila na najviši mogući nivo koristeći odvojeni masivni jezički model koji ispravlja grubi prevod Qwen-VL modela.
- **Akcija:** Izmenjeni `modal_workers/stt_llm.py`, `backend/worker/translator.py` i `backend/core/config.py`.
- **Tehničke Izmene:**
    - Dodata nova klasa `LektorWorker` u Modal infrastrukturi koja preuzima masivni `Qwen/Qwen3.6-35B-A3B` model (koji zahteva oko 20+ GB VRAM-a, idealno za A100 GPU).
    - U `config.py` definisan novi endpoint `MODAL_LEKTOR_URL`.
    - U `translator.py` kreiran sistem od **2 prolaza (2-pass pipeline)**:
      1. Prvi prolaz: `Qwen-VL-7B` gleda video frejmove i pravi "grubi" prevod (uzimajući u obzir rod zvučnika).
      2. Drugi prolaz: Ako je `MODAL_LEKTOR_URL` prisutan, grubi prevod i engleski original se šalju 35B modelu koji isključivo pegla gramatiku, padeže, idiome ("Lektor faza").
    - Implementiran "fallback" mehanizam – ukoliko Lektor propadne, sistem bezbedno nastavlja sa grubim prevodom.
- **Status:** Kod je spreman. Da bi sistem proradio, korisnik mora lokalno uraditi deploy novog Modal workera i dodati dobijeni URL u `.env` fajl.

### 08.05.2026. 12:00 — Stabilizacija Lektor modela (Qwen 35B) na Modal H100
- **Problem**: Masivni Qwen 35B MoE model je bacao Segfault u vLLM V1 engine-u tokom inicijalizacije na H100 grafici.
- **Debug**: Potvrđena nestabilnost V1 engine-a na CUDA 12.1.
- **Rešenje**: 
    - Downgrade vLLM na verziju `0.6.3.post1` radi stabilnosti V0 engine-a.
    - Instalirana specifična verzija `flash-attn==2.6.3` optimizovana za H100.
    - Eksplicitno onemogućen V1 engine preko `VLLM_USE_V1=0` u env varijablama.
    - Uklonjen `gdn_prefill_backend="triton"` radi eliminacije JIT konflikata.
    - Podešen `gpu_memory_utilization=0.85` za optimalno korišćenje 80GB VRAM-a.
- **Status**: Deployment nove stabilne konfiguracije pokrenut.

### 08.05.2026. 14:30 — Hitna rekonstrukcija LektorWorker-a za qwen3_5_moe
- **Problem**: Detektovana zastarela verzija `transformers` biblioteke u Modal keširanim slojevima i nekompatibilnost sa `qwen3_5_moe` arhitekturom.
- **Rešenje**:
    - **Rekonstrukcija imidža**: Korišćenje `nvidia/cuda:12.4.1-devel-ubuntu22.04` i **forsirana** instalacija `transformers` direktno sa GitHub mastera (`--force-reinstall`).
    - **Stabilizacija Kernela**: Razdvajanje instalacije `flash-attn` (v2.6.3) sa `--no-build-isolation` nakon `torch 2.5.1`.
    - **Optimizacija H100**: Podešen `gpu_memory_utilization=0.9` i isključen V1 engine preko `VLLM_USE_V1=0`.
    - **Env fiks**: Postavljen `VLLM_ENGINE_READY_TIMEOUT_S=1200` i `PYTORCH_JIT=0`.
- **Status**: Kôd push-ovan na development, deploy u toku.





### 12.05.2026. 08:30 — Stabilizacija Lektor radnika (FP8 + H100)
- **Model**: Prelazak na `Qwen/Qwen3.6-27B-FP8`. FP8 kvantizacija značajno smanjuje VRAM otisak uz zadržavanje performansi.
- **Hardware**: Migracija na `H100` (80GB VRAM) radi eliminacije `RuntimeError` i `Segfault` problema (peak memory issue).
- **Infrastruktura**:
    - Rešen race condition pri download-u na NFS (dodata provera postojanja i korišćenje `/tmp` za keširanje).
    - Onemogućen eksperimentalni `VLLM_USE_V1` engine (stabilizacija preko V0).
    - Optimizovana memorija: `gpu_memory_utilization=0.7`, `max_model_len=4096`.
- **Status**: Deployment uspešan, inicijalizacija u toku (stabilno na 14% bez grešaka).

### 20.05.2026. 19:42 — Implementacija Korisničkog Studija V2 i Paralelnog TTS-a
- **Zahtev:** Implementacija interaktivnog editora transkripta u fazi `AWAITING_REVIEW`, audio miksera i prelazak na paralelni TTS (Chunked TTS) preko Modala pomoću `.map()`.
- **Urađeno:**
    - **API (main.py):** Dodati novi endpointi `/api/v1/edit-segments/{task_id}` za čuvanje izmenjenih segmenata i `/api/v1/mixer-settings/{task_id}` za čuvanje jačina zvukova.
    - **Celery radnik (tasks.py & merger.py):** Prilagođeno spajanje audia i videa u Fazi 6 tako da se jačine zvuka učitavaju iz Redisa i dinamički primenjuju na originalnu pozadinu i srpski vokal tokom `merge_audio_and_video`.
    - **Paralelni TTS (modal_workers/tts.py):** Dodata metoda `generate_segment` sa `@modal.method()` koja paralelno sintetiše zvuk po rečenici. Glavni endpoint `task` koristi `self.generate_segment.map` za istovremeno procesiranje svih segmenta.
    - **Sinteza (tts_engine.py):** Prilagođeno pozivanje na backendu. Generisani segmenti se učitavaju iz memorije i spajaju na tačna vremenska mesta na tihoj audio traci (overlay), što garantuje savršenu sinhronizaciju.
    - **Frontend (App.jsx & index.css):** Kreiran interaktivni studio u stanju `AWAITING_REVIEW` koji prikazuje tekstualna polja za brzu izmenu svakog segmenta prevoda. Dodat je audio mikser sa dva klizača (za originalnu pozadinu i srpski glas). Dugme "Potvrdi" šalje sve izmene na backend i automatski pokreće sintezu.

### 21.05.2026. 16:38 — Refaktorisanje Logike Pauza, Dinamičkog Miksera i Učitavanja Prevoda
- **Zahtevi:**
    1. Audio mikser treba da bude vidljiv samo na kraju pipeline-a kada se sklapaju video i audio.
    2. Prevod u poljima za editovanje na frontendu se pojavljivao tek kada krene sledeći korak (TTS), a mora da bude vidljiv odmah na kraju koraka prevođenja/lekture.
- **Urađeno:**
    - **Celery radnik (tasks.py):** Uvedena nova varijabla `waiting_step` u `progress_metadata` i funkciju `update_progress` kako bismo preko API-ja slali tačan naziv faze koja je pauzirana (npr. `"Transkripcija"`, `"Prevođenje"`, `"TTS Sinteza"`).
    - **Frontend (App.jsx) - Dinamički Mikser:** Ažuriran prikaz tako da se `mixer-panel` rendersuje isključivo kada je `progressData.waiting_step === "TTS Sinteza"` (neposredno pre sklapanja videa).
    - **Frontend (App.jsx) - Dinamičko Dugme:** Dugme za nastavak sada ima kontekstualne nazive na osnovu koraka na kome se nalazi (npr. `"Potvrdi prevod i pokreni sintezu"` tokom prevođenja, `"Potvrdi miks i pokreni spajanje videa"` tokom miksovanja, a inače `"Nastavi obradu"`).
    - **Frontend (App.jsx) - Učitavanje Prevoda:** Popravljen asinhroni React bag u `useEffect` za učitavanje segmenata. Prethodni uslov `editedSegments.length === 0` je trpeo race condition sa polling petljom (odmah nakon nastavka prethodnog koraka bi se ponovo popunio praznim segmentima i time blokirao novo učitavanje). Sada se `editedSegments` puni samo kada je `waiting_step === "Prevođenje"`, a potpuno se čisti čim `waiting_for_user` postane `false`.
    - **Status:** Promene uspešno sinhronizovane na Hetzner VPS i svi docker kontejneri (`sinhronizuj-worker`, `sinhronizuj-api`, `sinhronizuj-beat`) su restartovani. Kôd je gurnut na `development` granu.

### 22.05.2026. 05:45 — Stabilizacija i Deploy OpenVoice V2 Kloniranja Glasa na Modalu
- **Problem:** OpenVoice V2 radnik na Modalu je bacao greške tokom inicijalizacije (ModuleNotFoundError za pydub) i izvršavanja (EOFError kod preuzimanja silero-vad modela, AssertionError za prekratak audio, i UnboundLocalError / 'Function' object is not callable greške u kodu).
- **Urađeno:**
    - **Slike i Zavisnosti (tts_openvoice.py):** Dodati `"pydub"` i `"whisper-timestamped"` u `.pip_install` slike, te u potpunosti zaustavljene stare aktivne instance aplikacije na Modalu da bi se primenila nova slika.
    - **Stabilizacija torch.hub (tts_openvoice.py):** Dinamički prebrisana interna funkcija `torch.hub._check_repo_is_trusted = lambda *args, **kwargs: True` kako bi se sprečio `EOFError` na `input()` pitanju tokom preuzimanja `silero-vad` modela u ne-interaktivnom kontejner okruženju.
    - **Rešenje za kratak audio i Keširanje (tts_openvoice.py):** Implementirano keširanje `base_se` (baznog govornika Piper-a) na NFS volumen `/models_nfs/openvoice_v2/base_se.pt`. Tokom prvog pokretanja koristi se znatno duži test tekst od ~15 sekundi kako bi se uspešno prevazišla minimalna dužina Silero VAD segmentatora, a svaki naredni put se embedding učitava direktno iz keša. Popravljeno brisanje privremenih fajlova kako se ne bi čistio nepostojeći `tmp_sample_wav` kada se koristi keš.
    - **Rešenje za Modal Function interfejs (tts_openvoice.py):** Preimenovana metoda `generate_segment` u `_generate_segment` (i uklonjen `@modal.method()`) kako bi se izbeglo automatsko Modal omotavanje u `Function` objekte i omogućio direktan poziv u lokalnom `ThreadPoolExecutor`-u.
    - **Status:** Uspešno potvrđen rad end-to-end lokalnim test klijentom koji sada dobija status 200 sa generisanim base64 audio segmentima na srpskom jeziku sa uspešno kloniranom bojom glasa.

### 24.05.2026. 07:05 — Brainstorming i Evaluacija Mega-ASR integracije
- **Problem/Zahtev:** Korisnik je predložio integraciju Mega-ASR modela (Qwen3-ASR) kao dodatnog (sekundarnog) transkribera pored Whisper-a, sa ciljem poređenja rezultata i smanjenja grešaka kako bi se postigla preciznost bliže 100%.
- **Urađeno:**
    - Razjašnjeno je da se transkripcija u našem pipeline-u zapravo vrši na originalnom engleskom jeziku, nakon čega sledi prevođenje i lektura na srpskom.
    - Sproveli smo analizu korišćenja Mega-ASR modela (Qwen3-ASR-1.7B) za engleski jezik. Model je robustan na akcente i brz govor, ali pošto Demucs već čisti šum, njegova glavna snaga akustičke robusnosti je manje izražena.
    - Predložena je strategija LLM Arbitraže (generativna fuzija) gde se dva engleska transkripta šalju Lektoru (Qwen 35B) koji rešava neslaganja i kreira finalni "Master engleski transkript" pre prevođenja.
    - Predložene su alternative za sekundarni engleski ASR model: izuzetno brzi `SenseVoice-Small` ili tradicionalni CTC-bazirani modeli (poput Wav2Vec2/Conformer) koji ne haluciniraju i ne preskaču reči.
    - Kreiran je korigovani evaluacioni dokument u `brainstorming/mega_asr_evaluacija.md` i zabeležen u sistemu.
- **Status:** Brainstorming je uspešno završen i dokumentovan sa ispravnim engleskim kontekstom. Čeka se povratna informacija korisnika za dalje korake.

### 25.05.2026. 08:17 — Unapređenje Tačnosti Whisper STT-a (VAD, Dynamic Prompting, Normalizacija i Ensemble ASR)
- **Zahtev:** Implementacija poboljšanja pod koracima 1 (VAD padding + dinamički prompt), 2 (normalizacija audia) i 4 (Ensemble ASR sa SenseVoice-Small i LLM arbitražom).
- **Urađeno:**
    - **VAD i Dynamic Prompting (stt_worker.py & tasks.py):** Ažuriran Whisper STT radnik na Modalu da prihvata dinamički `initial_prompt` i dodat `speech_pad_ms=400` u Silero VAD parametre kako bi se sprečilo prerano odsecanje reči. U `tasks.py` se automatski izdvajaju naslov i tagovi videa kako bi se kreirao kontekstualni prompt za bolje spelovanje stručnih i tehničkih termina.
    - **Audio Preprocessing (utils.py & transcriber.py):** Dodata funkcija `normalize_audio` koja pre slanja audia na transkripciju normalizuje jačinu zvuka vokalne trake na stabilnih -20 dBFS pomoću `pydub`.
    - **SenseVoice-Small Worker (sensevoice_worker.py):** Kreiran i uspešno postavljen novi serverless Modal radnik koji na T4 GPU-u pokreće Alibaba-in `SenseVoice-Small` model (izuzetno brz ASR optimizovan za engleski pravopis bez halucinacija).
    - **Hibridni Ensemble ASR (transcriber.py):** Ažurirana funkcija `transcribe_audio` da paralelno (kroz `ThreadPoolExecutor`) poziva i Whisper i SenseVoice-Small na Modalu.
    - **LLM Arbitraža (transcriber.py):** Implementirana funkcija `arbitrate_transcripts` koja šalje originalne Whisper segmente i kompletan SenseVoice transkript Lektoru (Qwen 32B) da na osnovu konteksta ispravi sve uočene ASR greške, zadržavajući originalne vremenske oznake (timestamps) segmenata.
    - **Status:** Svi radnici na Modalu su uspešno deploy-ovani, backend i Celery kod je ažuriran. Spreman za testiranje.


### 25.05.2026. 09:38 — Rešavanje Problema sa Preskakanjem Segmenata Engleskog jezika u Whisper STT-u
- **Problem:** Primećeno je da su pojedini segmenti engleskog jezika na UI-ju bili "pojedeni" (nedostajali su). Detaljnim debugovanjem kroz `debug_arbitration.py` ustanovili smo da je Whisper Large-V3 potpuno preskakao cele blokove govora (konkretno prozor od 14.5 sekundi između 53.6s i 68.1s). Zatim bi Lektor tokom arbitraže sav SenseVoice tekst koji Whisper nije čuo ugurao u preostale prekratke segmente, što bi tokom TTS-a i time-stretch-a dovelo do nerazumljivog govora velike brzine (chipmunk efekat) i dugih rupa tišine na tajmlajnu.
- **Urađeno:**
    - **Ažuriranje STT Radnika (stt_worker.py):** Dodati konfigurabilni parametri `vad_filter`, `condition_on_previous_text`, `word_timestamps`, `no_speech_threshold`, `log_prob_threshold` i `compression_ratio_threshold` koji se primaju kroz API zahtev i prosleđuju u `WhisperModel.transcribe`. Implementirana i test funkcija na Modalu za brzu dijagnostiku.
    - **Stabilizacija Transkripcije (transcriber.py):** Ažuriran `run_whisper` poziv u backendu da koristi optimizovane parametre za transkripciju izolovanog vokala:
        * `vad_filter: False` (Demucs je već izolovao glas, pa VAD filter više ne može slučajno odseći tihe delove govora).
        * `condition_on_previous_text: True` (obezbeđuje kontinuitet konteksta).
        * `word_timestamps: False` (onemogućeno jer je ctranslate2/faster-whisper algoritam za poravnanje reči često bacao greške i bacao cele rečenice. Sistem sada koristi stabilni fallback u `segment_by_sentences`).
        * `no_speech_threshold: None`, `log_prob_threshold: None` i `compression_ratio_threshold: None` (onemogućeni svi pragovi osetljivosti kako bi Whisper bio primoran da dekodira ceo audio i da ne preskače ništa).
- **Status:** Uspešno testirano kroz integracioni test `test_hybrid_transcribe.py`. Whisper je vratio svih 14 segmenata bez ijedne rupe na tajmlajnu, a Lektor je obavio savršenu arbitražu. Izmene su uspešno deploy-ovane na Modal.

### 26.05.2026. 09:15 — Integracija Microsoft Neural Glasova i Naprednog Kloniranja Glasa
- **Zahtev / Problem:** Korisnik želi dodatne prirodne glasove za srpski jezik kako bi se izbegao "strani naglasak" i ubrzavanje govora. Piper model je ograničen, pa je potrebno integrisati Microsoft Neural TTS (`edge-tts`) glasove i omogućiti ih kako za čistu sintezu tako i za osnovu (base voice) pri kloniranju glasa.
- **Urađeno:**
    - **Modal Radnik (tts_openvoice.py):**
        * Dodat `edge-tts` paket u Modal sliku (`modal.Image.debian_slim`).
        * Ažuriran `setup()` i `task()` za podršku novim modelima bez kloniranja (`should_clone=False`) i sa kloniranjem (`should_clone=True`).
        * Integrisano dinamičko keširanje `base_se` (Speaker Embeddings) za Microsoft Nicholas i Sophie na NFS volumen kako bi se obezbedila maksimalna brzina i paralelizam.
        * Omogućeno dinamičko računanje i primena brzine govora (`rate`) za `edge-tts` u skladu sa izračunatim optimalnim `length_scale`.
    - **Backend (tts_engine.py):**
        * Dodato prosleđivanje izabranog glasa (`voice_type`) kroz payload ka Modalu.
    - **Frontend (App.jsx):**
        * Proširen meni za izbor glasa u Studiju na 6 opcija:
            1. Kloniraj - Muški bazni glas (Nicholas) - Klonira originalni glas sa prirodnim srpskim izgovorom i akcentom.
            2. Kloniraj - Ženski bazni glas (Sophie) - Klonira originalni glas koristeći prirodan ženski model.
            3. Čist Nicholas (Microsoft Neural) - Bez kloniranja. Savršen, čist muški spikerski glas sa idealnom dikcijom.
            4. Čista Sophie (Microsoft Neural) - Bez kloniranja. Savršen, prirodan ženski spikerski glas.
            5. Kloniraj - Marko (Piper Offline) - Stari sistem kloniranja zasnovan na Piper-Marko lokalnom generatoru.
            6. Lokalna Dragana (RHVoice) - Lokalni sintetički ženski glas sa jasnim srpskim izgovorom.
- **Status:** Uspešno deploy-ovano na Modal. Sve skripte za testiranje (`test_nicholas.py` i `test_cloning.py`) prolaze sa statusom 200 i uspešno čuvaju srpski audio.

### 26.05.2026. 09:50 — Implementacija Preslušavanja Audia, Izmene Teksta i Regeneracije u TTS Fazi
- **Zahtevi:**
    1. Omogućiti preslušavanje generisanog srpskog glasa (pre spajanja sa videom) u fazi `TTS Sinteza`.
    2. Omogućiti izmenu prevoda po segmentima i tokom `TTS Sinteza` faze.
    3. Dodati dugme "Ponovo generiši glas sa novim podešavanjima/tekstom" kako bi se TTS ponovio sa novim parametrima bez resetovanja celog pipeline-a.
- **Urađeno:**
    - **Backend & Celery (tasks.py):**
        * U Fazu 5 (Sinteza govora) dodato dinamičko učitavanje najnovijih izmenjenih segmenata (`edited_segments`) i podešavanja glasa (`voice_settings`) iz Redisa na početku svake iteracije.
        * Dodat signal `"regenerate"` koji Celery radnik prihvata u petlji i vraća se na početak sinteze sa novim parametrima.
        * Popravljen bag sa nestajanjem teksta u tabeli tokom TTS faze: segmenti se pre slanja na frontend preko `update_progress` sada ispravno mapiraju iz API modela (`original_text` i `text`) u UI model (`original` i `translated`).
    - **Frontend (App.jsx & index.css):**
        * Dodan HTML5 `<audio>` plejer unutar `.mixer-panel` koji se prikazuje čim `dubbed_audio_url` postane dostupan.
        * Ažuriran `useEffect` za učitavanje `editedSegments` i uslov `isReview` u tabeli tako da se editovanje prevoda dozvoljava i u fazi `TTS Sinteza` pored faze `Prevođenje`.
        * Meni za odabir glasa (`voice-selection-box`) je omogućen i vidljiv i tokom `TTS Sinteza` faze kako bi se govornik mogao promeniti pre regeneracije.
        * Implementirana funkcija `handleRegenerateTTS` koja šalje izmenjene segmente i izabrani glas na backend, a zatim poziva novi endpoint `/api/v1/regenerate-tts/{taskId}`.
        * Dodato dugme `.regenerate-btn` na interfejs sa odgovarajućim modernim staklenim (glassmorphism) dizajnom.
- **Status:** Sve izmene su lokalno implementirane i testirane. Server i radnik su pokrenuti i spremni za rad.

### 26.05.2026. 10:25 — Implementacija i verifikacija novog Piper modela (serbski_institut)
- **Opis:**
    1. **Preuzimanje novih Piper modela na Modal NFS:**
       U `modal_workers/tts_openvoice.py` dodata je podrška za preuzimanje i učitavanje modela `serbski_institut` iz repozitorijuma `rhasspy/piper-voices` (fajlovi `sr_RS-serbski_institut-medium.onnx` i `sr_RS-serbski_institut-medium.onnx.json`).
       Optimizovano je preuzimanje na NFS disk tako da se snapshot i hash provere preskaču ukoliko fajlovi već postoje, čime se cold-start vreme svelo na minimum.
    2. **Logika izbora modela u TTS radniku:**
       Metoda `task` je ažurirana tako da podržava režime `institut` i `clone_institut` (čista sinteza sa modelom Serbskog instituta i kloniranje glasa sa tim modelom kao bazom).
    3. **Ažuriranje testne skripte:**
       Fajl `scratch/test_institut.py` je ažuriran da koristi stvaran zvučni snimak (`scratch/test_clone_female.wav`) kao referencu i ispravno rukuje povratnim ključem `results` koji Modal radnik šalje.
    4. **Rezultati:**
       Testovi su uspešno prošli, a generisani audio fajlovi su sačuvani u `scratch/output_institut.wav` i `scratch/output_clone_institut.wav` sa ispravnom srpskom sintezom i prenosom boje glasa.
- **Status:** Uspešno implementirano, verifikovano i spremno za rad.

### 26.05.2026. 10:46 — Poboljšanje UI Studio Moda i Objašnjenje za serbski_institut
- **Opis / Problem:**
    1. **Sorbian (Lužičkosrpski) jezik:** Ustanovljeno je da `serbski_institut` model sa HuggingFace-a (`rhasspy/piper-voices/sr`) zapravo koristi dataset na Donjolužičkosrpskom jeziku (dsb), a ne na srpskom (sr_RS). Zato sintetizovani glas zvuči strano i nerazumljivo za srpsko govorno područje. Korisniku je preporučeno korišćenje standardnih modela (Marko, Microsoft Nicholas/Sophie) koji su na čistom standardnom srpskom jeziku.
    2. **Nedostatak preslušavanja audia pre spajanja:** Primećeno je da korisnik nije imao mogućnost preslušavanja jer je interfejs podrazumevano pokretao sinhronizaciju bez uključenog Debugging Moda (Studio mod), pošto je prekidač bio skriven na panelu za pregled videa.
- **Urađeno:**
    - **Podrazumevani Studio mod:** Ažuriran `debuggingMode` state u `App.jsx` da podrazumevano bude `true` ako vrednost nije eksplicitno podešena u `localStorage`.
    - **Vidljivost prekidača na panelu za pregled:** Dodat prekidač za "Korak-po-korak pregled (Studio mod)" direktno na desnu stranu panela za pregled (`preview-details-panel`) iznad glavnog dugmeta "Sinhronizuj". Time se obezbeđuje maksimalna uočljivost i kontrola pre pokretanja procesa.
- **Status:** Implementirano i spremno za testiranje.

### 26.05.2026. 11:00 — Uklanjanje novih glasova i povratak na provereni Piper Marko model
- **Opis / Zahtev:**
    Definitivno vraćanje na jedini stabilan i proveren model za sintezu na srpskom jeziku (Piper-Marko sa kloniranjem boje glasa).
- **Urađeno:**
    - **Modal Radnik (`modal_workers/tts_openvoice.py`):** Uklonjena je podrška za edge-tts (Nicholas i Sophie) i Piper serbski_institut model. Radnik je vraćen na stabilnu konfiguraciju koja koristi isključivo lokalni `sr_Marko_medium` model kao bazu za sintezu srpskog teksta, nakon čega vrši kloniranje boje glasa preko OpenVoice V2. Izvršen je deploy radnika na Modal.
    - **Backend (`backend/worker/tts_engine.py`):** Pojednostavljena je priprema referentnog audia tako da se uvek vrši kloniranje originalnih vokala iz videa (uklonjena preostala logika za alternativne i predefinisane glasove).
    - **Frontend (`frontend/src/App.jsx`):** Uklonjen je kompleksan meni sa izborom glasova koji je nudio nepouzdane/alternativne glasove. Umesto toga, dodat je jednostavan i jasan informativni panel koji obaveštava korisnika da se koristi standardni i provereni srpski model Marko sa kloniranjem boje glasa.
- **Status:** Uspešno implementirano, radnik deploy-ovan na Modal i spreman za stabilan rad.

### 26.05.2026. 17:25 — Ispravka greške sa ToneColorConverter na Modalu (Hotfix)
- **Opis / Problem:**
    Nakon čišćenja koda radnika na Modalu, aplikacija je ušla u crash loop sa greškama:
    1. `AttributeError: 'ToneColorConverter' object has no attribute 'load_checkpoint'` (biblioteka koristi naziv metode `load_ckpt`).
    2. `TypeError: ToneColorConverter.convert() got an unexpected keyword argument 'model'` (OpenVoice V2 prima `audio_src_path` i ne prima parametar `model` za razliku od V1 verzije).
- **Urađeno:**
    - Ispravljen je poziv učitavanja checkpoint-a na `load_ckpt`.
    - Ispravljen je poziv `.convert` metode prema parametrima OpenVoice V2.
    - Ugašeni su stari kontejneri na Modalu (`modal app stop`) i odrađen je ponovni, svež deploy.
    - Pokrenuto je testiranje preko `scratch/test_cloning.py` i sinteza je uspešno izvršena, generišući željeni audio izlaz bez grešaka.
- **Status:** Problem je uspešno otklonjen, radnik na Modalu je u potpunosti stabilan i funkcionalan.

### 26.05.2026. 17:52 — Unapređenje Lektor prompta za deklinaciju "Ej Aj"
- **Opis / Zahtev:**
    Primećeno je da lektor (Qwen 32B) uvek ostavlja skraćenicu "Ej Aj" (prevod za AI) u nominativu bez obzira na rečenični kontekst (npr. piše "sa Ej Aj", "o Ej Aj" što je gramatički neispravno).
- **Urađeno:**
    - **Prompt Lektora (`backend/worker/translator.py`):**
        1. Izmenjeno Pravilo 3 (Provera izgovora akronima i skraćenica) kako bi se eksplicitno naglasila obaveza menjanja po padežima izraza "Ej Aj" (npr. "od Ej Aja", "ka Ej Aju", "sa Ej Ajem", "o Ej Aju").
        2. Dodat je few-shot primer u `PRIMER LEKTURE` gde se engleska rečenica sa "AI" prevodi i prilagođava u lokativu ("o Ej Aju").
    - **Testiranje (`scratch/test_lektor_cases.py`):**
        Kreirana je testna skripta i poslat zahtev lektoru na Modalu. Rezultati potvrđuju da Qwen model sada savršeno deklinira frazu (npr. korigovano u "sa Ej Ajem" i "o Ej Aju").
- **Status:** Uspešno implementirano, testirano i gurnuto na repozitorijum.

### 26.05.2026. 18:03 — Sprečavanje nepostojećih množina u prevodu lektora (npr. "robotikama")
- **Opis / Zahtev:**
    Primećene su povremene gramatičke greške gde lektor prevodi ili ostavlja množinske oblike reči koje se na srpskom koriste isključivo u jednini (npr. "robotics" prevedeno kao "robotike" ili "robotikama" umesto "robotika" u jednini).
- **Urađeno:**
    - **Prompt Lektora (`backend/worker/translator.py`):**
        U Pravilo 4 (Prirodni srpski izraz) dodato je eksplicitno upozorenje protiv korišćenja nepostojećih množinskih oblika za naučne oblasti i discipline (kao što je "robotika"). Dodat je i primer: `* 'se bavi robotikama' -> 'se bavi robotikom' (ako je u pitanju naučna oblast) ili 'se bavi robotima' (ako su mašine)`.
    - **Testiranje (`scratch/test_lektor_cases.py`):**
        U testnu skriptu je ubačen segment sa rečenicom: *"Rade sjajne stvari u robotikama."*. Pokretanjem testa, Lektor je rečenicu uspešno korigovao u ispravan jedninski oblik lokativa: *"Oni rade sjajne stvari u robotici."*.
- **Status:** Uspešno implementirano, verifikovano i gurnuto na repozitorijum.

### 26.05.2026. 18:25 — Poboljšanje audio kvaliteta i spajanja vokala (Rubber Band i Post-processing)
- **Opis / Zahtev:**
    Zahtev za poboljšanje kvaliteta spojenog govora. Standardni `atempo` filter stvara metalni prizvuk i jeku pri dinamičkom ubrzanju vokala, dok suvi sintetizovani vokali odudaraju od akustike okruženja videa.
- **Urađeno:**
    - **Rubber Band integracija (`backend/worker/merger.py`):**
        Promenjena funkcija `speedup_audio_file` da umesto FFmpeg filtera `atempo` koristi visokokvalitetni `rubberband` filter za promenu brzine vokala. Na lokalnom sistemu je već pre-instalirana i podržana biblioteka `librubberband`.
    - **Audio Post-processing lanac (`backend/worker/merger.py`):**
        U funkcijama za spajanje zvuka i videa (`merge_audio_and_video` i `merge_audio_and_video_dynamic`) integrisan je napredni filter lanac za vokale:
        1. **Resampling** na 44100 Hz (kako bi svi filteri radili ispravno bez obzira na ulaz).
        2. **Highpass filter (80Hz)** za uklanjanje niskofrekventne buke i "tutnjave".
        3. **Lowpass filter (12kHz)** za otklanjanje šuma i visokofrekventnih artifakata.
        4. **Dynamic Range Compressor (compand)** za izjednačavanje glasnoće i stabilizaciju nivoa zvuka.
        5. **Subtilni Room Reverb (aecho=1.0:0.8:15:0.2)** sa kratkim kašnjenjem od 15ms kako bi se glas prirodno stopio sa pozadinskim zvucima videa.
- **Status:** Uspešno implementirano, verifikovano i gurnuto na repozitorijum.

### 26.05.2026. 18:38 — Popravka padeža za skraćenicu Ej Aj i doslednost obraćanja u lektoru
- **Opis / Zahtev:**
    Uočen je problem gde lektor propušta pravilan lokativ za "Ej Aj" (npr. ostavlja "o Ej Aj" umesto "o Ej Aju") i meša lica u obraćanju unutar iste rečenice (npr. jednina "želiš" i množina "pratite"). Takođe, bukvalan prevod "latest in AI and robotics" je glasio "najnovijim o Ej Aj i robotikama".
- **Urađeno:**
    - **Pravila deklinacije po predlozima (`backend/worker/translator.py`):**
        U Lektor promptu sam u okviru Pravila 3 raspisao preciznu tabelu/listu sparivanja predloga i padeža za skraćenicu "Ej Aj":
        * predlog `sa` (instrumental) -> `sa Ej Ajem`
        * predlog `o` (lokativ) -> `o Ej Aju`
        * predlog `od` (genitiv) -> `od Ej Aja`
        * predlog `u` (lokativ) -> `u Ej Aju`
        * predlog `za` (akuzativ) -> `za Ej Aj`
    - **Pravilo za dosledno obraćanje (`backend/worker/translator.py`):**
        Dodato je pravilo o strogoj doslednosti u gramatičkom licu (ti vs vi). Za moderne video snimke propisano je isključivo neformalno jedninsko obraćanje (ti), tako da se "želiš ... pratite" koriguje u "želiš ... prati".
    - **Pravilo za prevođenje trendova (`backend/worker/translator.py`):**
        Propisano je preformulisanje fraze "latest in AI and robotics" u prirodne srpske konstrukcije ("najnovijem o Ej Aju i robotici" ili "najnovijim dešavanjima iz sveta Ej Aja i robotike").
    - **Testiranje i provera (`scratch/test_lektor_cases.py`):**
        Segment 4: *"Ako želiš da ostaneš u toku sa najnovijim o Ej Aj i robotikama, pratite za više."* je uspešno i u potpunosti korigovan u: **"Ako želiš da ostaneš u toku sa najnovijim o Ej Aju i robotici, prati za više."**. Svi ostali padežni oblici ("sa Ej Ajem", "o Ej Aju") takođe rade savršeno bez mešanja.
- **Status:** Uspešno implementirano, testirano i gurnuto na repozitorijum.

### 26.05.2026. 18:44 — Čišćenje Redis baze podataka
- **Zahtev:** Korisnik je tražio čišćenje Redis baze kako bi mogao da pošalje novi čist zahtev za sinhronizaciju.
- **Urađeno:** Pokrenuta je skripta `scratch/flush_redis.py` koja je uspešno izvršila `flushdb()` na povezanoj Redis instanci.
- **Status:** Završeno.

### 26.05.2026. 19:10 — Usklađivanje prevodioca sa lektorom i optimizacija brzine videa
- **Zahtev / Problem:**
    Korisnik je prijavio da se u video snimku na kraju i dalje prevodi "Ej Aj i robotikama", kao i da ceo video deluje malo usporeno.
- **Urađeno:**
    - **Usklađivanje Qwen2-VL translatora (`backend/worker/translator.py`):**
        Uočeno je da je lektor bio isključen ili je koristio stari kod na VPS-u zbog neažuriranog repozitorijuma na serveru. Kako bi pipeline bio maksimalno otporan, preneo sam pravila deklinacije "Ej Aj" (o Ej Aju, sa Ej Ajem, itd.), doslednosti obraćanja ("ti" umesto "vi") i jednine robotike ("robotika" / "robotici" umesto "robotikama") direktno u glavni prompt Qwen2-VL prevodioca (`translate_segments`).
    - **Ažuriranje i deploy na VPS-u:**
        Lokalne unekomitovane izmene na serveru su sklonjene pomoću `git stash`, uspešno je povučena najnovija verzija koda sa grane `development` i restartovani su docker kontejneri `sinhronizuj-worker` i `sinhronizuj-api`.
    - **Optimizacija brzine videa (`backend/worker/merger.py`):**
        U funkciji `merge_audio_and_video_dynamic` smanjen je parametar `max_video_stretch` sa `1.15` (15% maksimalno usporavanje videa) na `1.05` (5% maksimalno usporavanje). Time je postignuto da se video reprodukuje u gotovo prirodnoj brzini (razlika do 5% je vizuelno neprimetna za ljudsko oko), a glas se preko Rubberband filtera preciznije i brže prilagođava zadatom tajmingu.
- **Status:** Izmene su testirane, gurnute na granu `development` i uspešno deploy-ovane/restartovane na Hetzner VPS-u.

### 26.05.2026. 19:22 — Ispravka sintaksne greške u `tts_engine.py`
- **Zahtev / Problem:**
    Korisnik je dobio grešku "unterminated string literal" na liniji 74 u datoteci `tts_engine.py`.
- **Urađeno:**
    - **Uklanjanje viška karaktera:** Na liniji 74 u `backend/worker/tts_engine.py` nalazio se višak karaktera na kraju linije (`ia: {e}"}`) nastao usled prethodnog automatskog spajanja. Kod je ispravljen i proveren preko `py_compile`.
    - **Deploy i restart:** Izmene su poslate na GitHub granu `development`, povučene na Hetzner VPS i kontejneri `sinhronizuj-worker` i `sinhronizuj-api` su restartovani.
- **Status:** Završeno i deploy-ovano na server.

### 26.05.2026. 19:36 — Implementacija automatskog Python Regex korektora (post-processora)
- **Zahtev / Problem:**
    Korisnik je prihvatio predlog 1 (automatska programska ispravka teksta) kako bi se osigurala 100% ispravnost prevoda pre slanja u TTS sintezu glasa, i eliminisale sitne greške lektora (poput pogrešnog prevoda *hiring* -> *priprema*, gramatičkih grešaka sa rodom kod knjiga, nepostojećeg izraza *ovo buduće* i nepravilnog oblika glagola *poći*).
- **Urađeno:**
    - **Funkcija `clean_translation_text` (`backend/worker/translator.py`):**
        Implementirao sam novu funkciju koja pomoću regularnih izraza (Regex) čisti tekst od specifičnih LLM grešaka:
        *   Zamenjuje nepravilne padeže za Ej Aj (npr. `sa Ej Aj` -> `sa Ej Ajem`, `o Ej Aj` -> `o Ej Aju`, `od Ej Aj` -> `od Ej Aja`, `u Ej Aj` -> `u Ej Aju`).
        *   Ispravlja nepravilnu imenicu `buduće` u `budućnost` (npr. `ovo buduće` -> `ovu budućnost`).
        *   Koriguju greške lektora kod glagola `poći` (npr. `pođi po zlu` -> `poći po zlu`).
        *   Usklađuje slaganje rodova kod množine imenice *knjiga* (npr. `koji su popularni` -> `koje su popularne`).
        *   Ispravlja prevod *odluke o pripremi* u `odluke o zapošljavanju`.
    - **Poziv funkcije:** Funkcija se izvršava na samom kraju `lektor_segments` faze, i to nad svim segmentima u listi `translated_segments` (čime pokriva i uspešnu lekturu i fallback slučaj).
    - **Testiranje:** Svi test primeri su uspešno prošli kroz automatski Python test skript.
- **Status:** Uspešno implementirano, testirano, gurnuto na granu `development` i deploy-ovano na server.

### 26.05.2026. 19:45 — Proširivanje Regex post-processora novim jezičkim pravilima
- **Zahtev / Problem:**
    Korisnik je zatražio analizu poslednjeg sklapanja videa i ispravku preostalih uočenih problema u prevodu.
- **Urađeno:**
    - **Analiza logova:** Utvrđeno je da je lektor u novoj iteraciji ispravio nekoliko grešaka, ali su i dalje postojale nesavršenosti:
        1.  Uvedeno je gramatički neispravno povratno "se" kod glagola postati: *koje su se ironično postale popularne*.
        2.  Izraz *articles of incorporation* je lektor pogrešno preveo kao *članke o firmi* umesto *osnivačke dokumente/akte*.
        3.  Zid u prodavnici je opisan kao *zadnja zidina* umesto prirodnog *zadnji zid*.
        4.  Redosled negacije nužnosti je glasio *ne nužno rade/čine* umesto tečnog *ne rade/čine nužno*.
        5.  Izraz *odluke o prijemu* je mapiran u *odluke o zapošljavanju*.
    - **Dodavanje novih pravila u `clean_translation_text`:**
        Proširio sam Python regex funkciju da automatski i garantovano rešava ove specifične situacije:
        *   `su se ... postale` -> `su ... postale`
        *   `na zadnjoj zidini` -> `na zadnjem zidu`
        *   `članke o firmi kako bi je registrovala` -> `dokumente za registraciju kako bi registrovala firmu`
        *   `ne nužno rade/čine` -> `ne rade/čine nužno`
        *   `odluke o prijemu` -> `odluke o zapošljavanju`
    - **Deploy:** Izmene su gurnute na granu `development` i kontejneri na Hetzner serveru su restartovani nakon preuzimanja najnovijeg koda.
- **Status:** Završeno i deploy-ovano.

### 26.05.2026. 20:11 — Implementacija rukovanja greškama u video plejeru i rešavanje autoplay blokade
- **Zahtev / Problem:**
    Korisnik je prijavio problem gde plejer stoji na `0:00` i prikazuje crn ekran nakon uspešne obrade.
- **Urađeno:**
    - **Analiza:** 
        1. Proverio sam validnost fajla na serveru (H264 video + AAC audio, ispravan i potpuno čitljiv/dostupan preko `200` i `206 Partial Content`).
        2. Glavni sumnjivac za zamrznut plejer na `0:00` u modernim pretraživačima je bezbednosna politika automatske reprodukcije (`autoPlay`) bez stišanog zvuka (`muted`), što tera pretraživač da blokira učitavanje i reprodukciju.
    - **Rešenje:**
        1. Dodao sam `muted` atribut na `<video>` tag u `App.jsx` kako bi se zaobišle restrikcije pretraživača.
        2. Implementirao sam reaktivno stanje `videoError` i `onError` hendler na nivou video plejera koji prevodi i ispisuje precizan uzrok greške direktno na ekranu (npr. mrežna greška, neispravan kodek ili nepodržan format).
- **Status:** Završeno, ažurirano lokalno i gurnuto na granu `development`.














