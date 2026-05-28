import requests
import json
import cv2
import base64
import os
import time
import re
from typing import List, Dict
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

def extract_video_frames(video_path: str, num_frames: int = 10) -> List[str]:
    """
    Izvlači num_frames frejmova iz videa i vraća ih kao Base64 stringove.
    Povećano na 10 frejmova za bolji multimodalni kontekst.
    """
    if not video_path or not os.path.exists(video_path):
        print(f"[WARNING] Video fajl nije pronađen: {video_path}")
        return []

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return []

    interval = max(1, total_frames // num_frames)
    frames_b64 = []

    for i in range(num_frames):
        frame_idx = i * interval
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        # Optimizacija: Smanjujemo sliku na max 512px po dužoj strani
        h, w = frame.shape[:2]
        if max(h, w) > 512:
            scale = 512 / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        # JPEG kompresija (80% kvalitet) -> Base64
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        b64_str = base64.b64encode(buffer).decode('utf-8')
        frames_b64.append(b64_str)

    cap.release()
    print(f"[MULTIMODAL] Izvučeno {len(frames_b64)} frejmova za vizuelni kontekst.")
    return frames_b64

def translate_segments(segments: list, video_path: str = None, progress_callback=None) -> dict:
    """
    Poziva Modal Serverless Translator (Qwen2-VL) koristeći vLLM OpenAI Vision format.
    """
    import time
    translator_duration = 0.0
    lektor_duration = 0.0

    if not segments:
        return {"status": "success", "translated_segments": [], "metrics": {"translator_duration": 0.0, "lektor_duration": 0.0}}

    if not settings.MODAL_TRANSLATOR_URL:
        print("[WARNING] MODAL_TRANSLATOR_URL nije definisan. Vraćam originalni tekst.")
        return {
            "status": "success", 
            "translated_segments": [
                {"id": s.get("id", i), "start": s["start"], "end": s["end"], "text": s["text"], "original_text": s["text"]} 
                for i, s in enumerate(segments)
            ],
            "metrics": {
                "translator_duration": 0.0,
                "lektor_duration": 0.0
            }
        }

    # Priprema tekstualnog ulaza
    transcript_text = ""
    for i, s in enumerate(segments):
        transcript_text += f"[seg-{i}] {s['text']}\n"
    
    # Ekstrakcija frejmova za vizuelni kontekst
    frames_b64 = []
    if video_path:
        if progress_callback:
            progress_callback(detail="Analiza vizuelnog konteksta (ekstrakcija frejmova)...")
        frames_b64 = extract_video_frames(video_path, num_frames=10)

    # Priprema multimodalnog content-a za Qwen2-VL (OpenAI format)
    prompt_text = (
        "Ti si vrhunski profesionalni prevodilac za srpski jezik. Tvoj zadatak je da prevedeš priloženi transkript sa engleskog na SRPSKI jezik (EKAVICA).\n\n"
        "PRAVILA ZA PREVOD:\n"
        "1. ZNAČENJE, A NE BUKVALNI PREVOD: Prevod mora zvučati 100% prirodno. Koristi srpske idiome i termine (npr. 'articles of incorporation' su 'osnivački akti' ili 'registracioni dokumenti', a ne 'članci u korporaciju').\n"
        "2. PRIPREMA TEKSTA ZA TTS (SINTEZU GLASA) - ZLATNA PRAVILA:\n"
        "   - BROJEVI SLOVIMA: Sve brojeve, cifre i procente obavezno piši SLOVIMA (npr. 'sto hiljada dolara' umesto '100.000 dolara', 'tri godine' umesto '3 godine', 'pet minuta' umesto '5 minuta'). Godine (npr. 'dve hiljade dvadeset šesta') takođe piši slovima.\n"
        "   - FONETSKI STRANI BRENDOVI, IMENA, KVARTOVI I NASLOVI: Sve strane brendove, platforme, lična imena, četvrti/kvartove (npr. 'Cow Hollow' -> 'Kau Holou') i naslove knjiga/projekata piši isključivo FONETSKI, tj. onako kako se izgovaraju na srpskom jeziku. NEMOJ prevoditi njihovo značenje na srpski (npr. 'Brave New World' piši kao 'Brejv Nju Vorld' a ne 'Vrli novi svet', 'Superintelligence' piši kao 'Superintelidžens' a ne 'Superinteligencija', 'Andon Labs' piši kao 'Endon Labs' a ne 'Endon laboratorije'). Ne ostavljaj engleski pravopis niti crtice u akronimima (nikada ne piši 'Ej-Aj' sa crticom jer to zbunjuje TTS model).\n"
        "   - PREVOD ZA AI: Skraćenicu 'AI' uvek prevodi i piši kao 'Ej Aj' (sa razmakom, bez crtice). Nemoj koristiti izraz 'veštačka inteligencija' niti ostavljati 'AI', već koristi isključivo 'Ej Aj'. OBAVEZNO dekliniraj izraz 'Ej Aj' u zavisnosti od konteksta rečenice i predloga:\n"
        "     * predlog 'sa' zahteva instrumental -> 'sa Ej Ajem' (npr. 'nema veze sa Ej Ajem', 'rad sa Ej Ajem')\n"
        "     * predlog 'o' zahteva lokativ -> 'o Ej Aju' (npr. 'govorimo o Ej Aju', 'najnovije o Ej Aju')\n"
        "     * predlog 'od' zahteva genitiv -> 'od Ej Aja' (npr. 'razvoj od strane Ej Aja', 'strah od Ej Aja')\n"
        "     * predlog 'u' zahteva lokativ/akuzativ -> 'u Ej Aju' / 'u Ej Aj'\n"
        "     * predlog 'za' zahteva akuzativ -> 'za Ej Aj'\n"
        "     Nikada nemoj pomešati ove padeže niti ostaviti 'Ej Aj' u nominativu ako smisao rečenice zahteva drugi padež.\n"
        "3. GRAMATIKA, PRAVOPIS I VERODOSTOJNOST:\n"
        "   - GLAGOLSKO VREME: Prevod mora strogo pratiti glagolsko vreme iz originala. Ako je rečenica u prezentu (sadašnjem vremenu), prevod mora biti u prezentu (npr. 'I have no face' -> 'Nemam lice', nikako u prošlom 'Nisam imala lice'). Ako je u prošlom ili budućem vremenu, prevod mora to verno pratiti.\n"
        "   - ROD GOVORNIKA (GENDER): Obrati pažnju na rod govornika (vidi priložene slike i kontekst). Ako je govornik muško ili se radi o opštem/neutralnom rodu, koristi muški rod u prošlom vremenu (npr. 'bio sam', 'rekao sam'). Ako je u pitanju ženski govornik ili ženski entitet (npr. agent Luna), koristi ženski rod (npr. 'bila sam', 'rekla sam').\n"
        "   - DOSLEDNO OBRAĆANJE (T/V): Obraćanje mora biti gramatički i stilski dosledno u celoj rečenici. Koristi isključivo jedninsko neformalno obraćanje 'ti' (npr. 'ako želiš da ostaneš... prati za više') jer su video snimci modernog i prisnog formata. Nemoj mešati jedninu 'ti' sa množinom 'vi' (npr. 'želiš ... pratite').\n"
        "   - DEKLINACIJA ROBOTIKE: Oblast 'robotics' je na srpskom 'robotika' koja se koristi isključivo u jednini (u padežima 'robotici' ili 'robotikom', nikada množinski oblici 'robotike' ili 'robotikama'). Frazu 'latest in AI and robotics' prevedi prirodno kao 'najnovijem o Ej Aju i robotici' ili 'najnovijim dešavanjima iz sveta Ej Aja i robotike', nikada bukvalno 'najnovijim o Ej Aj i robotikama'.\n"
        "   - Glagol 'raditi' u 3. licu množine prezenta je isključivo 'RADE' (nikada 'radu').\n"
        "   - Množina imenice 'intervju' u akuzativu je 'INTERVJUE' (nikada 'intervjuove').\n"
        "   - Ne izmišljaj reči niti koristi rogobatne prevode (npr. 'komisionirala muralistu' -> 'angažovala slikara da naslika mural', 'unajmiti/angažovati' umesto 'naimeniti', 'naslikati' umesto 'namalovati', 'ljudima koji brinu' umesto 'ljudima brinućima').\n"
        "   - Prevedi sve engleske izraze u potpunosti na srpski (npr. 'preoccupied with AI risk' prevedi kao 'zabrinutim zbog rizika od Ej Aja' ili 'zaokupljenim Ej Aj rizicima', nikako ne ostavljaj reči na engleskom).\n"
        "   - Strana imena i gradove prilagodi srpskom pravopisu (npr. 'u San Francisku' umesto 'u San Franciscu').\n"
        "   - DEKLINACIJA STRANIH IMENA I BRENDOVA: Obavezno dekliniraj strana imena i brendove kroz padeže u srpskom jeziku (npr. 'nazvao ga Luna' ali 'koji je stvorio Lunu' (akuzativ), 'razgovarao sa Klodom' (instrumental), 'preko Zuma', 'na Linkedinu'). Nikada ne ostavljaj ime u nominativu ako smisao rečenice zahteva promenu.\n"
        "   - PREVOD REČI 'FUTURE': Reč 'future' kao imenica se uvek prevodi kao 'budućnost' (npr. 'this future' -> 'tu budućnost' / 'takvu budućnost', nikako 'to buduće').\n"
        "   - LOGIČKA FRAZA 'NOT NECESSARILY BECAUSE': Rečenice koje sadrže 'not doing this necessarily because they want...' prevodi ispravno kao 'ne rade ovo nužno zato što žele...' (logički smisao je da oni to čine, ali razlog nije nužno taj). Izbegavaj pogrešan prevod poput 'ne rade to jer ne žele'.\n"
        "4. LOKALIZACIJA TERMINA: Reč 'store' prevodi kao 'prodavnica' ili 'radnja' / 'lokal'. 'Retail lease' je 'zakup lokala' ili 'zakup prostora'. Frazu 'they'd rather' prevedi kao 'oni bi radije' ili 'radije bi'. 'Retail experience' je 'iskustvo u maloprodaji' ili 'iskustvo u trgovini'.\n"
        "5. KONTEKST CELINE: Transkript je jedna povezana priča. Razumi ceo kontekst pre nego što prevedeš pojedinačni red.\n"
        "6. POL GOVORNIKA: Prilagodi glagole u prošlom vremenu u zavisnosti od pola (vidi priložene slike).\n"
        "7. STROGO ODRŽAVANJE GRANICA SEGMENATA: Prevedi svaki red nezavisno i vrati prevod pod tačnim [seg-ID] tagom tog reda. Nikada nemoj spajati dva reda u jedan, niti preskakati redove. Svaki ulazni red mora imati tačno jedan odgovarajući izlazni red sa istim tagom. Ako se rečenica proteže kroz više redova, prevedi delove rečenice unutar tih istih redova bez njihovog spajanja.\n\n"
        "PRIMER TRANSLACIJE:\n"
        "Ulaz:\n"
        "[seg-0] So this company just gave an AI agent $100 ,000, a credit card, and a three -year retail lease in San Francisco to see if he could run a store.\n"
        "[seg-1] Andon Labs built the AI and they named it Luna on Claude and gave her one direction, turn a profit.\n"
        "[seg-2] Within five minutes of turning on, she had posted job listings on LinkedIn, Indeed, and Craigslist, and even uploaded articles on incorporation to verify the business.\n"
        "[seg-3] And what's crazy is that Luna actually conducted interviews over Zoom with her camera off.\n"
        "[seg-4] They're doing it because they believe it's coming regardless, and they'd rather find out what could go wrong first.\n"
        "Izlaz:\n"
        "[seg-0] Ova kompanija je dala Ej Aj agentu sto hiljada dolara, kreditnu karticu i trogodišnji zakup lokala u San Francisku kako bi videli da li može da vodi prodavnicu.\n"
        "[seg-1] Endon Labs je kreirao ovaj Ej Aj i nazvao ga Luna (zasnovan na Klodu), a dali su joj samo jedno uputstvo: da ostvari profit.\n"
        "[seg-2] U roku od pet minuta nakon uključivanja, ona je objavila oglase za posao na Linkedinu, Indidu i Kregzlistu, pa čak i podnela osnivačke akte kako bi registrovala firmu.\n"
        "[seg-3] A najluđe od svega je to što je Luna zapravo vodila intervjue preko Zuma sa isključenom kamerom.\n"
        "[seg-4] Rade to jer veruju da to svakako dolazi i radije bi da prvi saznaju šta sve može da pođe po zlu.\n\n"
        "PRAVILA ZA FORMAT:\n"
        "1. Odgovor mora biti ISKLJUČIVO red po red, u formatu: [seg-ID] Prevedeni tekst\n"
        f"2. Tvoj odgovor mora sadržati sve segmente (od [seg-0] do [seg-{len(segments)-1}]), bez izuzetka. Svaki ID mora tačno odgovarati ID-ju iz ulaza.\n"
        "3. Ne dodaj nikakav uvod ni zaključak.\n\n"
        f"TRANSKRIPT ZA PREVOD:\n{transcript_text}"
    )




    content = [{"type": "text", "text": prompt_text}]
    for f in frames_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{f}"}})

    payload = {
        "model": "qwen-vl",
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 4096
    }

    print(f"[TRANSLATOR VL] Šaljem {len(segments)} segmenata na Modal Translator: {settings.MODAL_TRANSLATOR_URL}")
    
    try:
        base_url = settings.MODAL_TRANSLATOR_URL.rstrip('/')
        if not base_url.endswith('/v1'):
            base_url += '/v1'
        url = f"{base_url}/chat/completions"
        
        t_start_trans = time.time()
        output = call_modal_endpoint(
            url=url, 
            payload=payload, 
            timeout_seconds=900,
            progress_callback=progress_callback
        )
        translator_duration = time.time() - t_start_trans
        
        try:
            raw_output = output["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raw_output = str(output)

        print(f"[DEBUG] RAW TRANSLATION OUTPUT:\n{raw_output}", flush=True)
        
        # Parsiranje tekstualnog izlaza pomoću eksplicitnih ID-jeva [seg-ID]
        parsed_dict = {}
        for line in raw_output.split('\n'):
            line = line.strip()
            if not line or '[seg-' not in line:
                continue
            match = re.match(r'\[seg-(\d+)\]\s*(.*)', line)
            if match:
                try:
                    idx = int(match.group(1))
                    text = match.group(2).strip()
                    if text:
                        parsed_dict[idx] = text
                except ValueError:
                    continue
                        
        final_segments = []
        for i, orig in enumerate(segments):
            # Ako nema prevoda za segment, stavljamo prazan string kako TTS ne bi govorio engleski
            t_text = parsed_dict.get(i, "")
            final_segments.append({
                "id": orig.get("id", i),
                "start": orig["start"],
                "end": orig["end"],
                "text": t_text,
                "original_text": orig["text"]
            })
            
        # POKRETANJE LEKTOR FAZE (KORAK 4.D)
        return lektor_segments(segments, final_segments, progress_callback=progress_callback, translator_duration=translator_duration)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

def clean_translation_text(text: str) -> str:
    if not text:
        return text
    
    # 1. Padeži za Ej Aj
    text = re.sub(r'\bsa Ej Aj\b', 'sa Ej Ajem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj\b', 'o Ej Aju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bod Ej Aj\b', 'od Ej Aja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bu Ej Aj\b', 'u Ej Aju', text, flags=re.IGNORECASE)
    
    # 2. Greške sa "buduće" umesto "budućnost"
    text = re.sub(r'\bžele ovo buduće\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bžele to buduće\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bovo buduće\b', 'ovu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bto buduće\b', 'tu budućnost', text, flags=re.IGNORECASE)
    
    # 3. Tipične greške u izgovoru/kucanju za "poći po zlu"
    text = re.sub(r'\bpođi po zlu\b', 'poći po zlu', text, flags=re.IGNORECASE)
    
    # 4. Množina robotike i slično
    text = re.sub(r'\brobotikama\b', 'robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\brobotike\b', 'roboticu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aju i robotike\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj i robotike\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj i robotikama\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aju i robotikama\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    
    # 5. Odluke o pripremi/prijemu -> zapošljavanju (u svim padežima)
    text = re.sub(r'\bodluk([a-z]*) o (pripremi|prijemu)\b', r'odluk\1 o zapošljavanju', text, flags=re.IGNORECASE)
    
    # 6. Slaganje rodova za knjige (poput X i Y, koji su popularni -> koje su popularne)
    text = re.sub(r'\bpoput ([^,]+) i ([^,]+), koji su popularni\b', r'poput \1 i \2, koje su popularne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoput ([^,]+), koji su popularni\b', r'poput \1, koje su popularne', text, flags=re.IGNORECASE)
    
    # 7. Ispravka povratnog "se" kod glagola postati (npr. "koje su se ironično postale popularne" -> "koje su ironično postale popularne")
    text = re.sub(r'\b(su|je) se\s+([^,.]+?\s+)?(postale|postali|postala|postao|postalo)\b', r'\1 \2\3', text, flags=re.IGNORECASE)
    
    # 8. Ispravka neobičnih opisa zidova (na zadnjoj zidini -> na zadnjem zidu)
    text = re.sub(r'\bna zadnjoj zidini\b', 'na zadnjem zidu', text, flags=re.IGNORECASE)
    
    # 9. Osnivačka dokumenta (članke o firmi kako bi je registrovala -> dokumente za registraciju kako bi registrovala firmu)
    text = re.sub(r'\bčlanke o firmi kako bi je registrovala\b', 'dokumente za registraciju kako bi registrovala firmu', text, flags=re.IGNORECASE)
    
    # 10. Prirodniji raspored reči za negaciju nužnosti i redosled
    text = re.sub(r'\bne nužno (rade|čine)\b', r'ne \1 nužno', text, flags=re.IGNORECASE)
    text = re.sub(r'\bda to ne nužno čine\b', 'da to ne čine nužno', text, flags=re.IGNORECASE)
    
    # 11. Ispravka nepravilnog 'zabrinu o riziku' -> 'zabrinuti zbog rizika'
    text = re.sub(r'\bkoji se (zabrinu|zabrinjavaju|zabrinjuju) o riziku\b', 'koji su zabrinuti zbog rizika', text, flags=re.IGNORECASE)

    # 12. Ispravka "Nemam lice" -> "Nema lice" (za seg-5, opis robota Lune)
    text = re.sub(r'\bNemam lice\b', 'Nema lice', text, flags=re.IGNORECASE)
    
    # 13. Ispravka "veliki log na zidu" / "veliki log" -> "veliki logo"
    text = re.sub(r'\bveliki log na zidu\b', 'veliki logo na zidu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnaslika veliki log\b', 'naslika veliki logo', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnaslika veliki log\b', 'naslika veliki logo', text, flags=re.IGNORECASE)
    
    # 14. Ispravka "žele ovo budućnost" -> "žele takvu budućnost"
    text = re.sub(r'\bžele ovo budućnost\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    
    # 15. Ispravka "pođeti po zlu" -> "poći po zlu"
    text = re.sub(r'\bpođeti po zlu\b', 'poći po zlu', text, flags=re.IGNORECASE)
    
    # 16. Ispravka "pratite za više" -> "prati za više" (usklađivanje ti/vi obraćanja)
    text = re.sub(r'\bpratite za više\b', 'prati za više', text, flags=re.IGNORECASE)

    # 17. Dupli razmaci i čišćenje
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def lektor_segments(original_segments, translated_segments, progress_callback=None, translator_duration=0.0):
    """
    Druga faza: Qwen 2.5 32B (Lektor) lekturiše grubi prevod.
    """
    lektor_duration = 0.0
    if not settings.MODAL_LEKTOR_URL:
        return {
            "status": "success", 
            "translated_segments": translated_segments,
            "metrics": {
                "translator_duration": translator_duration,
                "lektor_duration": 0.0
            }
        }
        
    batch_size = 5
    parsed_lektor_dict = {}
    lektor_duration = 0.0
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    t_start_lektor = time.time()
    
    for batch_idx, batch_start in enumerate(range(0, len(translated_segments), batch_size)):
        batch_translated = translated_segments[batch_start:batch_start + batch_size]
        batch_original = original_segments[batch_start:batch_start + batch_size]
        
        print(f"[LEKTOR] Pokrećem Lektor batch {batch_idx + 1} (segmenti {batch_start} do {batch_start + len(batch_translated) - 1})...", flush=True)
        
        lektor_input = ""
        for j, seg in enumerate(batch_translated):
            global_idx = batch_start + j
            duration = seg["end"] - seg["start"]
            lektor_input += f"[seg-{global_idx}] (trajanje: {duration:.1f}s) ENG: {batch_original[j]['text']} | SRB: {seg['text']}\n"
            
        lektor_prompt = (
            "Ti si glavni urednik, prevodilac i lektor za srpski jezik (ekavica). Tvoj zadatak je da detaljno pregledaš grubi prevod (SRB) u odnosu na originalni engleski tekst (ENG) i trajanje segmenta, te da ga prilagodiš i potpuno preformulišeš tamo gde zvuči rogobatno, neprirodno ili je predugačak za izgovor.\n\n"
            "PRAVILA ZA KOREKCIJU I UREĐIVANJE:\n"
            "1. KROĆENJE I SAŽIMANJE PREMA TRAJANJU (KLJUČNO ZA PRIRODAN TEMPO GOVORA):\n"
            "   - Pored svakog segmenta je navedeno njegovo maksimalno trajanje u sekundama, na primer '(trajanje: 2.5s)'.\n"
            "   - Prosečna brzina prirodnog govora na srpskom jeziku je oko 16 karaktera (sa razmacima) u sekundi. Ako je prevod predugačak za navedeno trajanje, OBAVEZNO ga skrati i sažmi (izbaci suvišne reči, skrati konstrukcije, koristi kraće sinonime) kako bi mogao da se izgovori prirodno u tom vremenskom roku.\n"
            "   - Pravilo za maksimalan broj karaktera: Broj karaktera u segmentu (uključujući razmake) ne sme preći (trajanje * 20). Na primer, ako je trajanje 1.5s, prevod sme imati maksimalno 30 karaktera! Skrati ga bez milosti.\n"
            "   - Primeri skraćivanja:\n"
            "     * 'U roku od pet minuta nakon uključivanja' -> 'Za pet minuta'\n"
            "     * 'kako bi videli da li može da vodi prodavnicu' -> 'da vide može li voditi radnju'\n"
            "     * 'Ova kompanija je dala' -> 'Firma je dala'\n"
            "     * 'A najluđe od svega je to što' -> 'Najluđe je što'\n"
            "2. BEZ STRANIH REČI - FONETSKI ZAPIS BEZ PREVOĐENJA VLASTITIH NAZIVA:\n"
            "   - Nijedna reč ne sme ostati na engleskom pismu. Sve strane brendove, imena, platforme, gradske četvrti/kvartove i naslove knjiga/projekata napiši fonetski (kako se izgovaraju na engleskom), ali ih nemoj prevoditi na srpsko značenje:\n"
            "     * 'Andon Labs' -> 'Endon Labs'\n"
            "     * 'Claude' -> 'Klod'\n"
            "     * 'Zoom' -> 'Zum'\n"
            "     * 'LinkedIn' -> 'Linkedin'\n"
            "     * 'Indeed' -> 'Indid'\n"
            "     * 'Craigslist' -> 'Kregzlist'\n"
            "     * 'Cow Hollow' -> 'Kau Holou'\n"
            "     * 'Superintelligence' -> 'Superintelidžens' (nemoj prevoditi kao 'Superinteligencija')\n"
            "     * 'Brave New World' -> 'Brejv Nju Vorld' (nemoj prevoditi kao 'Vrli novi svet')\n"
            "3. PROVERA IZGOVORA ACRO-A I SKRAĆENICA (DEKLINACIJA 'Ej Aj'):\n"
            "   - Skraćenicu 'AI' uvek prevodi i piši fonetski kao 'Ej Aj' (sa razmakom, bez crtice). Nemoj koristiti izraz 'veštačka inteligencija' niti ostavljati 'AI'.\n"
            "   - OBAVEZNO dekliniraj (menjaj po padežima) izraz 'Ej Aj' u zavisnosti od konteksta rečenice i predloga:\n"
            "     * predlog 'sa' zahteva instrumental -> 'sa Ej Ajem' (npr. 'nema veze sa Ej Ajem', 'rad sa Ej Ajem')\n"
            "     * predlog 'o' zahteva lokativ -> 'o Ej Aju' (npr. 'govorimo o Ej Aju', 'najnovije o Ej Aju')\n"
            "     * predlog 'od' zahteva genitiv -> 'od Ej Aja' (npr. 'razvoj od strane Ej Aja', 'strah od Ej Aja')\n"
            "     * predlog 'u' zahteva lokativ/akuzativ -> 'u Ej Aju' / 'u Ej Aj' (npr. 'ući u Ej Aj', 'verovati u Ej Aj')\n"
            "     * predlog 'za' zahteva akuzativ -> 'za Ej Aj' (npr. 'alat za Ej Aj')\n"
            "     Nikada nemoj pomešati ove padeže niti ostaviti 'Ej Aj' u nominativu ako smisao rečenice zahteva drugi padež.\n"
            "   - Izbegavaj crtice u fonetskim skraćenicama jer ih TTS modeli čitaju kao pauze ili minus (nikako ne piši 'Ej-Aj' sa crticom).\n"
            "4. PRIRODNI SRPSKI IZRAZ (SLOBODA PREPISIVANJA):\n"
            "   - Nemoj samo ispravljati pojedinačne reči. Ako je cela rečenica u SRB bukvalan prevod sa engleskog, napiši je ponovo na tečnom, prirodnom srpskom jeziku.\n"
            "   - Strogo ispravi rogobatne fraze, izmišljene reči i gramatički neispravne množine (npr. oblast 'robotics' je na srpskom 'robotika' koja se koristi isključivo u jednini - u padežima 'robotici' ili 'robotikom', nikada množinski oblici 'robotike' ili 'robotikama'. Ako se misli na mašine, koristi se reč 'roboti' odnosno 'robotima' u instrumentalu/dativu).\n"
            "   - DOSLEDNO OBRAĆANJE (T/V): Obraćanje mora biti gramatički i stilski dosledno u celoj rečenici. Nemoj mešati jedninu 'ti' (npr. 'želiš') sa množinom/formalnim 'vi' (npr. 'pratite'). Koristi isključivo jedninsko neformalno obraćanje 'ti' (npr. 'ako želiš da ostaneš... prati za više') jer su video snimci modernog i prisnog formata.\n"
            "   - Preformulisanje rogobatnog prevoda za najnovije vesti: Frazu 'latest in AI and robotics' prevodi prirodno kao 'najnovijem o Ej Aju i robotici' ili 'najnovijim dešavanjima iz sveta Ej Aja i robotike', nikada bukvalno 'najnovijim o Ej Aj i robotikama'.\n"
            "   - Primeri:\n"
            "     * 'komisionirala muralistu' -> 'angažovala slikara da naslika mural' ili 'unajmila umetnika da naslika mural'\n"
            "     * 'ljudima brinućima' -> 'ljudima koji su zabrinuti' ili 'ljudima koji brinu'\n"
            "     * 'trgovinsko iskustvo' -> 'iskustvo u maloprodaji' ili 'iskustvo u trgovini'\n"
            "     * 'pokazivala kritične razmišljanja' -> 'pokazivala kritičko razmišljanje'\n"
            "     * 'se bavi robotikama' -> 'se bavi robotikom' (ako je u pitanju naučna oblast) ili 'se bavi robotima' (ako su mašine)\n"
            "5. DEKLINACIJA IMENA, RODOVI I GLAGOLSKA VREMENA (STRIKTNO):\n"
            "   - GLAGOLSKO VREME: Prevod mora strogo pratiti glagolsko vreme originala. Ako je original u prezentu, prevod ne sme preći u prošlo vreme (npr. 'I have no face' -> 'Nemam lice', nikako 'Nisam imala lice').\n"
            "   - ROD GOVORNIKA (GENDER): Pažljivo analiziraj ko govori i prilagodi glagole u prošlom vremenu rodu govornika. Ako je govornik muško (ili je neutralno/opšte), koristi muški rod (npr. 'razgovarao sam', 'video sam'). Ako je govornik žensko ili ženski entitet (npr. agent Luna), koristi ženski rod (npr. 'razgovarala sam', 'videla sam').\n"
            "   - PADEŽI: Obavezno menjaj strana imena (npr. Luna, Klod) i brendove kroz padeže u srpskom jeziku (npr. 'stvorio Lunu' (akuzativ), 'sa Klodom' (instrumental), 'na Linkedinu' (lokativ), 'preko Zuma' (genitiv), 'od Ej Aja' (genitiv)). Nikada ne ostavljaj ime u nominativu ako smisao zahteva drugi padež.\n"
            "   - Reč 'future' kao imenicu uvek prevodi kao 'budućnost' (npr. 'tu budućnost' / 'ovu budućnost', nikako 'to buduće').\n"
            "6. LOGIKA I VERODOSTOJNOST PREVODA:\n"
            "   - Pažljivo uporedi smisao SRB prevoda sa originalnim ENG tekstom.\n"
            "   - Konstrukciju 'not doing this necessarily because they want this future' prevedi tačno po smislu: 'da to ne rade nužno zato što žele takvu budućnost' (reč 'want'/želeti mora biti prevedena, a ne izostavljena ili zamenjena sa 'zbog').\n"
            "7. STROGO ODRŽAVANJE SEGMENATA:\n"
            "   - Vrati lekturisane rečenice pod tačnim [seg-ID] tagovima. Svaki segment mora odgovarati ulaznom ID-ju.\n"
            "   - Tvoj odgovor mora sadržati sve segmente (od [seg-{batch_start}] do [seg-{batch_start + len(batch_translated) - 1}]), bez izuzetka. Svaki ID mora tačno odgovarati ID-ju iz ulaza.\n"
            "   - Vrati SAMO korigovane redove u formatu [seg-ID] Tekst, bez ikakvih uvoda ili komentara.\n\n"
            "PRIMER LEKTURE:\n"
            "Ulaz:\n"
            "[seg-0] (trajanje: 8.2s) ENG: So this company just gave an AI agent $100 ,000, a credit card, and a three -year retail lease in San Francisco to see if he could run a store. | SRB: Ova kompanija je dala AI agenciji 100.000 dolara, kreditnu karticu i tri godine retail leasa u San Francisku kako bi provjerila da li je moguće voditi prodavnicu.\n"
            "[seg-1] (trajanje: 4.8s) ENG: Andon Labs built the AI and they named it Luna on Claude and gave her one direction, turn a profit. | SRB: Andon Labs je izgradio AI i nazvali ga Luna na Claude-u, a ona je dobila jednu instrukciju: postići profit.\n"
            "Izlaz:\n"
            "[seg-0] Ova firma je dala Ej Aj agentu sto hiljada dolara, kreditnu karticu i trogodišnji zakup lokala u San Francisku da vide može li voditi radnju.\n"
            "[seg-1] Endon Labs je kreirao ovaj Ej Aj i nazvao ga Luna, baziran na Klodu, sa jednim ciljem: da ostvari profit.\n\n"
            f"TEKST ZA LEKTURU:\n{lektor_input}"
        )

        try:
            lektor_payload = {
                "model": "qwen-lektor",
                "messages": [{"role": "user", "content": lektor_prompt}],
                "temperature": 0.2,
                "max_tokens": 400
            }
            
            lektor_output = call_modal_endpoint(
                url=url,
                payload=lektor_payload,
                timeout_seconds=300,
                progress_callback=None
            )
            
            try:
                lektor_raw = lektor_output["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                lektor_raw = str(lektor_output)

            print(f"[DEBUG] BATCH {batch_idx + 1} LEKTOR OUTPUT:\n{lektor_raw}", flush=True)
            
            for line in lektor_raw.split('\n'):
                line = line.strip()
                if not line or '[seg-' not in line:
                    continue
                match = re.match(r'\[seg-(\d+)\]\s*(.*)', line)
                if match:
                    try:
                        idx = int(match.group(1))
                        text = match.group(2).strip()
                        if text:
                            parsed_lektor_dict[idx] = text
                    except ValueError:
                        continue
        except Exception as batch_err:
            print(f"[WARNING] Greška u Lektor batchu {batch_idx + 1}: {batch_err}")

    lektor_duration = time.time() - t_start_lektor
    
    if len(parsed_lektor_dict) > 0:
        for i, seg in enumerate(translated_segments):
            if i in parsed_lektor_dict:
                seg["text"] = parsed_lektor_dict[i]
        
    # Na kraju, uvek primenjujemo post-processing čišćenje/korekciju teksta na sve segmente
    for seg in translated_segments:
        if "text" in seg:
            seg["text"] = clean_translation_text(seg["text"])
            
    return {
        "status": "success", 
        "translated_segments": translated_segments,
        "metrics": {
            "translator_duration": translator_duration,
            "lektor_duration": lektor_duration
        }
    }
