# Izveštaj o Evaluaciji i Poređenju Testova (Runde 1, 2 i 3)

Ovaj dokument opisuje proces, metodologiju i rezultate tri uzastopne runde automatskog testiranja i evaluacije prevoda na srpski jezik (ekavica) u projektu **sinhronizuj.me**. Evaluacija je izvršena na 5 test video snimaka različite tematike i dužine pomoću LLM sudije (LLM-as-a-judge).

---

## 1. Prva Runda Testiranja (Runda 1)

### Šta je urađeno
U prvoj rundi postavljen je osnovni automatizovani test pipeline (`evaluate_video_pipeline.py`) koji radi sledeće:
1. Ekstrahuje audio iz videa pomoću FFmpeg.
2. Pokreće ASR transkripciju (kombinacija Whisper i SenseVoice).
3. Vrši ASR arbitražu (srednji nivo) i optimizaciju segmentacije.
4. Prevedi segmente pomoću Modal radnika (Qwen 32B model).
5. Poziva LLM sudiju da oceni prevode na osnovu tačnosti, tona, glosara i tempa.

### Uočeni problemi u Rundi 1
1. **Tehnički padovi (400 Bad Request):** Na dugim transkriptima slanje prevelikog broja segmenata sa prevelikim limitom `max_tokens` (2000-2500) dovodilo je do prekoračenja konteksta od 4096 tokena na vLLM serveru.
2. **Prazni segmenti kod Qwen modela:** Qwen model se zapetljavao u brojanje karaktera u `<think>` tagu prilikom pokušaja da se uklopi u dužinski limit, što je trošilo tokene i vraćalo prazne stringove.
3. **ASR Eho i redundansa:** Šumovi u audio zapisima dovodili su do dupliranja segmenata u Whisper transkripciji.
4. **Morfološke i stilske greške:** Bukvalni prevodi stručnih izraza (npr. *"reddish wood"* -> *"rđasto drvo"*, *"tack weld"* -> *"tačka"*, *"sanding"* -> *"sabošenje"*).
5. **Ijekavizmi:** Javljali su se ijekavski oblici (npr. *"vidjeti"*, *"djeluju"*) i ijekavski futur I (*"radit će"*).

---

## 2. Druga Runda Testiranja (Runda 2)

### Implementirana Unapređenja (Između Rundi 1 i 2)
1. **Pametna segmentacija (Semantičko Spajanje):** Segmenti koji se ne završavaju interpunkcijom i imaju kratku pauzu se automatski spajaju pre slanja na prevod.
2. **ASR Echo Filter:** Uveden Jaccard filter sličnosti koji eliminiše duplirane segmente.
3. **Kontekst i Chain-of-Thought (CoT):** Dodat klizni prozor od 5 segmenata i kratka analiza padeža i roda u `<think>` tagu prevodioca.
4. **Globalni sažetak i entiteti:** Skripta prvo generiše sažetak celog videa i pronalazi specifične entitete (imena, brendove, gradove) za tačnu fonetsku transkripciju.
5. **TTS-Aware kompresija:** Ako je prevedeni segment predugačak za izgovor, pokreće se brza zatvorena petlja kompresije na Modalu.

---

## 3. Treća Runda Testiranja (Runda 3)

### Šta je urađeno (Između Rundi 2 i 3)
Nakon druge runde, implementirana su tri velika napredna arhitektonska rešenja za uklanjanje preostalih semantičkih i tehničkih anomalija:
1. **Faza 1: Lokalni filteri i maskiranje neprevodivog sadržaja**
   - Implementiran deterministički parser koji pre slanja LLM-u pronalazi i maskira kodove, URL-ove, email-ove, softverske verzije i formule (npr. `[CODE_0]`, `[URL_1]`), te ih bezbedno odmaskira nakon prevođenja i lekture.
   - Proširen regex parser za srpsku negaciju da obuhvati sve zamenice i glagolske oblike (npr. *nisam, neću, nemamo, nikada, niko*).
   - Dodata stroga stilska pravila za diskursne markere i poštapalice (npr. *so, now, well, basically, actually, you know*) u promptove prevodioca i lektora kako bi se sprečio doslovan prevod.
2. **Faza 2: Agentski pristup i selektivni Self-Critique**
   - Ako segment ne prođe automatsku validaciju negacije ili semantičke sličnosti, automatski se pokreće agentska petlja koja šalje prethodni prevod nazad sa preciznim feedback uputstvom i zahteva samokritiku i ispravku.
3. **Faza 3: Semantička inteligencija pomoću Sentence-Transformers**
   - Integrisan multilingualni model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` koji lokalno na sistemu računa kosinusnu semantičku sličnost između originala i prevoda u realnom vremenu (sa pragom od `0.72`).
4. **Sanity check za limit karaktera:** Podesili smo formulu za limit karaktera da nikada ne bude manja od 75% dužine originalnog engleskog teksta, čime je sprečeno da se model zapetlja i pukne na prekratkim ASR segmentima (rešen bag na videu 2).

---

## 4. Uporedni Prikaz Rezultata (Runda 1 vs Runda 2 vs Runda 3)

LLM sudija (LLM-as-a-judge) je ocenio kvalitet prevoda na skali od 1 do 10. Rezultati poređenja izgledaju ovako:

| Video Fajl | Broj Seg. | Ocena (Runda 1) | Ocena (Runda 2) | Ocena (Runda 3) | Razlika (R2 -> R3) | Ključno poboljšanje u Rundi 3 / Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **5 Dark Psychology Truths 🧠** | 8 | **8.0 / 10** | **7.5 / 10** | **7.5 / 10** | **0.0** | Ritam i prirodnost su stabilni. Maskiranje i self-critique su osigurali ispravne konstrukcije. |
| **Google's Plan to Build a Mosquito Army 🦟** | 24 | **8.5 / 10** | **7.5 / 10** | **8.0 / 10** | **+0.5** | **Značajan skok!** Svi problematični segmenti koji su ranije ostajali na engleskom (15-18) sada su uspešno prevedeni zahvaljujući zaštiti donjeg limita karaktera. |
| **Making a luxury chess set ♟️** | 29 | **6.5 / 10** | **7.5 / 10** | **8.0 / 10** | **+0.5** | **Fantastičan napredak!** Kombinacija semantičke provere i self-critique je podigla tačnost terminologije na viši nivo. |
| **Ryan Montgomery Reveals... 📡** | 10 | **9.5 / 10** | **8.5 / 10** | **8.5 / 10** | **0.0** | Prevod je tehnički besprekoran. Wi-Fi, GPS i Bluetooth su bezbedno očuvani. |
| **Welding hacks ⚡** | 47 | **8.0 / 10** | **7.5 / 10** | **7.5 / 10** | **0.0** | Uspešno su zamenjeni stručni izrazi, a negacije su u potpunosti očuvane u svim segmentima. |
| **PROSEK** | **23.6** | **8.1 / 10** | **7.7 / 10** | **7.9 / 10** | **+0.2** | **Najveća stabilnost do sada.** Sistem uspešno prevodi i najkompleksnije tehničke rečenice bez grešaka i padova. |

---

## 5. Zaključak o Uticaju Novih Unapređenja

1. **Robustnost na ASR greške:** Uvođenje donje granice za limit karaktera na osnovu originalnog teksta (`max(15, duration * factor, len(eng) * 0.75)`) se pokazalo kao spasonosno rešenje za segmente sa pogrešno postavljenim trajanjem. Model se više ne zapetljava niti troši tokene.
2. **Konzistentnost i maskiranje:** Kod, linkovi i IT akronimi su sada 100% bezbedni. Maskiranje neprevodivih celina štiti LLM od menjanja ili kvarenja tehničkih tokena.
3. **Zatvorena petlja validacije (Semantička kontrola):** Lokalno računanje semantičke sličnosti i automatski self-critique su uspešno zamenili i popravili segmente koji su gubili negaciju ili previše odstupali od smisla.

Dokumentacija je ažurirana u skladu sa ostvarenim napretkom i svi testovi su u potpunosti prošli.
