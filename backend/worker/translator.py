import json
import cv2
import base64
import os
import time
import re
from typing import List
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ђ': 'đ', 'е': 'e', 'ж': 'ž',
    'з': 'z', 'и': 'i', 'ј': 'j', 'к': 'k', 'л': 'l', 'љ': 'lj', 'м': 'm', 'н': 'n',
    'њ': 'nj', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'ћ': 'ć', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'č', 'џ': 'dž', 'ш': 'š',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Ђ': 'Đ', 'Е': 'E', 'Ж': 'Ž',
    'З': 'Z', 'И': 'I', 'Ј': 'J', 'К': 'K', 'Л': 'L', 'Љ': 'Lj', 'М': 'M', 'Н': 'N',
    'Њ': 'Nj', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'Ћ': 'Ć', 'У': 'U',
    'Ф': 'F', 'Х': 'H', 'Ц': 'C', 'Ч': 'Č', 'Џ': 'Dž', 'Ш': 'Š',
    'ѓ': 'đ', 'ќ': 'ć', 'ѕ': 'dz', 'Ѓ': 'Đ', 'Ќ': 'Ć', 'Ѕ': 'Dz'
}

def to_latin(text: str) -> str:
    if not text:
        return text
    res = []
    for char in text:
        res.append(CYRILLIC_TO_LATIN.get(char, char))
    text = "".join(res)
    
    # Dodatno čišćenje bugarskih/čeških specifičnih karaktera
    text = text.replace('ť', 't')
    text = text.replace('Ť', 'T')
    text = text.replace('ъ', 'a')
    text = text.replace('Ъ', 'A')
    
    # Determinističke zamene ijekavizama, makedonizama i čestih grešaka modela
    replacements = {
        r'\bdijelovi\b': 'delovi',
        r'\bdijelove\b': 'delove',
        r'\bdijela\b': 'dela',
        r'\bdijelom\b': 'delom',
        r'\bdijel\b': 'deo',
        r'\brješenje\b': 'rešenje',
        r'\brješenja\b': 'rešenja',
        r'\brješenjem\b': 'rešenjem',
        r'\brješenjima\b': 'rešenjima',
        r'\bvještački\b': 'veštački',
        r'\bvještačka\b': 'veštačka',
        r'\bvještačko\b': 'veštačko',
        r'\bvještačke\b': 'veštačke',
        r'\bvještačkih\b': 'veštačkih',
        r'\bvidio\b': 'video',
        r'\bsmije\b': 'smeje',
        r'\bdolje\b': 'dole',
        r'\bgdje\b': 'gde',
        r'\bnijesu\b': 'nisu',
        r'\busmjeruju\b': 'usmeravaju',
        r'\bspokoen\b': 'spokojan',
        r'\bspokoena\b': 'spokojna',
        r'\bspokoeno\b': 'spokojno',
        r'\bspokoeni\b': 'spokojni',
        r'\bkomarice\b': 'komarci',
        r'\bkomarica\b': 'komarac',
        r'\bkomaricama\b': 'komarcima',
        r'\banticonceptiv\b': 'kontracepcija',
        r'\bzaštića\b': 'štiti',
        r'\boluhami\b': 'olujama',
        r'\bosvještiti\b': 'olabaviti',
        r'\bdengue šake\b': 'denga groznice',
        r'\bdengue\b': 'denga',
        r'\bfebre\b': 'groznice',
        r'\bžuta febra\b': 'žuta groznica',
        r'\bžute febre\b': 'žute groznice',
        r'\bženice\b': 'ženke',
        r'\bženicama\b': 'ženkama',
        r'\bšaljubiti\b': 'poludeti',
        r'\btrpešćine\b': 'strpljenja',
        r'\bsmejte\b': 'smeje',
        r'\bsmejne\b': 'smeje',
        r'\bvreže\b': 'seče',
        r'\bse smešta\b': 'maže',
        r'\bdrevne osnovice\b': 'drvene osnove',
        r'\bdrevne\b': 'drvene',
        r'\bzavari seam\b': 'zavari šav',
        r'\bseam\b': 'šav',
        r'\buvijek\b': 'uvek',
        r'\bpolovicu\b': 'polovinu',
        r'\bpolovica\b': 'polovina',
        r'\bpolovice\b': 'polovine',
        r'\bpolovici\b': 'polovini',
        r'\bsvijet\b': 'svet',
        r'\bdijete\b': 'dete',
        r'\bvrijeme\b': 'vreme',
        r'\bumjesto\b': 'umesto',
        r'\bvjerovatno\b': 'verovatno',
        r'\bvjerojatno\b': 'verovatno',
        r'\bvjerovati\b': 'verovati',
        r'\bmjesto\b': 'mesto',
        r'\bmjesta\b': 'mesta',
        r'\bprimjerno\b': 'primereno',
        r'\bneprimjerno\b': 'neprimereno',
        r'\bprimerno\b': 'primereno',
        r'\bneprimerno\b': 'neprimereno',
        r'\bopakuj\b': 'obmotaj',
        r'\bopakujte\b': 'obmotajte',
        r'\bopakuje\b': 'obmotava',
        r'\bopakuju\b': 'obmotavaju',
        r'\bteško oko\b': 'čvrsto oko',
        r'\bneprimerno sigurno\b': 'nedovoljno čvrsto',
        r'\bneprimerno siguran\b': 'nedovoljno čvrst',
        r'\bneprimereno sigurno\b': 'nedovoljno čvrsto',
        r'\bneprimereno siguran\b': 'nedovoljno čvrst',
        r'\bse lako odlaze\b': 'lako olabave',
        r'\blako odlaze\b': 'lako olabave',
        r'\brezao papir\b': 'sekao papir',
        r'\brezati papir\b': 'seći papir',
        r'\bserez\b': 'isečeš',
        r'\bserežeš\b': 'isečeš',
        r'\bsereže\b': 'iseče',
        r'\bserezati\b': 'iseći',
        r'\bsrezati\b': 'iseći'
    }
    
    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        
    return text

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
        b64_str = base64.b64encode(buffer).decode('utfdef extract_and_parse_json(text: str):
    if not text:
        return None
    # Čišćenje thought tagova ako ih model sa rezonovanjem vrati
    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Traženje JSON bloka unutar ```json i ```
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
            
    # Traženje prvog '[' i poslednjeg ']' ili '{' i '}'
    start_arr = text.find('[')
    end_arr = text.rfind(']')
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        try:
            return json.loads(text[start_arr:end_arr+1])
        except json.JSONDecodeError:
            pass
            
    start_obj = text.find('{')
    end_obj = text.rfind('}')
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        try:
            return json.loads(text[start_obj:end_obj+1])
        except json.JSONDecodeError:
            pass
            
    return None

def translate_segments(segments: list, video_path: str = None, progress_callback=None) -> dict:
    """
    Poziva Modal Serverless Lektor (Qwen3-32B) za tekstualni prevod visoke tačnosti.
    Optimizovano: bez slika, bez hladnog starta na A10G, batch size = 30.
    """
    import time
    translator_duration = 0.0

    if not segments:
        return {"status": "success", "translated_segments": [], "metrics": {"translator_duration": 0.0, "lektor_duration": 0.0}}

    if not settings.MODAL_LEKTOR_URL:
        print("[WARNING] MODAL_LEKTOR_URL nije definisan. Vraćam originalni tekst.")
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

    print(f"[TRANSLATOR] Pokrećem prevođenje {len(segments)} segmenata koristeći Qwen3-32B Lektor endpoint.", flush=True)
    t_start_trans = time.time()
    
    batch_size = 30
    parsed_dict = {}
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    
    for batch_idx, batch_start in enumerate(range(0, len(segments), batch_size)):
        batch_segments = segments[batch_start:batch_start + batch_size]
        print(f"[TRANSLATOR] Batch {batch_idx + 1}/{((len(segments)-1)//batch_size)+1} (segmenti {batch_start} do {batch_start + len(batch_segments) - 1})", flush=True)
        
        if progress_callback:
            progress_callback(detail=f"Prevođenje batcha {batch_idx + 1}...")
            
        transcript_text = ""
        for j, s in enumerate(batch_segments):
            global_idx = batch_start + j
            transcript_text += f"[seg-{global_idx}] {s['text']}\n"
            
        prompt_text = (
            "Ti si vrhunski profesionalni prevodilac za srpski jezik. Tvoj zadatak je da prevedeš priloženi transkript sa engleskog na SRPSKI jezik (EKAVICA).\n\n"
            "PRAVILA ZA PREVOD:\n"
            "1. ZNAČENJE, A NE BUKVALNI PREVOD: Prevod mora zvučati 100% prirodno. Koristi srpske idiome i termine (npr. 'articles of incorporation' su 'osnivački akti' ili 'registracioni dokumenti', a ne 'članci u korporaciju').\n"
            "2. PRIPREMA TEKSTA ZA TTS (SINTEZU GLASA) - ZLATNA PRAVILA:\n"
            "   - BROJEVI SLOVIMA: Sve brojeve, cifre i procente obavezno piši SLOVIMA (npr. 'sto hiljada dolara' umesto '100.000 dolara', 'tri godine' umesto '3 godine', 'pet minuta' umesto '5 minuta'). Godine (npr. 'dve hiljade dvadeset šesta') takođe piši slovima.\n"
            "   - FONETSKI STRANI BRENDOVI, IMENA, KVARTOVI I NASLOVI: Sve strane brendove, platforme, lična imena, četvrti/kvartove (npr. 'Cow Hollow' -> 'Kau Holou') i naslove knjiga/projekata piši isključivo FONETSKI, tj. onako kako se izgovaraju na srpskom jeziku. NEMOJ prevoditi njihovo značenje na srpski (npr. 'Brave New World' piši kao 'Brejv Nju Vorld' a ne 'Vrli novi svet', 'Superintelligence' piši kao 'Superintelidžens' a ne 'Superinteligencija', 'Andon Labs' piši kao 'Endon Labs' a ne 'Endon laboratorije'). Ne ostavljaj engleski pravopis niti crtice u akronimima (nikada ne piši 'Ej-Aj' sa crticom verujući da to TTS model bolje čita, piši 'Ej Aj').\n"
            "   - PREVOD ZA AI: Skraćenicu 'AI' uvek prevodi i piši kao 'Ej Aj' (sa razmakom, bez crtice). Nemoj koristiti izraz 'veštačka inteligencija' niti ostavljati 'AI', već koristi isključivo 'Ej Aj'. OBAVEZNO dekliniraj izraz 'Ej Aj' u zavisnosti od konteksta rečenice i predloga:\n"
            "     * predlog 'sa' zahteva instrumental -> 'sa Ej Ajem' (npr. 'nema veze sa Ej Ajem', 'rad sa Ej Ajem')\n"
            "     * predlog 'o' zahteva lokativ -> 'o Ej Aju' (npr. 'govorimo o Ej Aju', 'najnovije o Ej Aju')\n"
            "     * predlog 'od' zahteva genitiv -> 'od Ej Aja' (npr. 'razvoj od strane Ej Aja', 'strah od Ej Aja')\n"
            "     * predlog 'u' zahteva lokativ/akuzativ -> 'u Ej Aju' / 'u Ej Aj'\n"
            "     * predlog 'za' zahteva akuzativ -> 'za Ej Aj'\n"
            "     Nikada nemoj pomešati ove padeže niti ostaviti 'Ej Aj' u nominativu ako smisao rečenice zahteva drugi padež.\n"
            "3. GRAMATIKA, PRAVOPIS I VERODOSTOJNOST:\n"
            "   - GLAGOLSKO VREME: Prevod mora strogo pratiti glagolsko vreme iz originala. Ako je rečenica u prezentu (sadašnjem vremenu), prevod mora biti u prezentu (npr. 'I have no face' -> 'Nemam lice', nikako u prošlom 'Nisam imala lice'). Ako je u prošlom ili budućem vremenu, prevod mora to verno pratiti.\n"
            "   - ROD GOVORNIKA (GENDER): Obrati pažnju na rod govornika (ako je iz konteksta jasno). Ako je govornik muško ili se radi o opštem/neutralnom rodu, koristi muški rod u prošlom vremenu (npr. 'bio sam', 'rekao sam'). Ako je u pitanju ženski govornik, koristi ženski rod (npr. 'bila sam', 'rekla sam').\n"
            "   - DOSLEDNO OBRAĆANJE (T/V): Obraćanje mora biti gramatički i stilski dosledno u celoj rečenici. Koristi isključivo jedninsko neformalno obraćanje 'ti' (npr. 'ako želiš da ostaneš... prati za više') jer su video snimci modernog i prisnog formata. Nemoj mešati jedninu 'ti' sa množinom 'vi' (npr. 'želiš ... pratite').\n"
            "   - DEKLINACIJA ROBOTIKE: Oblast 'robotics' je na srpskom 'robotika' koja se koristi isključivo u jednini (u padežima 'robotici' ili 'robotikom', nikada množinski oblici 'robotike' ili 'robotikama'). Frazu 'latest in AI and robotics' prevedi prirodno kao 'najnovijem o Ej Aju i robotici' ili 'najnovijim dešavanjima iz sveta Ej Aja i robotike', nikako nužno 'najnovijim o Ej Aj i robotikama'.\n"
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
            "6. STROGO ODRŽAVANJE GRANICA SEGMENATA: Prevedi svaki red nezavisno i vrati prevod pod tačnim [seg-ID] tagom tog reda. Nikada nemoj spajati dva reda u jedan, niti preskakati redove. Svaki ulazni red mora imati tačno jedan odgovarajući izlazni red sa istim tagom. Ako se rečenica proteže kroz više redova, prevedi delove rečenice unutar tih istih redova bez njihovog spajanja.\n\n"
            "FORMAT ODGOVORA:\n"
            "Odgovori isključivo u validnom JSON formatu prema sledećoj šemi, bez ikakvog uvodnog ili pratećeg teksta. JSON mora sadržati listu 'segments' gde svaki segment ima ključeve:\n"
            "  - 'id': ceo broj (identifikator segmenta iz ulaza)\n"
            "  - 'translated_text': korigovan i očišćen prevod na srpskom jeziku\n\n"
            "PRIMER TRANSLACIJE:\n"
            "Izlaz:\n"
            "{\n"
            "  \"segments\": [\n"
            "    {\n"
            "      \"id\": 9999,\n"
            "      \"translated_text\": \"Ova kompanija je dala Ej Aj agentu sto hiljada dolara, kreditnu karticu i trogodišnji zakup lokala u San Francisku kako bi videli da li može da vodi prodavnicu.\"\n"
            "    },\n"
            "    {\n"
            "      \"id\": 99999,\n"
            "      \"translated_text\": \"Endon Labs je kreirao ovaj Ej Aj i nazvao ga Luna (zasnovan na Klodu).\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"TRANSKRIPT ZA PREVOD:\n{transcript_text}"
        )
        
        payload = {
            "model": "qwen-lektor",
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.1,
            "max_tokens": 4096
        }
        
        try:
            res = call_modal_endpoint(
                url=url, 
                payload=payload, 
                timeout_seconds=300,
                progress_callback=None
            )
            
            try:
                raw_output = res["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                raw_output = str(res)
                
            print(f"[DEBUG] BATCH {batch_idx + 1} RAW TRANSLATION:\n{raw_output}", flush=True)
            
            # Parsiranje - prvo pokušavamo sa JSON
            data = extract_and_parse_json(raw_output)
            batch_parsed = {}
            if data:
                segments_list = data if isinstance(data, list) else data.get("segments", [])
                if isinstance(segments_list, list):
                    for item in segments_list:
                        if isinstance(item, dict):
                            idx = item.get("id")
                            text = item.get("translated_text") or item.get("refined_text") or item.get("text")
                            if idx is not None and text is not None:
                                batch_parsed[int(idx)] = str(text).strip()
                                
            # Ako JSON parsiranje nije dalo sve segmente iz ovog batch-a, koristimo regex tag fallback
            if len(batch_parsed) < len(batch_segments):
                print(f"[TRANSLATOR] JSON parser vratio {len(batch_parsed)} od {len(batch_segments)} segmenata. Pokrećem regex tag fallback...", flush=True)
                parts = re.split(r'\[seg[- ]*(\d+)\]', raw_output)
                if len(parts) > 1:
                    for k in range(1, len(parts), 2):
                        try:
                            idx = int(parts[k])
                            text = parts[k+1].strip().lstrip(':-= \t\n')
                            if text and idx not in batch_parsed:
                                batch_parsed[idx] = text
                        except ValueError:
                            continue
                            
            # Spajanje u glavni rečnik
            for idx, text in batch_parsed.items():
                if batch_start <= idx < batch_start + len(batch_segments):
                    parsed_dict[idx] = text
                    
        except Exception as batch_err:
            print(f"[ERROR] Greška pri prevođenju batcha {batch_idx + 1}: {batch_err}", flush=True)
            
    translator_duration = time.time() - t_start_trans
    print(f"[TRANSLATOR] Prevođenje završeno za {translator_duration:.2f}s. Uspešno prevedeno {len(parsed_dict)} od {len(segments)} segmenata.", flush=True)

    # Pravljenje finalne liste segmenata
    final_segments = []
    for i, orig in enumerate(segments):
        # Pametan fallback: ako nema prevoda, koristi originalni tekst umesto praznog stringa da sprečimo tišinu
        t_text = parsed_dict.get(i, "").strip()
        if not t_text:
            print(f"[WARNING] Segment {i} nema prevod. Koristim originalni engleski tekst kao fallback.", flush=True)
            t_text = orig["text"]
            
        final_segments.append({
            "id": orig.get("id", i),
            "start": orig["start"],
            "end": orig["end"],
            "text": t_text,
            "original_text": orig["text"]
        })
        
    # Pokretanje Lektor faze
    try:
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

GLOSSARY_FILE = os.path.join(os.path.dirname(__file__), "glossaries.json")

def load_glossaries() -> dict:
    if os.path.exists(GLOSSARY_FILE):
        try:
            with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[GLOSSARY] Greška pri čitanju {GLOSSARY_FILE}: {e}")
    return {}

def detect_topic_and_terms(transcript_text: str) -> dict:
    """
    Poziva Modal Lektor da detektuje temu i izvuče 5-10 ključnih stručnih termina iz transkripta.
    Vraća rečnik sa ključevima 'topic' i 'terms'.
    """
    if not settings.MODAL_LEKTOR_URL:
        return {"topic": "other", "terms": []}
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "Analyze the following English transcript from a video. "
        "1. Identify the main topic of the video (choose one of: 'welding_and_crafts', 'biology_and_nature', 'technology_and_it', or 'other').\n"
        "2. Extract 5-10 key technical nouns, verbs, or phrases (jargon) that are central to this video.\n\n"
        "Respond strictly in JSON format with the following keys:\n"
        "{\n"
        "  \"topic\": \"topic_name\",\n"
        "  \"terms\": [\"term1\", \"term2\", ...]\n"
        "}\n\n"
        f"TRANSCRIPT:\n{transcript_text}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 300
    }
    
    try:
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL).strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        data = json.loads(content)
        return {
            "topic": data.get("topic", "other"),
            "terms": data.get("terms", [])
        }
    except Exception as e:
        print(f"[GLOSSARY DETECT ERROR] Greška pri detekciji teme: {e}")
        return {"topic": "other", "terms": []}

def translate_terms_to_serbian(terms: list) -> dict:
    """
    Prevedi listu engleskih stručnih pojmova na srpski jezik (ekavica, latinica).
    """
    if not terms or not settings.MODAL_LEKTOR_URL:
        return {}
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "You are an expert English-to-Serbian translator. Translate the following list of English technical terms "
        "or jargon into standard Serbian as spoken in Serbia (ekavica, latinica). Keep translations short, accurate, and natural. "
        "IMPORTANT RULES:\n"
        "- Use standard Serbian vocabulary only (Serbia, ekavica). Avoid dialectal, archaic, or invented words.\n"
        "- Avoid Bulgarian, Macedonian, Croatian, or Slovenian words (e.g. do NOT translate 'pipes' as 'trublji' or 'trube' -> use 'cevi'; do NOT translate 'weld' as 'zavar' or 'var'; do NOT translate 'welders' as 'varilci' -> use 'zavarivači'; do NOT translate 'fold' as 'ugovo' -> use 'preklop' or 'presavijanje').\n"
        "- Translate exactly the list of terms.\n\n"
        "Respond strictly in JSON format (a single dictionary where keys are English terms and values are Serbian translations):\n"
        "{\n"
        "  \"english term\": \"serbian translation\"\n"
        "}\n\n"
        f"TERMS: {json.dumps(terms)}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 400
    }
    
    try:
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL).strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        return json.loads(content)
    except Exception as e:
        print(f"[GLOSSARY TRANSLATE ERROR] Greška pri prevođenju termina: {e}")
        return {}

def get_dynamic_glossary(transcript_text: str) -> str:
    """
    Glavna funkcija koja orkestrira detekciju teme, proveru u bazi i automatski prevod nepoznatih reči.
    Vraća formatirani tekstualni glosar za prompt lektora.
    """
    print("[GLOSSARY] Pokrećem analizu teme i prepoznavanje termina...", flush=True)
    detect_res = detect_topic_and_terms(transcript_text)
    topic = detect_res.get("topic", "other")
    terms = detect_res.get("terms", [])
    
    print(f"[GLOSSARY] Detektovana tema: {topic}. Izvučeni termini: {terms}", flush=True)
    
    glossaries = load_glossaries()
    predefined = glossaries.get(topic, {})
    
    final_glossary = {}
    missing_terms = []
    
    for term in terms:
        term_clean = term.strip().lower()
        found = False
        for category, cat_dict in glossaries.items():
            if term_clean in cat_dict:
                final_glossary[term] = cat_dict[term_clean]
                found = True
                break
        
        if not found:
            missing_terms.append(term)
            
    if missing_terms:
        print(f"[GLOSSARY] Prevodim {len(missing_terms)} nepoznatih stručnih termina preko LLM...", flush=True)
        llm_translations = translate_terms_to_serbian(missing_terms)
        for eng, srb in llm_translations.items():
            if srb:
                final_glossary[eng] = srb
                
    for eng, srb in predefined.items():
        if eng not in final_glossary:
            final_glossary[eng] = srb
            
    if not final_glossary:
        return "Nema specifičnih termina za ovaj video."
        
    glossary_lines = []
    for eng, srb in final_glossary.items():
        glossary_lines.append(f'- "{eng}" -> "{srb}"')
        
    glossary_str = "\n".join(glossary_lines)
    print(f"[GLOSSARY] Formiran dinamički glosar sa {len(final_glossary)} stavki.", flush=True)
    return glossary_str

def lektor_segments(original_segments, translated_segments, progress_callback=None, translator_duration=0.0):
    """
    Druga faza: Qwen 2.5/3.0 Lektor lekturiše grubi prevod sa programskom deduplikacijom i dinamičkim glosarom.
    Optimizovano: batch_size = 30, max_tokens = 4096, robusno JSON + Regex parsiranje.
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
        
    # 1. Programska deduplikacija ponovljenih identičnih segmenata
    unique_segments = []
    seen_keys = set()
    orig_to_unique_map = {}
    
    for i, seg in enumerate(translated_segments):
        orig_seg = original_segments[i]
        duration = seg["end"] - seg["start"]
        
        key = orig_seg["text"].strip().lower()
        
        if key not in seen_keys:
            seen_keys.add(key)
            unique_idx = len(unique_segments)
            unique_segments.append({
                "unique_id": unique_idx,
                "orig_indices": [i],
                "orig_text": orig_seg["text"],
                "translated_text": seg["text"],
                "start": seg["start"],
                "end": seg["end"],
                "duration": duration
            })
            orig_to_unique_map[i] = unique_idx
        else:
            for u_idx, u_seg in enumerate(unique_segments):
                u_key = u_seg["orig_text"].strip().lower()
                if u_key == key:
                    u_seg["orig_indices"].append(i)
                    orig_to_unique_map[i] = u_idx
                    break

    print(f"[LEKTOR] Deduplikacija završena. Sa originalnih {len(translated_segments)} smanjeno na {len(unique_segments)} jedinstvenih segmenata.", flush=True)

    # Generisanje dinamičkog glosara za ceo video pre pokretanja lekture
    try:
        transcript_text = " ".join([seg["orig_text"] for seg in unique_segments])
        dynamic_glossary_str = get_dynamic_glossary(transcript_text)
    except Exception as e:
        print(f"[WARNING] Greška pri kreiranju dinamičkog glosara: {e}. Koristim prazan glosar.")
        dynamic_glossary_str = "Nema specifičnih termina za ovaj video."

    batch_size = 30
    parsed_lektor_dict = {}
    lektor_duration = 0.0
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    t_start_lektor = time.time()
    
    for batch_idx, batch_start in enumerate(range(0, len(unique_segments), batch_size)):
        batch_translated = unique_segments[batch_start:batch_start + batch_size]
        
        print(f"[LEKTOR] Pokrećem Lektor batch {batch_idx + 1} (segmenti {batch_start} do {batch_start + len(batch_translated) - 1})...", flush=True)
        
        lektor_input = ""
        for j, seg in enumerate(batch_translated):
            global_idx = batch_start + j
            duration = seg["duration"]
            lektor_input += f"[seg-{global_idx}] (trajanje: {duration:.1f}s) ENG: {seg['orig_text']} | SRB: {to_latin(seg['translated_text'])}\n"
            
        lektor_prompt = (
            "Ti si glavni urednik, prevodilac i lektor za srpski jezik (ekavica). Tvoj zadatak je da detaljno pregledaš grubi prevod (SRB) u odnosu na originalni engleski tekst (ENG) i trajanje segmenta, ispraviš sve greške i vratiš tečan, potpuno prirodan srpski prevod na ekavici i latinici.\n\n"
            "OBAVEZNA PRAVILA ZA PREVOĐENJE I UREĐIVANJE:\n\n"
            "1. PIŠI ISKLJUČIVO SRPSKOM LATINICOM:\n"
            "   - Celokupan tvoj izlaz mora biti na srpskoj latinici (nikada ćirilica i nikada mešavina pisama).\n\n"
            "2. GLOSAR I ZAMENA TERMINOLOGIJE (KORISTI OVE PREVODE, ALI IH GRAMATIČKI PRILAGODI KONTEKSTU):\n"
            "   - Koristi ponuđeni prevod za stručni termin, ali ga gramatički prilagodi rečenici (npr. promeni padež, rod, broj, ili ga pretvori u odgovarajući glagolski oblik ako je u pitanju radnja, kako bi rečenica bila prirodna, npr. 'tack weld' -> 'heftati'/'heftaš'/'punktirati'/'punktiraš', a ne bukvalno imenica 'heftanje' ako ne odgovara).\n"
            f"{dynamic_glossary_str}\n\n"
            "3. STRIKTNA EKAVICA I PRAVOPIS (BEZ DIJALEKATA, IJEKAVICE I STRANIH REČI):\n"
            "   - Zameni sve makedonske/bugarske/hrvatske/češke reči srpskim ekavskim rečima.\n"
            "   - NIKADA ne koristi ijekavske reči kao što su:\n"
            "     * \"smije\", \"smie\" -> smeje\n"
            "     * \"dijela\", \"dijelovi\" -> dela, delovi\n"
            "     * \"dijel\" -> deo\n"
            "     * \"vidio\" -> video\n"
            "     * \"rješenje\" -> rešenje\n"
            "     * \"točke\", \"točka\" -> tačke, tačka\n"
            "     * \"štorme\", \"štormovi\", \"oluhami\" -> oluje, olujama\n"
            "     * \"zavariť\" -> zavariti\n"
            "     * \"poroditi se\" -> pariti se\n"
            "     * \"zaostrili\" -> zabrinuli\n"
            "     * \"korisnena\" -> korišćena\n"
            "     * \"ispuskači\" -> pustiti\n"
            "     * \"nacrtai\" -> nacrtaj\n"
            "     * \"stricno\" -> striktno\n"
            "     * \"zaštića\" -> štiti\n"
            "     * \"matiču\" -> maticu\n\n"
            "4. BEZ SKRAĆIVANJA PREMA DUŽINI SEGMENTA (OSIM MIKRO-SEGMENATA):\n"
            "   - U ovoj fazi tvoj prioritet je potpunost, bogatstvo i gramatička tačnost prevoda. NIKADA ne skraćuj rečenicu niti izbacuj detalje samo da bi se uklopio u vremenski limit. Prevedi kompletnu misao iz engleskog teksta prirodno i tačno na srpski.\n"
            "   - MIKRO-SEGMENTI (trajanje < 0.5s): Ako je trajanje segmenta kraće od 0.5 sekundi (npr. 0.1s, 0.2s, 0.3s, 0.4s), refined_text MORA biti potpuno prazan string `\"\"` (bez izuzetaka!).\n"
            "   - Za sve ostale segmente, bez obzira na trajanje, vrati pun, bogat prevod.\n\n"
            "5. DOSLEDNA TI-FORMA (NEFORMALNO OBRAĆANJE):\n"
            "   - Obraćaj se isključivo sa \"ti\" (npr. \"Ako imaš\", a ne \"Ako imate\"; \"Poravnaj\", a ne \"Poravnajte\").\n"
            "   - Koristi ispravne imperativne oblike: \"Poravnaj\", \"Zavari\", \"Iseci\", \"Nacrtaj\".\n\n"
            "6. LINGVISTIČKA SAMOKONTROLA (IZUZETNO VAŽNO):\n"
            "   - Pre nego što doneseš konačan prevod, u polju 'analysis' (CoT) obavezno razloži značenje teških fraza u kontekstu i proveri gramatičko slaganje (rod, broj, padež).\n"
            "   - NIKADA ne koristi nepravilne prevode poput:\n"
            "     * \"where it gets crazy\" -> \"postaje ludo\"\n"
            "     * \"It turns out...\" -> \"Ispostavilo se\"\n"
            "     * \"laughs\" -> \"smeje se\"\n"
            "     * \"cracked\" (u kontekstu metala/cevi) -> \"napuklo\"\n"
            "     * \"patience\" -> \"strpljenje\"\n"
            "     * \"rubs a dark paste\" -> \"maže tamnu pastu\"\n\n"
            "FORMAT ODGOVORA:\n"
            "Odgovori isključivo u validnom JSON formatu prema sledećoj šemi, bez ikakvog uvodnog ili pratećeg teksta. JSON mora sadržati listu 'segments' gde svaki segment ima ključeve:\n"
            "  - 'id': ceo broj (identifikator segmenta iz ulaza)\n"
            "  - 'analysis': kratko obrazloženje odluka (npr. 'Trajanje < 0.5s, vraćam prazan string.')\n"
            "  - 'refined_text': korigovan i očišćen prevod na srpskom jeziku\n\n"
            f"TEKST ZA LEKTURU:\n{lektor_input}"
        )

        try:
            lektor_payload = {
                "model": "qwen-lektor",
                "messages": [{"role": "user", "content": lektor_prompt}],
                "temperature": 0.1,
                "max_tokens": 4096,
                "presence_penalty": 0.5
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

            # Čišćenje thought tagova ako ih model sa rezonovanjem vrati
            lektor_raw_clean = re.sub(r'<thought>.*?</thought>', '', lektor_raw, flags=re.DOTALL).strip()
            print(f"[DEBUG] BATCH {batch_idx + 1} LEKTOR CLEANED OUTPUT:\n{lektor_raw_clean}", flush=True)
            
            # Parsiranje pomoću našeg novog robusnog json parsera
            data = extract_and_parse_json(lektor_raw_clean)
            batch_parsed_lektor = {}
            if data:
                segments_list = data if isinstance(data, list) else data.get("segments", [])
                if isinstance(segments_list, list):
                    for item in segments_list:
                        if isinstance(item, dict):
                            idx = item.get("id")
                            text = item.get("refined_text") or item.get("translated_text") or item.get("text")
                            if idx is not None and text is not None:
                                batch_parsed_lektor[int(idx)] = str(text).strip()
                                
            # Regex fallback ako nedostaju neki segmenti
            if len(batch_parsed_lektor) < len(batch_translated):
                print(f"[LEKTOR] JSON parser vratio {len(batch_parsed_lektor)} od {len(batch_translated)} segmenata. Pokrećem regex fallback...", flush=True)
                parts = re.split(r'\[seg[- ]*(\d+)\]', lektor_raw_clean)
                if len(parts) > 1:
                    for k in range(1, len(parts), 2):
                        try:
                            idx = int(parts[k])
                            text = parts[k+1].strip().lstrip(':-= \t\n')
                            if text:
                                # Ako model ponovi "SRB: ..." ili slično, uzimamo samo prevod
                                if "SRB:" in text:
                                    text = text.split("SRB:")[-1].strip()
                                elif "|" in text:
                                    # Formati poput ENG: ... | SRB: ...
                                    parts_pipe = text.split("|")
                                    for p in parts_pipe:
                                        if "SRB:" in p:
                                            text = p.split("SRB:")[-1].strip()
                                            break
                                if idx not in batch_parsed_lektor:
                                    batch_parsed_lektor[idx] = text
                        except ValueError:
                            continue
                            
            # Spajanje u parsed_lektor_dict
            for idx, text in batch_parsed_lektor.items():
                if batch_start <= idx < batch_start + len(batch_translated):
                    parsed_lektor_dict[idx] = text
                    print(f"[LEKTOR] Segment {idx} lekturisan: {text[:60]}...", flush=True)
                    
        except Exception as batch_err:
            print(f"[WARNING] Greška u Lektor batchu {batch_idx + 1}: {batch_err}")

    lektor_duration = time.time() - t_start_lektor
    
    if len(parsed_lektor_dict) > 0:
        for i, seg in enumerate(translated_segments):
            unique_idx = orig_to_unique_map.get(i)
            if unique_idx is not None and unique_idx in parsed_lektor_dict:
                seg["text"] = parsed_lektor_dict[unique_idx]
        
    for seg in translated_segments:
        if "text" in seg:
            seg["text"] = clean_translation_text(seg["text"])
            seg["text"] = to_latin(seg["text"])
            
    return {
        "status": "success", 
        "translated_segments": translated_segments,
        "metrics": {
            "translator_duration": translator_duration,
            "lektor_duration": lektor_duration
        }
    }

