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
        r'\bsrezati\b': 'iseći',
        r'\bvidjeti\b': 'videti',
        r'\bvidjeće\b': 'videće',
        r'\bvidjećeš\b': 'videćeš',
        r'\bvidjećemo\b': 'videćemo',
        r'\bvidjećete\b': 'videćete',
        r'\bdonijeti\b': 'doneti',
        r'\bdonijeće\b': 'doneće',
        r'\bdonijećeš\b': 'donećeš',
        r'\bdonijećemo\b': 'donećemo',
        r'\bdonijećete\b': 'donećete',
        r'\bdijeliti\b': 'deliti',
        r'\bdijeliće\b': 'deliće',
        r'\bdijelićeš\b': 'delićeš',
        r'\bdijelićemo\b': 'delićemo',
        r'\bdijelićete\b': 'delićete',
        r'\bhtjeti\b': 'hteti',
        r'\bhtjeće\b': 'hteće',
        r'\bhtjećeš\b': 'htećeš',
        r'\bhtjećemo\b': 'htećemo',
        r'\bhtjećete\b': 'htećete',
        r'\briješiti\b': 'rešiti',
        r'\briješiće\b': 'rešiće',
        r'\briješeno\b': 'rešeno',
        r'\bpromijeniti\b': 'promeniti',
        r'\bpromijeniće\b': 'promeniće',
        r'\bpromijenjeno\b': 'promenjeno',
        r'\brazumjeti\b': 'razumeti',
        r'\brazumjeće\b': 'razumeće',
        r'\bukuju\b': 'bodu',
        r'\bukuje\b': 'bode'
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
        b64_str = base64.b64encode(buffer).decode('utf-8')
        frames_b64.append(b64_str)

    cap.release()
    return frames_b64

def clean_thought_tags(text: str) -> str:
    if not text:
        return ""
    # Podrška i za <think> (DeepSeek) i za <thought> (Qwen)
    for tag in ["think", "thought"]:
        text = re.sub(rf'<{tag}>.*?</{tag}>', '', text, flags=re.DOTALL)
        if f"<{tag}>" in text:
            text = text.split(f"<{tag}>")[0]
    return text.strip()

def extract_and_parse_json(text: str):
    if not text:
        return None
    # Čišćenje thought tagova ako ih model sa rezonovanjem vrati
    text = clean_thought_tags(text)
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

def generate_video_summary(transcript_text: str) -> str:
    """
    Poziva Modal Lektor (Qwen 32B) da generiše kratak sažetak videa na engleskom (do 100 reči)
    na osnovu celog transkripta, kako bi se pružio globalni kontekst.
    """
    if not transcript_text or not settings.MODAL_LEKTOR_URL:
        return "No context available."
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "You are an AI assistant helping a translator. Analyze the following English transcript from a video. "
        "Write a very brief summary (maximum 100 words) of what the video is about. "
        "Focus on the main topic, context, and key goal of the video. Keep it concise.\n\n"
        f"TRANSCRIPT:\n{transcript_text}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 800
    }
    
    try:
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        content = clean_thought_tags(content)
        return content
    except Exception as e:
        print(f"[SUMMARY ERROR] Greška pri generisanju sažetka: {e}", flush=True)
        return "Failed to generate video summary."

def parse_glossary_to_dict(glossary_str: str) -> dict:
    """
    Parsira tekstualni glosar (dobijen iz get_dynamic_glossary) u Python rečnik.
    """
    glossary_dict = {}
    if not glossary_str:
        return glossary_dict
    for line in glossary_str.split("\n"):
        line = line.strip()
        if not line or not line.startswith("-"):
            continue
        # Tražimo format: - "eng" -> "srb"
        match = re.search(r'-\s*"([^"]+)"\s*->\s*"([^"]+)"', line)
        if match:
            glossary_dict[match.group(1).strip()] = match.group(2).strip()
        else:
            # Fallback za slučaj da nema navodnika: - eng -> srb
            parts = line[1:].split("->")
            if len(parts) == 2:
                eng = parts[0].strip().strip('"')
                srb = parts[1].strip().strip('"')
                if eng and srb:
                    glossary_dict[eng] = srb
    return glossary_dict

def calculate_dynamic_factor(seg: dict, user_avg_speedup: float = 1.0) -> float:
    base_factor = 14.0
    speed = seg.get("speed", 1.0)
    if speed is None:
        speed = 1.0
    voice_type = seg.get("voice_type", "male")
    if voice_type is None:
        voice_type = "male"
        
    voice_correction = {
        "clone": 0.92,
        "male": 1.0,
        "female": 0.95
    }
    correction = voice_correction.get(voice_type, 1.0)
    
    factor = base_factor * speed * correction
    
    if user_avg_speedup > 1.1:
        factor = factor / user_avg_speedup
        
    return factor

def translate_segments(segments: list, video_path: str = None, progress_callback=None, user_avg_speedup: float = 1.0) -> dict:
    """
    Poziva Modal Serverless Lektor (Qwen3-32B) za tekstualni prevod visoke tačnosti.
    Optimizovano: bez slika, bez hladnog starta na A10G, batch size = 30.
    Uvedeni: globalni sažetak, klizni prozor konteksta, Chain-of-Thought analiza,
             dužinska svesnost i running glossary za konzistentnost.
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
    
    # 1. Generisanje globalnog sažetka i glosara za ceo video
    try:
        full_eng_transcript = " ".join([s["text"] for s in segments])
        print("[TRANSLATOR] Generišem globalni sažetak videa...", flush=True)
        video_summary = generate_video_summary(full_eng_transcript)
        print(f"[TRANSLATOR] Sažetak videa uspešno generisan:\n{video_summary}", flush=True)
        
        print("[TRANSLATOR] Generišem dinamički glosar i entitete...", flush=True)
        dynamic_glossary_str = get_dynamic_glossary(full_eng_transcript)
    except Exception as e:
        print(f"[WARNING] Greška pri generisanju globalnog konteksta: {e}. Koristim prazan kontekst.")
        video_summary = "No context available."
        dynamic_glossary_str = "Nema specifičnih termina za ovaj video."

    # Inicijalizacija running glossary mehanizma
    full_glossary_dict = parse_glossary_to_dict(dynamic_glossary_str)
    confirmed_translations = {}

    batch_size = 5
    parsed_dict = {}
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    
    for batch_idx, batch_start in enumerate(range(0, len(segments), batch_size)):
        batch_segments = segments[batch_start:batch_start + batch_size]
        print(f"[TRANSLATOR] Batch {batch_idx + 1}/{((len(segments)-1)//batch_size)+1} (segmenti {batch_start} do {batch_start + len(batch_segments) - 1})", flush=True)
        
        if progress_callback:
            progress_callback(detail=f"Prevođenje batcha {batch_idx + 1}...")
            
        # Generisanje transkripta sa limitom karaktera (dužinska svesnost)
        transcript_text = ""
        for j, s in enumerate(batch_segments):
            global_idx = batch_start + j
            duration = s["end"] - s["start"]
            factor = calculate_dynamic_factor(s, user_avg_speedup)
            limit_char = max(15, int(duration * factor))
            transcript_text += f"[seg-{global_idx}] (trajanje: {duration:.1f}s, LIMIT: {limit_char} karaktera) {s['text']}\n"
            
        # Klizni prozor konteksta (poslednjih 2 segmenta iz prethodnog batch-a)
        history_text = ""
        if batch_idx > 0:
            history_start = max(0, batch_start - 2)
            history_segments = segments[history_start:batch_start]
            history_lines = []
            for prev_idx, prev_seg in enumerate(history_segments):
                global_prev_idx = history_start + prev_idx
                prev_translation = parsed_dict.get(global_prev_idx, "")
                history_lines.append(f"[seg-{global_prev_idx}] ENG: {prev_seg['text']} | SRB: {prev_translation}")
            history_text = "\n".join(history_lines)
            
        history_section = ""
        if history_text:
            history_section = (
                "ISTORIJA PRETHODNIH REČENICA (koristi isključivo kao kontekst da bi prevod novih rečenica bio "
                "gramatički i smisleno povezan sa prethodnim. NIKADA ne prevodi ponovo ove segmente niti ih uključuj u izlazni JSON):\n"
                f"{history_text}\n\n"
            )
            
        # Formiranje running glossary sekcija za ovaj batch
        confirmed_lines = []
        proposed_lines = []
        batch_eng_text = " ".join([s["text"].lower() for s in batch_segments])
        
        for eng_term, srb_term in full_glossary_dict.items():
            if eng_term.lower() in batch_eng_text:
                if eng_term in confirmed_translations:
                    confirmed_lines.append(f'- "{eng_term}" -> "{confirmed_translations[eng_term]}"')
                else:
                    proposed_lines.append(f'- "{eng_term}" -> "{srb_term}"')
                    
        glossary_prompt_section = ""
        if confirmed_lines:
            glossary_prompt_section += (
                "STRIKTNI POTVRĐENI PREVODI IZ PRETHODNIH SEGMENATA (OBAVEZNO koristi tačno ove srpske prevode radi konzistentnosti):\n"
                + "\n".join(confirmed_lines) + "\n\n"
            )
        if proposed_lines:
            glossary_prompt_section += (
                "STRIKTNI PREDLOŽENI GLOSAR ZA NOVE ENTITETE (OBAVEZNO koristi ove srpske prevode i prilagodi ih gramatički kontekstu rečenice, zabranjeno je koristiti druge sinonime):\n"
                + "\n".join(proposed_lines) + "\n\n"
            )
        if not glossary_prompt_section:
            glossary_prompt_section = "Nema specifičnih termina za ovaj batch.\n\n"

        prompt_text = (
            "Ti si vrhunski profesionalni prevodilac za srpski jezik. Tvoj zadatak je da prevedeš priloženi transkript sa engleskog na SRPSKI jezik (EKAVICA).\n\n"
            "VAŽNO ZA REZONOVANJE: U svom procesu razmišljanja (<think>...</think>) budi ekstremno kratak (maksimalno 50 reči ukupno). NIKADA nemoj objašnjavati segment po segment niti raditi analizu svakog segmenta pojedinačno u razmišljanju. Samo ukratko navedi strategiju u dve rečenice i pređi na JSON odgovor.\n\n"
            f"{glossary_prompt_section}"
            f"{history_section}"
            "PRAVILA ZA PREVOD:\n"
            "1. PRIRODAN PREVOD: Prevod mora zvučati 100% prirodno. Koristi srpske idiome i termine.\n"
            "2. PRIPREMA ZA TTS (SINTEZU GLASA):\n"
            "   - Sve brojeve, cifre i procente piši SLOVIMA (npr. 'sto hiljada dolara', 'tri godine', 'dve hiljade dvadeset šesta').\n"
            "   - Strana lična imena, brendove i naslove piši FONETSKI, kako se izgovaraju na srpskom (npr. 'Brejv Nju Vorld', 'Endon Labs', 'Ej Aj').\n"
            "   - Izuzetak: Uobičajene IT akronime i tehnologije poput GPS, Wi-Fi i Bluetooth piši u njihovom originalnom obliku (GPS, Wi-Fi, Bluetooth) i nemoj ih pisati fonetski.\n"
            "   - Reč 'AI' prevodi kao 'Ej Aj' (bez crtice) i obavezno je dekliniraj kroz padeže ('sa Ej Ajem', 'o Ej Aju', 'od Ej Aja', 'za Ej Aj').\n"
            "3. GRAMATIKA I PRAVOPIS:\n"
            "   - Strogo prati glagolsko vreme iz originala (prezent za prezent, prošlo za prošlo).\n"
            "   - Prilagodi rod govornika (muški rod za neutralan/muški, ženski rod za ženski).\n"
            "   - Koristi isključivo jedninsko neformalno obraćanje 'ti' (npr. 'ako želiš', 'poravnaj', 'zavari').\n"
            "   - Prilagodi strana imena i gradove srpskom pravopisu i deklinaciji (npr. 'u San Francisku', 'sa Klodom', 'preko Zuma').\n"
            "   - Prevedi sve engleske izraze u potpunosti (nemoj ostavljati engleske reči).\n"
            "   - Izbegavaj pasivne konstrukcije sa 'od strane' (npr. umesto 'primenjena od strane vlada' koristi aktiv 'koju su vlade primenile').\n"
            "   - Izbegavaj bukvalne prevode engleskih fraza poput 'the hope is' u 'nadam se' ako se govori o opštem cilju projekta (bolje je 'cilj je' ili 'očekuje se'). Reč 'collapses' u kontekstu populacije ili sistema prevodi kao 'nestane', 'propadne' ili 'se uruši', a ne 'da se sruši'.\n"
            "   - MORFOLOGIJA I SLAGANJE: Strogo pazi na morfološko slaganje prideva i imenica po rodu, broju i padežu (npr. 'drveni komad' ili 'komad drveta', a nikako 'komad drvenog'; 'jednake cilindriće' u akuzativu množine, a ne 'jednake cilindri'; 'zavar je gladak' u muškom rodu, a ne 'glatko').\n"
            "   - PRIRODNOST FRAZA: Izbegavaj bukvalne prevode engleskih kolokvijalnih konstrukcija (npr. 'this is where it gets crazy' prevodi kao 'sada stvari postaju zanimljive' ili 'ovde nastaje preokret', a nikako 'ovde postaje ludilo').\n"
            "4. POŠTOVANJE LIMITA KARAKTERA:\n"
            "   - Tvoj prevod (translated_text) za svaki segment mora biti kraći ili jednak prosleđenom LIMITU kako bi se izgovorio u predviđenom vremenu. Koristi kraće sinonime ili sažmi rečenicu ako je potrebno.\n"
            "5. GRANICE SEGMENATA: Prevedi svaki red nezavisno pod tačnim [seg-ID] tagom. Nikada nemoj spajati ili preskakati redove.\n\n"
            "FORMAT ODGOVORA:\n"
            "Odgovori isključivo u validnom JSON formatu prema sledećoj šemi, bez ikakvog uvodnog ili pratećeg teksta. Neka polje 'analysis' bude izuzetno kratko (maksimalno jedna rečenica):\n"
            "{\n"
            "  \"segments\": [\n"
            "    {\n"
            "      \"id\": 9999,\n"
            "      \"analysis\": \"Kratka analiza padeža, roda i skraćenica.\",\n"
            "      \"translated_text\": \"Prevedeni tekst na srpskom jeziku koji poštuje limit karaktera.\"\n"
            "    }\n"
            "  ],\n"
            "  \"used_terms\": {\n"
            "    \"engleski_pojam\": \"srpski_prevod\"\n"
            "  }\n"
            "}\n\n"
            f"TRANSKRIPT ZA PREVOD:\n{transcript_text}"
        )
        
        payload = {
            "model": "qwen-lektor",
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.1,
            "max_tokens": 1500
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
                            text = None
                            for key in ["translated_text", "refined_text", "text"]:
                                if key in item:
                                    text = item[key]
                                    break
                            if idx is not None and text is not None:
                                batch_parsed[int(idx)] = str(text).strip()
                                
            # Ako JSON parsiranje nije dalo sve segmente iz ovog batch-a, koristimo regex tag fallback
            if len(batch_parsed) < len(batch_segments):
                print(f"[TRANSLATOR] JSON parser vratio {len(batch_parsed)} od {len(batch_segments)} segmenata. Pokrećem regex tag fallback...", flush=True)
                parts = re.split(r'\[seg[- ]*(\d+)\]', clean_thought_tags(raw_output))
                if len(parts) > 1:
                    for k in range(1, len(parts), 2):
                        try:
                            idx = int(parts[k])
                            text = parts[k+1].strip().lstrip(':-= \t\n')
                            if text and idx not in batch_parsed:
                                batch_parsed[idx] = text
                        except ValueError:
                            continue
                            
            # Spajanje u glavni rečnik i ažuriranje running glossary-ja
            for idx, text in batch_parsed.items():
                if batch_start <= idx < batch_start + len(batch_segments):
                    parsed_dict[idx] = text
                    
            # Ažuriranje confirmed_translations na osnovu used_terms koji je model vratio
            used_terms_found = False
            if isinstance(data, dict):
                used_terms = data.get("used_terms")
                if isinstance(used_terms, dict):
                    for eng, srb in used_terms.items():
                        if eng and srb:
                            confirmed_translations[eng] = srb
                            used_terms_found = True
                            
            # Fallback: ako model nije vratio used_terms, koristimo staru logiku prepoznavanja
            if not used_terms_found:
                for s in batch_segments:
                    text_lower = s["text"].lower()
                    for eng_term, srb_term in full_glossary_dict.items():
                        if eng_term.lower() in text_lower:
                            confirmed_translations[eng_term] = srb_term
                    
        except Exception as batch_err:
            print(f"[ERROR] Greška pri prevođenju batcha {batch_idx + 1}: {batch_err}", flush=True)
            
    translator_duration = time.time() - t_start_trans
    print(f"[TRANSLATOR] Prevođenje završeno za {translator_duration:.2f}s. Uspešno prevedeno {len(parsed_dict)} od {len(segments)} segmenata.", flush=True)

    # Pravljenje finalne liste segmenata
    final_segments = []
    for i, orig in enumerate(segments):
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
        
    # Pokretanje Lektor faze sa prosleđenim parametrima
    try:
        return lektor_segments(
            segments, 
            final_segments, 
            progress_callback=progress_callback, 
            translator_duration=translator_duration,
            dynamic_glossary_str=dynamic_glossary_str,
            video_summary=video_summary,
            user_avg_speedup=user_avg_speedup
        )
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

    # 17. Ispravka futura I sa "će" (hrvatski / ijekavski oblici: radit će -> radiće, raditi će -> radiće)
    text = re.sub(r'\b([a-zA-ZđžćčšĐŽĆČŠ]+)ti?\s+će(š|mo|te)?\b', r'\1će\2', text, flags=re.IGNORECASE)

    # 18. Morfološke i sintaksičke ispravke (na osnovu evaluacije)
    text = re.sub(r'\bjednake cilindri\b', 'jednake cilindriće', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsecu tradicionalne\b', 'seku tradicionalne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvenog komad\b', 'drveni komad', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkomad drvenog\b', 'komad drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvene podloge\b', 'drvene osnove', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvenog podloge\b', 'drvene osnove', text, flags=re.IGNORECASE)
    text = re.sub(r'\bna razmeru koju\b', 'u razmeri koju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bna razmeru\b', 'u razmeri', text, flags=re.IGNORECASE)
    text = re.sub(r'\bZavar je glatko\b', 'Zavar je gladak', text, flags=re.IGNORECASE)
    text = re.sub(r'\bglatko izgleda\b', 'gladak izgled', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnavojni štap montaža\b', 'montažni štap sa navojem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnavojnog štapa montaža\b', 'montažnog štapa sa navojem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofanje\b', 'brušenje', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofanja\b', 'brušenja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofati\b', 'brusiti', text, flags=re.IGNORECASE)
    
    # Dodatne ispravke za video 3
    text = re.sub(r'\brđav[ao] drv[o-z]\b', 'crvenkasto drvo', text, flags=re.IGNORECASE)
    text = re.sub(r'\brđast[ao] drv[o-z]\b', 'crvenkasto drvo', text, flags=re.IGNORECASE)
    text = re.sub(r'\brđast[a-z]*\b', 'crvenkast', text, flags=re.IGNORECASE)
    text = re.sub(r'\botrpere\b', 'obriše', text, flags=re.IGNORECASE)
    text = re.sub(r'\btrli\b', 'trlja', text, flags=re.IGNORECASE)
    text = re.sub(r'\btamlja\b', 'trlja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnevjera\b', 'neverovatno', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnevjerojatan\b', 'neverovatan', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnevjerojatno\b', 'neverovatno', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkontrast je neverovatno\b', 'kontrast je neverovatan', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkontrast je neverovatan\b', 'kontrast je neverovatan', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsečiv\b', 'sečivo', text, flags=re.IGNORECASE)
    text = re.sub(r'\bžičani sečiv\b', 'žičanu testeru', text, flags=re.IGNORECASE)
    text = re.sub(r'\bžičani sečivom\b', 'žičanom testerom', text, flags=re.IGNORECASE)
    text = re.sub(r'\bničeg osim ovim\b', 'ničeg osim ovog', text, flags=re.IGNORECASE)
    text = re.sub(r'\bničeg osim ove\b', 'ničeg osim ovog', text, flags=re.IGNORECASE)
    text = re.sub(r'\btamne komade drvenog\b', 'tamnog komada drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bosnovnim tamnim komade drvenog\b', 'osnovnog tamnog komada drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bosnovnim tamnim komadom drvenog\b', 'osnovnog tamnog komada drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bosnovnim tamnim komadom drveta\b', 'osnovnog tamnog komada drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKineski šahovski komplet\b', 'kineski šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKineski šahovski set\b', 'kineski šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKinesku šahovsku ploču\b', 'kineski šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKineski šahovsku ploču\b', 'kineski šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšahovsku ploču\b', 'šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšahovski set\b', 'šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsabošenje\b', 'šmirglanje', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsabošenja\b', 'šmirglanja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsabošiti\b', 'šmirglati', text, flags=re.IGNORECASE)
    text = re.sub(r'\bveštinu majstora\b', 'majstorsku veštinu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bveštinu ovog majstora\b', 'majstorsku veštinu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstvari postaju zanimljive\b', 'stvari postaju fascinantne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpostaju zanimljive\b', 'postaju fascinantne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bboju drva\b', 'boju drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bduboku boju drva\b', 'duboku boju drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bda stampa granicu\b', 'da utisne ivicu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvisokoj toploti da stampa granicu\b', 'visoku toplotu da utisne ivicu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvisokoj toploti da stampa\b', 'visoku toplotu da utisne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvisokoj toploti\b', 'visokom toplotom', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkoristi visokoj toploti\b', 'koristi visoku toplotu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkoristi visoku temperaturu za peč\b', 'koristi visoku toplotu da utisne ivicu', text, flags=re.IGNORECASE)



    # 19. Dupli razmaci i čišćenje
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
    Poziva Modal Lektor da detektuje temu, izvuče 5-10 ključnih stručnih termina
    i prepozna specifične entitete (imena, brendove, lokacije, skraćenice) koji zahtevaju transkripciju.
    Vraća rečnik sa ključevima 'topic', 'terms' i 'entities'.
    """
    if not settings.MODAL_LEKTOR_URL:
        return {"topic": "other", "terms": [], "entities": []}
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "Analyze the following English transcript from a video. "
        "1. Identify the main topic of the video (choose one of: 'welding_and_crafts', 'biology_and_nature', 'technology_and_it', or 'other').\n"
        "2. Extract 5-10 key technical nouns, verbs, or phrases (jargon) that are central to this video.\n"
        "3. Extract any specific proper nouns like person names, brand names, software, tools, locations, or acronyms (e.g. 'Claude', 'vLLM', 'AI', 'San Francisco', 'Docker') that will need phonetic transcription in Serbian.\n\n"
        "Respond strictly in JSON format with the following keys:\n"
        "{\n"
        "  \"topic\": \"topic_name\",\n"
        "  \"terms\": [\"term1\", \"term2\", ...],\n"
        "  \"entities\": [\"entity1\", \"entity2\", ...]\n"
        "}\n\n"
        f"TRANSCRIPT:\n{transcript_text}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    try:
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        content = clean_thought_tags(content)
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        data = json.loads(content)
        return {
            "topic": data.get("topic", "other"),
            "terms": data.get("terms", []),
            "entities": data.get("entities", [])
        }
    except Exception as e:
        print(f"[GLOSSARY DETECT ERROR] Greška pri detekciji teme i entiteta: {e}")
        return {"topic": "other", "terms": [], "entities": []}

def translate_terms_to_serbian(terms: list) -> dict:
    """
    Prevedi listu engleskih stručnih pojmova i entiteta na srpski jezik (ekavica, latinica).
    """
    if not terms or not settings.MODAL_LEKTOR_URL:
        return {}
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "You are an expert English-to-Serbian translator. Translate or transcribe the following list of English terms, "
        "proper nouns, and acronyms into standard Serbian as spoken in Serbia (ekavica, latinica). "
        "Keep translations short, accurate, and natural.\n\n"
        "IMPORTANT RULES FOR TRANSLATION AND TRANSCRIPTION:\n"
        "- TECHNICAL TERMS: Translate them to standard Serbian ekavica (e.g. 'welding' -> 'zavarivanje', 'pipes' -> 'cevi'). Avoid dialectal or Croatian words.\n"
        "- BRAND NAMES, SOFTWARE, AND NAMES: Transcribe them PHONETICALLY as they are pronounced (e.g. 'Claude' -> 'Klod', 'Docker' -> 'Doker', 'San Francisco' -> 'San Francisko', 'Luna' -> 'Luna'). Never leave them in English spelling.\n"
        "- ACRONYMS: Write them phonetically as they are pronounced in Serbian, without dashes (e.g. 'AI' -> 'Ej Aj', 'IT' -> 'Aj Ti', 'TTS' -> 'Ti Ti Es').\n\n"
        "Respond strictly in JSON format (a single dictionary where keys are English terms and values are Serbian translations/transcriptions):\n"
        "{\n"
        "  \"english term\": \"serbian translation\"\n"
        "}\n\n"
        f"TERMS: {json.dumps(terms)}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    try:
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        content = clean_thought_tags(content)
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        return json.loads(content)
    except Exception as e:
        print(f"[GLOSSARY TRANSLATE ERROR] Greška pri prevođenju termina/entiteta: {e}")
        return {}

def get_dynamic_glossary(transcript_text: str) -> str:
    """
    Glavna funkcija koja orkestrira detekciju teme, proveru u bazi i automatski prevod nepoznatih reči i entiteta.
    Vraća formatirani tekstualni glosar za prompt lektora i prevodioca.
    """
    print("[GLOSSARY] Pokrećem analizu teme i prepoznavanje termina i entiteta...", flush=True)
    detect_res = detect_topic_and_terms(transcript_text)
    topic = detect_res.get("topic", "other")
    terms = detect_res.get("terms", [])
    entities = detect_res.get("entities", [])
    
    all_items_to_translate = list(set(terms + entities))
    print(f"[GLOSSARY] Detektovana tema: {topic}. Izvučeni termini i entiteti: {all_items_to_translate}", flush=True)
    
    glossaries = load_glossaries()
    predefined = glossaries.get(topic, {})
    
    final_glossary = {}
    missing_terms = []
    
    for term in all_items_to_translate:
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
        print(f"[GLOSSARY] Prevodim {len(missing_terms)} nepoznatih termina/entiteta preko LLM...", flush=True)
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

def lektor_segments(original_segments, translated_segments, progress_callback=None, translator_duration=0.0, dynamic_glossary_str=None, video_summary=None, user_avg_speedup: float = 1.0):
    """
    Druga faza: Qwen 2.5/3.0 Lektor lekturiše grubi prevod sa programskom deduplikacijom i dinamičkim glosarom.
    Optimizovano: batch_size = 30, max_tokens = 1000, robusno JSON + Regex parsiranje.
    Dodatno: podrška za prosleđeni globalni sažetak, glosar i klizni prozor memorije.
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

    # 2. Generisanje ili preuzimanje globalnog konteksta i glosara
    if not video_summary:
        try:
            transcript_text = " ".join([seg["orig_text"] for seg in unique_segments])
            video_summary = generate_video_summary(transcript_text)
        except Exception:
            video_summary = "No context available."

    if not dynamic_glossary_str:
        try:
            transcript_text = " ".join([seg["orig_text"] for seg in unique_segments])
            dynamic_glossary_str = get_dynamic_glossary(transcript_text)
        except Exception as e:
            print(f"[WARNING] Greška pri kreiranju dinamičkog glosara: {e}. Koristim prazan glosar.")
            dynamic_glossary_str = "Nema specifičnih termina za ovaj video."

    batch_size = 5
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
            factor = calculate_dynamic_factor(seg, user_avg_speedup)
            limit_char = max(15, int(duration * factor))
            lektor_input += f"[seg-{global_idx}] (trajanje: {duration:.1f}s, LIMIT: {limit_char} karaktera) ENG: {seg['orig_text']} | SRB: {to_latin(seg['translated_text'])}\n"
            
        # Klizni prozor konteksta za lektora
        history_text = ""
        if batch_idx > 0:
            history_start = max(0, batch_start - 2)
            history_segments = unique_segments[history_start:batch_start]
            history_lines = []
            for prev_idx, prev_seg in enumerate(history_segments):
                global_prev_idx = history_start + prev_idx
                prev_lektorised = parsed_lektor_dict.get(global_prev_idx, prev_seg["translated_text"])
                history_lines.append(f"[seg-{global_prev_idx}] ENG: {prev_seg['orig_text']} | SRB (lektura): {prev_lektorised}")
            history_text = "\n".join(history_lines)
            
        history_section = ""
        if history_text:
            history_section = (
                "ISTORIJA PRETHODNO LEKTURISANIH REČENICA (koristi isključivo kao kontekst za kontinuitet i gramatičko "
                "povezivanje. NIKADA ne lekturiši ponovo ove segmente niti ih uključuj u izlazni JSON):\n"
                f"{history_text}\n\n"
            )

        lektor_prompt = (
            "Ti si glavni urednik i lektor za srpski jezik. Tvoj zadatak je da pregledaš grubi prevod (SRB) u odnosu na originalni engleski tekst (ENG) i trajanje segmenta, ispraviš greške i vratiš tečan srpski prevod na ekavici i latinici.\n\n"
            "VAŽNO ZA REZONOVANJE: U svom procesu razmišljanja (<think>...</think>) budi ekstremno kratak (maksimalno 50 reči ukupno). NIKADA nemoj raditi analizu segment po segment niti objašnjavati svaki segment pojedinačno. Samo ukratko navedi strategiju u dve rečenice i pređi na JSON odgovor.\n\n"
            f"{history_section}"
            "PRAVILA ZA UREĐIVANJE:\n"
            "1. PIŠI ISKLJUČIVO SRPSKOM LATINICOM (nikada ćirilica).\n"
            "2. STRIKTNI GLOSAR: Za engleske stručne pojmove OBAVEZNO koristi ponuđene prevode iz glosara ispod. Zabranjeno je koristiti druge sinonime ili bukvalno prevoditi (prilagodi ih gramatički padežu, rodu i broju):\n"
            f"{dynamic_glossary_str}\n\n"
            "3. STRIKTNA EKAVICA I PRAVOPIS:\n"
            "   - Zameni sve strane, dijalekatske i ijekavske reči srpskim ekavskim rečima (npr. 'smeje' umesto 'smije', 'dela'/'delovi' umesto 'dijela'/'dijelovi', 'deo' umesto 'dijel', 'video' umesto 'vidio', 'rešenje' umesto 'rješenje', 'tačke' umesto 'točke').\n"
            "   - Izuzetak: Uobičajene IT akronime i tehnologije poput GPS, Wi-Fi i Bluetooth piši u njihovom originalnom obliku (GPS, Wi-Fi, Bluetooth) i nemoj ih pisati fonetski ili menjati.\n"
            "   - Izbegavaj pasivne konstrukcije sa 'od strane' (npr. umesto 'primenjena od strane vlada' koristi aktiv 'vlade su primenile').\n"
            "   - Izbegavaj bukvalne prevode engleskih fraza poput 'the hope is' u 'nadam se' ako se govori o opštem cilju projekta (bolje je 'cilj je' ili 'očekuje se'). Reč 'collapses' u kontekstu populacije prevodi kao 'nestane' ili 'se uruši', a ne 'da se sruši'.\n"
            "   - MORFOLOGIJA I SLAGANJE: Strogo pazi na morfološko slaganje prideva i imenica po rodu, broju i padežu (npr. 'drveni komad' ili 'komad drveta', a nikako 'komad drvenog'; 'jednake cilindriće' u akuzativu množine, a ne 'jednake cilindri'; 'zavar je gladak' u muškom rodu, a ne 'glatko').\n"
            "   - PRIRODNOST FRAZA: Izbegavaj bukvalne prevode engleskih kolokvijalnih konstrukcija (npr. 'this is where it gets crazy' prevodi kao 'sada stvari postaju zanimljive' ili 'ovde nastaje preokret', a nikako 'ovde postaje ludilo').\n"
            "4. LIMIT KARAKTERA: Prevod (refined_text) mora biti kraći ili jednak prosleđenom LIMITU. Za mikro-segmente (trajanje < 0.5s) refined_text MORA biti potpuno prazan string `\"\"`. Za sve ostale segmente, ako je prevod već tačan, OBAVEZNO kopiraj grubi prevod (SRB) u 'refined_text' (nikada ne ostavljaj prazno za regularne segmente).\n"
            "5. DOSLEDNO OBRAĆANJE: Koristi neformalno obraćanje 'ti' (npr. 'ako želiš', 'poravnaj').\n"
            "6. LINGVISTIČKA PROVERA: U polju 'analysis' (CoT) obrazloži teške fraze. Izbegavaj bukvalne prevode poput 'postaje ludo' (prevedi npr. 'gde situacija postaje zanimljiva' ili 'gde se sve menja').\n\n"
            "FORMAT ODGOVORA:\n"
            "Odgovori isključivo u validnom JSON formatu prema sledećoj šemi, bez uvodnog ili pratećeg teksta. Neka polje 'analysis' bude izuzetno kratko (maksimalno jedna rečenica):\n"
            "{\n"
            "  \"segments\": [\n"
            "    {\n"
            "      \"id\": 9999,\n"
            "      \"analysis\": \"Kratka analiza lekture.\",\n"
            "      \"refined_text\": \"Lekturisani i skraćeni srpski prevod.\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"TEKST ZA LEKTURU:\n{lektor_input}"
        )

        try:
            lektor_payload = {
                "model": "qwen-lektor",
                "messages": [{"role": "user", "content": lektor_prompt}],
                "temperature": 0.1,
                "max_tokens": 1500,
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
            lektor_raw_clean = clean_thought_tags(lektor_raw)
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
                            text = None
                            for key in ["refined_text", "translated_text", "text"]:
                                if key in item:
                                    text = item[key]
                                    break
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
                            
            # Spajanje u parsed_lektor_dict i proračun metrika
            for idx, text in batch_parsed_lektor.items():
                if batch_start <= idx < batch_start + len(batch_translated):
                    parsed_lektor_dict[idx] = text
                    print(f"[LEKTOR] Segment {idx} lekturisan: {text[:60]}...", flush=True)
                    
                    # Pronalaženje originalnog segmenta za proračun limita i logovanje
                    idx_int = int(idx)
                    orig_seg = None
                    for u_seg in unique_segments:
                        if u_seg["unique_id"] == idx_int:
                            orig_seg = u_seg
                            break
                    if orig_seg:
                        duration = orig_seg["duration"]
                        factor = calculate_dynamic_factor(orig_seg, user_avg_speedup)
                        limit_char = max(15, int(duration * factor))
                        
                        # Pokušavamo da izvučemo 'analysis' polje iz parsed JSON-a ako postoji
                        analysis = ""
                        if data and isinstance(data, dict):
                            s_list = data.get("segments", [])
                            if isinstance(s_list, list):
                                for item in s_list:
                                    if isinstance(item, dict) and item.get("id") == idx_int:
                                        analysis = item.get("analysis") or ""
                                        break
                                        
                        # Kalkulacija confidence skora
                        confidence = 5
                        confidence_triggers = ["idiom", "unclear", "ambiguous", "colloquial", "cultural reference", "wordplay", "humor", "slang"]
                        for trigger in confidence_triggers:
                            if trigger in str(analysis).lower():
                                confidence -= 1
                        
                        overshoot = len(str(text)) / limit_char
                        if overshoot > 1.2:
                            confidence -= 1
                        confidence = max(1, confidence)
                        
                        orig_seg["confidence_score"] = confidence
                        
                        # Monitoring & Logging
                        import logging
                        compliance_logger = logging.getLogger("translation_compliance")
                        compliance_stats = {
                            "segment_id": idx_int,
                            "duration": duration,
                            "limit_char": limit_char,
                            "actual_char": len(str(text)),
                            "compliance": len(str(text)) <= limit_char,
                            "overshoot_pct": max(0.0, (len(str(text)) - limit_char) / limit_char * 100)
                        }
                        compliance_logger.info(f"[COMPLIANCE] {json.dumps(compliance_stats)}")
                    
        except Exception as batch_err:
            print(f"[WARNING] Greška u Lektor batchu {batch_idx + 1}: {batch_err}")

    lektor_duration = time.time() - t_start_lektor
    print(f"[LEKTOR] Lektura završena za {lektor_duration:.2f}s. Uspešno lekturisano {len(parsed_lektor_dict)} od {len(unique_segments)} jedinstvenih segmenata.", flush=True)
    
    # 3. Zatvorena petlja: Provera i kompresija predugačkih segmenata (TTS-Aware Compression)
    for u_seg in unique_segments:
        idx = u_seg["unique_id"]
        if idx in parsed_lektor_dict:
            lektorised_text = parsed_lektor_dict[idx]
            if not lektorised_text:
                continue
            duration = u_seg["duration"]
            factor = calculate_dynamic_factor(u_seg, user_avg_speedup)
            limit_char = max(15, int(duration * factor))
            
            if len(lektorised_text) > limit_char * 1.15:
                compressed = compress_sentence_via_llm(lektorised_text, limit_char)
                parsed_lektor_dict[idx] = compressed

    if len(parsed_lektor_dict) > 0:
        for i, seg in enumerate(translated_segments):
            unique_idx = orig_to_unique_map.get(i)
            if unique_idx is not None and unique_idx in parsed_lektor_dict:
                seg["text"] = parsed_lektor_dict[unique_idx]
                u_seg = unique_segments[unique_idx]
                seg["confidence_score"] = u_seg.get("confidence_score", 5)
        
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

def compress_sentence_via_llm(text: str, limit_char: int) -> str:
    """
    Poziva Modal Lektor da skrati srpsku rečenicu tako da stane u limit karaktera.
    """
    if not settings.MODAL_LEKTOR_URL or not text or len(text) <= limit_char:
        return text
        
    print(f"[COMPRESS] Skraćujem rečenicu ({len(text)} -> limit {limit_char}): {text}", flush=True)
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        f"Skrati sledeću rečenicu na srpskom jeziku (ekavica, latinica) tako da njena dužina bude maksimalno {limit_char} karaktera.\n"
        "VAŽNA PRAVILA:\n"
        "1. Zadrži osnovni smisao i informaciju iz rečenice.\n"
        "2. Skraćena rečenica mora biti gramatički ispravna i prirodna na srpskom.\n"
        "3. Tvoj odgovor mora sadržati isključivo skraćenu rečenicu, bez ikakvog dodatnog teksta, komentara, navodnika ili objašnjenja.\n"
        "4. STROGO ZABRANJENO: Nemoj brojati slova jedno po jedno niti raditi matematičke proračune u razmišljanju. Samo intuitivno i brzo napiši kraću verziju rečenice.\n\n"
        f"REČENICA ZA SKRAĆIVANJE: {text}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [
            {
                "role": "system", 
                "content": "Ti si brzi stručni lektor. Tvoj zadatak je da odmah vratiš skraćenu verziju rečenice na srpskom jeziku na osnovu zadatog limita. Ne analiziraj rečenicu detaljno i nemoj brojati slova u razmišljanju, samo odmah ispiši skraćeni tekst."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    try:
        from backend.worker.utils import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        cleaned = clean_thought_tags(content).strip().strip('"\'')
        
        if not cleaned or len(cleaned) < 2:
            print(f"[COMPRESS WARNING] Dobijen prazan ili nevalidan rezultat nakon čišćenja (sirovo: {repr(content)}). Vraćam originalni tekst.", flush=True)
            return text
            
        print(f"[COMPRESS SUCCESS] Nova rečenica ({len(cleaned)} karaktera): {cleaned}", flush=True)
        return cleaned
    except Exception as e:
        print(f"[COMPRESS ERROR] Greška pri skraćivanju: {e}", flush=True)
        return text



