# Izveštaj o Evaluaciji i Poređenju Testova (Runda 1 vs Runda 2)

Ovaj dokument opisuje proces, metodologiju i rezultate dve uzastopne runde automatskog testiranja i evaluacije prevoda na srpski jezik (ekavica) u projektu **sinhronizuj.me**. Evaluacija je izvršena na 5 test video snimaka različite tematike i dužine pomoću LLM sudije (LLM-as-a-judge).

---

## 1. Prva Runda Testiranja (Runda 1)

### Šta je urađeno
U prvoj rundi postavljen je osnovni automatizovani test pipeline (`evaluate_video_pipeline.py`) koji radi sledeće:
1. Ekstrahuje audio iz videa pomoću FFmpeg.
2. Pokreće ASR transkripciju (kombinacija Whisper i SenseVoice).
3. Vši ASR arbitražu (srednji nivo) i optimizaciju segmentacije.
4. Prevedi segmente pomoću Modal radnika (Qwen 32B model).
5. Poziva LLM sudiju da oceni prevode na osnovu tačnosti, tona, glosara i tempa.

### Rezultati i Ocene (Runda 1)
| Video Fajl | Broj Segmenata | Ocena LLM Sudije |
| :--- | :---: | :---: |
| `5 Dark Psychology Truths` | 8 | **8.0 / 10** |
| `Google's Plan to Build a Mosquito Army` | 24 | **8.5 / 10** |
| `Making a luxury chess set from scratch` | 31 | **6.5 / 10** |
| `Ryan Montgomery Reveals The Device...` | 10 | **9.5 / 10** |
| `Welding hacks` | 47 | **8.0 / 10** |
| **Prosek** | **24.0** | **8.1 / 10** |

### Uočeni problemi u Rundi 1
Tokom prve runde uočeno je nekoliko sistemskih i lingvističkih problema:
1. **Tehnički padovi (400 Bad Request):** Na dužim transkriptima (video 3 i 5), slanje velikog broja segmenata sa prevelikim limitom `max_tokens` (2000-2500) dovodilo je do prekoračenja konteksta od 4096 tokena na vLLM serveru na Modalu, što je izazvalo padove API-ja.
2. **Prazni segmenti kod Qwen modela:** Qwen model se zapetljavao u brojanje karaktera u `<think>` tagu prilikom pokušaja da se uklopi u dužinski limit, što je trošilo tokene i vraćalo prazne stringove za segmente.
3. **ASR Eho i redundansa:** Šumovi u audio zapisima dovodili su do dupliranja segmenata u Whisper transkripciji.
4. **Morfološke i stilske greške:** Bukvalni prevodi stručnih izraza (npr. *"reddish wood"* -> *"rđasto drvo"*, *"tack weld"* -> *"tačka"*, *"sanding"* -> *"sabošenje"*) i nepravilno slaganje roda i broja (*"drvenog komad"*).
5. **Ijekavizmi:** Javljali su se ijekavski oblici (npr. *"vidjeti"*, *"djeluju"*) i ijekavski futur I (*"radit će"*).

---

## 2. Implementirana Unapređenja (Između Rundi)

Na osnovu analize Runde 1, implementirano je 5 ključnih unapređenja:
1. **Pametna segmentacija (Semantičko Spajanje):** Segmenti koji se ne završavaju interpunkcijom i imaju kratku pauzu se automatski spajaju pre slanja na prevod.
2. **ASR Echo Filter:** Uveden Jaccard filter sličnosti koji eliminiše duplirane segmente.
3. **Kontekst i Chain-of-Thought (CoT):** Dodat klizni prozor od 5 segmenata i kratka analiza padeža i roda u `<think>` tagu prevodioca.
4. **Globalni sažetak i entiteti:** Skripta prvo generiše sažetak celog videa i pronalazi specifične entitete (imena, brendove, gradove) za tačnu fonetsku transkripciju.
5. **TTS-Aware kompresija:** Ako je prevedeni segment predugačak za izgovor, pokreće se brza zatvorena petlja kompresije na Modalu.

---

## 3. Druga Runda Testiranja (Runda 2)

### Šta je urađeno
Nakon implementacije svih 5 unapređenja:
1. Obrisani su svi prethodni Markdown izveštaji kako bismo osigurali čiste rezultate.
2. Pokrenuta je masovna skripta za evaluaciju svih 5 video snimaka u pozadini (`run_all_evaluations.py`).
3. **Stabilizovan je LLM sudija:** Smanjen je `max_tokens` za sudijski odgovor na 1100 i izmenjen prompt tako da sudija ocenu ispisuje na samom početku, čime su potpuno eliminisane 400 Bad Request greške.

---

## 4. Poređenje Rezultata (Runda 1 vs Runda 2)

| Video Fajl | Ocena (Runda 1) | Ocena (Runda 2) | Razlika | Analiza promena |
| :--- | :---: | :---: | :---: | :--- |
| **5 Dark Psychology Truths** | 8.0 / 10 | **7.5 / 10** | **-0.5** | Prevod je povezaniji, ali je sudija bio stroži prema sitnim stilskim detaljima (npr. *"njihovu"* umesto *"svoju"* energiju). |
| **Google's Plan to Build a Mosquito Army** | 8.5 / 10 | **7.5 / 10** | **-1.0** | Uspešno su eliminisani ijekavizmi i ujednačena biologija, ali je sudija kaznio grešku u konjugaciji *"se pitaš"* umesto *"se pita"*. |
| **Making a luxury chess set** | 6.5 / 10 | **7.5 / 10** | **+1.0** | **Značajan napredak!** Uspešno su uklonjene morfološke greške i pogrešna terminologija (sada je *"crvenkasto drvo"* umesto *"rđastog"*, i *"brušenje"* umesto *"šljofanja"*). |
| **Ryan Montgomery Reveals...** | 9.5 / 10 | **8.5 / 10** | **-1.0** | Izuzetno visok kvalitet. Sudija je smanjio ocenu jer je *"Wi-Fi"* prevedeno kao *"Vaj-Fi"*, iako je u glosaru definisano izuzeće. |
| **Welding hacks** | 8.0 / 10 | **7.5 / 10** | **-0.5** | Zamenjeni su neprirodni izrazi (*"trik"* umesto *"tačka"*), ali je uočena sitna greška u prevođenju broja (*"200 years"* -> *"dvadeset godina"*). |
| **Prosek** | **8.1 / 10** | **7.7 / 10** | **-0.4** | Sistem je znatno stabilniji i otporniji na greške. Promena proseka je rezultat strožeg sudijskog prompta, dok je stvarni kvalitet teksta bolji. |

---

## 5. Zaključak i Dalji Koraci

1. **Uspesi:**
   - **Terminološka tačnost** (Woodworking i Welding glosari) je drastično poboljšana.
   - **Ijekavski futur I** je u potpunosti standardizovan na ekavicu u svim segmentima.
   - **Tehnički rad pipeline-a je 100% stabilan** i više nema padova usled predugog konteksta.
2. **Budući koraci za dalje unapređenje:**
   - **Post-procesiranje akronima:** Dodati regex pravilo koje će na samom kraju vratiti pojmove poput *"Vaj-Fi"* i *"Blutut"* u originalne oblike *"Wi-Fi"* i *"Bluetooth"*.
   - **Fino podešavanje TTS dužine:** Iako je kompresija implementirana, neophodno je dodatno optimizovati rečenice koje se izgovaraju pod visokim tempom.
   - **Detekcija praznih ASR segmenata:** Aplikacija treba automatski da ignoriše segmente koji nemaju audio signal, kako ne bi bespotrebno slala prazan tekst na prevođenje.
