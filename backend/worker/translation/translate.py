import time
import os
import re
import cv2
import json
import base64
from typing import List

from backend.core.config import settings

# Uvoženje iz lokalnih modula
from .masking import mask_untranslatable, unmask_text, mask_segment_pair
from .transliter import to_latin
from .dialect import clean_translation_text, clean_thought_tags
from .glossary import parse_glossary_to_dict
from .qe import get_comet_kiwi_score, check_negation_preservation, get_llm_judge_score

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    t1 = re.sub(r'[^\w\s]', '', text1.lower()).split()
    t2 = re.sub(r'[^\w\s]', '', text2.lower()).split()
    set1 = set(t1)
    set2 = set(t2)
    if not set1 or not set2:
        return 0.0
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union)

def fix_json_newlines(json_str: str) -> str:
    if not json_str:
        return ""
    def repl(match):
        return match.group(0).replace('\n', '\\n')
    return re.sub(r'"(?:[^"\\]|\\.)*"', repl, json_str)

def repair_truncated_json(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text.endswith(','):
        text = text[:-1].strip()
    unescaped_quotes = 0
    in_escape = False
    for char in text:
        if char == '\\':
            in_escape = not in_escape
        elif char == '"':
            if not in_escape:
                unescaped_quotes += 1
            in_escape = False
        else:
            in_escape = False
    if unescaped_quotes % 2 != 0:
        text += '"'
    if text.endswith(','):
        text = text[:-1].strip()
    stack = []
    in_string = False
    in_escape = False
    for char in text:
        if char == '\\':
            if in_string:
                in_escape = not in_escape
            else:
                in_escape = False
        elif char == '"':
            if not in_escape:
                in_string = not in_string
            in_escape = False
        elif not in_string:
            if char in ('{', '['):
                stack.append(char)
            elif char in ('}', ']'):
                if stack:
                    last = stack[-1]
                    if (char == '}' and last == '{') or (char == ']' and last == '['):
                        stack.pop()
        else:
            in_escape = False
    for open_char in reversed(stack):
        if open_char == '{':
            text += '}'
        elif open_char == '[':
            text += ']'
    return text

def extract_and_parse_json(text: str):
    if not text:
        return None
    text = clean_thought_tags(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        fixed_text = fix_json_newlines(text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        json_content = match.group(1)
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            try:
                return json.loads(fix_json_newlines(json_content))
            except json.JSONDecodeError:
                pass
    try:
        repaired = repair_truncated_json(text)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    try:
        repaired = repair_truncated_json(fix_json_newlines(text))
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    start_arr = text.find('[')
    if start_arr != -1:
        json_content = text[start_arr:]
        end_arr = text.rfind(']')
        if end_arr != -1 and end_arr > start_arr:
            json_content = text[start_arr:end_arr+1]
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            try:
                return json.loads(repair_truncated_json(json_content))
            except json.JSONDecodeError:
                try:
                    return json.loads(repair_truncated_json(fix_json_newlines(json_content)))
                except json.JSONDecodeError:
                    pass
    start_obj = text.find('{')
    if start_obj != -1:
        json_content = text[start_obj:]
        end_obj = text.rfind('}')
        if end_obj != -1 and end_obj > start_obj:
            json_content = text[start_obj:end_obj+1]
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            try:
                return json.loads(repair_truncated_json(json_content))
            except json.JSONDecodeError:
                try:
                    return json.loads(repair_truncated_json(fix_json_newlines(json_content)))
                except json.JSONDecodeError:
                    pass
    return None

def group_segments_into_sentences(segments: list, max_group_duration: float = 12.0) -> list:
    """
    Grupiše susedne segmente u rečenice na osnovu završne interpunkcije.
    Vraća listu grupa, gde je svaka grupa lista rečnika segmenata.
    Grupa se prekida ako se segment završava sa ., !, ? ili ... ili ako trajanje grupe prelazi max_group_duration.
    """
    groups = []
    current_group = []
    
    for seg in segments:
        current_group.append(seg)
        text = seg.get("text", "").strip()
        group_duration = current_group[-1]["end"] - current_group[0]["start"]
        
        # Provera da li se tekst završava interpunkcijom
        ends_with_punctuation = any(text.endswith(p) for p in ['.', '!', '?', '...'])
        
        if ends_with_punctuation or group_duration >= max_group_duration:
            groups.append(current_group)
            current_group = []
            
    if current_group:
        groups.append(current_group)
        
    return groups

def split_translated_text(translated_text: str, original_segments: list) -> list:
    """
    Deli prevedeni tekst rečenice nazad na originalne segmente.
    Koristi udeo dužine karaktera originalnih segmenata za određivanje gde seći reči.
    """
    k = len(original_segments)
    if k == 0:
        return []
    if k == 1:
        return [translated_text]
        
    words = translated_text.split()
    if not words:
        return [""] * k
        
    # Računanje dužina originalnih tekstova
    orig_lens = [len(s.get("text", "").strip()) for s in original_segments]
    total_orig_len = sum(orig_lens)
    if total_orig_len == 0:
        # Ravnomerna podela po broju reči
        words_per_seg = max(1, len(words) // k)
        parts = []
        for i in range(k):
            if i == k - 1:
                parts.append(" ".join(words[i*words_per_seg:]))
            else:
                parts.append(" ".join(words[i*words_per_seg:(i+1)*words_per_seg]))
        return parts

    # Kumulativni udeli
    cum_weights = []
    running_sum = 0
    for length in orig_lens:
        running_sum += length
        cum_weights.append(running_sum / total_orig_len)
        
    # Izračunavanje kumulativnih dužina reči (sa uključenim razmacima)
    words_cum_lens = []
    current_len = 0
    for w in words:
        if current_len > 0:
            current_len += 1  # Razmak
        current_len += len(w)
        words_cum_lens.append(current_len)
        
    total_translated_len = current_len
    
    # Ciljne kumulativne dužine
    target_cum_lens = [w * total_translated_len for w in cum_weights]
    
    # Pronalaženje optimalnih tačaka podele (indeksa reči)
    splits = []
    for j in range(k - 1):
        target = target_cum_lens[j]
        best_idx = 0
        min_diff = float('inf')
        for idx, w_len in enumerate(words_cum_lens):
            diff = abs(w_len - target)
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
        splits.append(best_idx)
        
    # Sastavljanje delova na osnovu splits
    parts = []
    start_idx = 0
    for j in range(k):
        if j == k - 1:
            end_idx = len(words)
        else:
            end_idx = splits[j] + 1
            if end_idx <= start_idx:
                end_idx = start_idx + 1  # Barem jedna reč po segmentu
            if end_idx > len(words) - (k - 1 - j):
                end_idx = len(words) - (k - 1 - j)
                
        part_text = " ".join(words[start_idx:end_idx])
        parts.append(part_text)
        start_idx = end_idx
        
    return parts

def select_best_translation_via_llama(english_text: str, candidates: List[str]) -> str:
    """
    Poziva Llama 3.1 8B da izabere prirodniji i tačniji prevod od ponuđenih kandidata.
    """
    if not settings.MODAL_LEKTOR_URL or not candidates:
        return candidates[0] if candidates else ""
    if len(candidates) == 1:
        return candidates[0]
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    
    prompt = (
        "Ti si stručni žiri i sudija za srpski jezik (ekavica, latinica).\n"
        "Tvoj zadatak je da odabereš bolji, prirodniji i tačniji prevod sa engleskog na srpski.\n\n"
        f"Originalni engleski tekst: \"{english_text}\"\n"
        f"Kandidat A: \"{candidates[0]}\"\n"
        f"Kandidat B: \"{candidates[1]}\"\n\n"
        "Uputstvo za odabir:\n"
        "- Izaberi onaj prevod koji zvuči prirodnije, tečnije i naratorski na srpskom jeziku.\n"
        "- Odabrani prevod mora poštovati sva stilska pravila (brojevi slovima, bez ijekavice, latinica).\n"
        "- Vrati ISKLJUČIVO odabrani srpski tekst prevoda direktno, bez ikakvih uvodnih reči, navodnika, obrazloženja ili objašnjenja.\n"
        "- STROGO ZABRANJENO: Nemoj pisati <think> ili <thought> tagove i bilo kakvo razmišljanje. Odmah ispiši odabrani prevod."
    )
    
    payload = {
        "model": "mistral-translator",
        "messages": [
            {
                "role": "system",
                "content": "Ti si sudija za odabir najboljeg srpskog prevoda. Vrati isključivo odabrani prevod direktno."
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
        from backend.worker.translator import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=45)
        selected = res["choices"][0]["message"]["content"].strip().strip('"\'')
        cleaned = clean_thought_tags(selected).strip()
        print(f"[LLAMA SELECT BEST] Između '{candidates[0]}' i '{candidates[1]}', Llama 8B je izabrao: '{cleaned}'", flush=True)
        if cleaned:
            return cleaned
    except Exception as e:
        print(f"[LLAMA SELECT ERROR] Greška pri odabiru prevoda: {e}", flush=True)
        raise e


def retranslate_with_self_critique(english_text: str, bad_translation: str, feedback_hint: str) -> str:
    if not settings.MODAL_LEKTOR_URL:
        return bad_translation
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    
    prompt = (
        "Ti si stručni prevodilac za srpski jezik (ekavica). Prethodni prevod ima greške.\n"
        f"Originalni engleski tekst: {english_text}\n"
        f"Prethodni loš prevod: {bad_translation}\n"
        f"Uočene greške / Uputstvo za ispravku: {feedback_hint}\n\n"
        "Tvoj zadatak je da pružiš novi, ispravljeni prevod na srpskom jeziku (ekavica, latinica) koji:\n"
        "1. U potpunosti rešava sve uočene greške i prati uputstvo.\n"
        "2. Zvuči prirodno, koristi srpske idiome i ispravne gramatičke oblike.\n"
        "3. Piše sve brojeve i procente slovima (npr. 'dvesta', 'pet posto').\n"
        "4. Piše strana imena i brendove fonetski (npr. 'Klod', 'Doker') osim GPS, Wi-Fi, Bluetooth.\n"
        "5. Tvoj odgovor mora sadržati isključivo ispravljeni srpski tekst prevoda, bez ikakvih uvodnih rečenica, objašnjenja, navodnika ili think tagova.\n"
        "6. STROGO JE ZABRANJENO generisanje <think> ili <thought> tagova i bilo kakvog razmišljanja. Samo odmah vrati ispravljeni prevod direktno.\n"
    )
    
    payload = {
        "model": "mistral-translator",
        "messages": [
            {
                "role": "system",
                "content": "Ti si stručni prevodilac i lektor. Vrati isključivo ispravljeni prevod na srpski jezik bez ikakvog dodatnog teksta ili komentara. STROGO JE ZABRANJENO generisanje <think> ili <thought> tagova i bilo kakvog razmišljanja. Samo odmah vrati ispravljeni prevod direktno."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "n": 2,
        "max_tokens": 1500
    }
    
    try:
        from backend.worker.translator import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        choices = res.get("choices", [])
        candidates = []
        for choice in choices:
            c_text = choice["message"]["content"].strip()
            cleaned = clean_thought_tags(c_text).strip().strip('"\'')
            if cleaned:
                candidates.append(cleaned)
                
        if candidates:
            best_translation = select_best_translation_via_llama(english_text, candidates)
            print(f"[SELF-CRITIQUE SUCCESS] Prethodni: {bad_translation} -> Izabrani: {best_translation}", flush=True)
            return best_translation
    except Exception as e:
        print(f"[SELF-CRITIQUE ERROR] Greška prilikom re-prevoda sa samokritikom: {e}", flush=True)
        
    return bad_translation

def compress_sentence_via_llm(text: str, limit_char: int) -> str:
    """
    Poziva Modal Lektor (Mistral-Small) da skrati srpsku rečenicu tako da stane u limit karaktera.
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
        "3. Tvoj odgovor mora sadržati isključivo skraćenu rečenicu, bez ikakvog dodatnog teksta, komentara, navodnika, objašnjenja ili think tagova.\n"
        "4. STROGO ZABRANJENO: Nemoj generisati nikakvo razmišljanje, obrazloženje ili <think> tag. Samo odmah ispiši skraćeni tekst.\n"
        "5. Ukoliko je limit karaktera prekratak da bi se zadržao ceo smisao, izostavi manje bitne detalje ili zadrži samo ključne reči.\n\n"
        f"REČENICA ZA SKRAĆIVANJE: {text}"
    )
    
    payload = {
        "model": "mistral-translator",
        "messages": [
            {
                "role": "system", 
                "content": "Ti si brzi stručni lektor. Tvoj zadatak je da odmah vratiš skraćenu verziju rečenice na srpskom jeziku na osnovu zadatog limita. STROGO JE ZABRANJENO generisanje <think> ili <thought> tagova i bilo kakvog razmišljanja. Samo odmah ispiši skraćenu rečenicu direktno."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
        "enable_thinking": False
    }
    
    try:
        from backend.worker.translator import call_modal_endpoint
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
        # Kodiranje frejma u JPEG -> Base64
        _, buffer = cv2.imencode('.jpg', frame)
        b64_str = base64.b64encode(buffer).decode('utf-8')
        frames_b64.append(b64_str)

    cap.release()
    return frames_b64

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

def translate_segments(segments: list, video_path: str = None, progress_callback=None, user_avg_speedup: float = 1.0, skip_lektor: bool = False, skip_gating: bool = False, skip_deduplication: bool = False, project_id: str = None) -> dict:
    """
    Poziva Modal Serverless Lektor (Qwen3-32B) za tekstualni prevod visoke tačnosti.
    Optimizovano: bez slika, bez hladnog starta na A10G, batch size = 30.
    Uvedeni: grupisanje segmenata u logičke rečenice (Sentence-level Re-segmentation),
             hibridni LLM-as-a-Judge gating i iterativna samokritika (Multi-turn Critique).
    """
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

    # Grupisanje segmenata u logičke rečenice (Sentence-level Re-segmentation)
    grouped_sentences = group_segments_into_sentences(segments, max_group_duration=12.0)
    print(f"[TRANSLATOR] Pokrećem prevođenje {len(segments)} segmenata grupisana u {len(grouped_sentences)} rečenica.", flush=True)
    t_start_trans = time.time()

    # Učitavanje RAG (Translation Memory) i Wiki pravila iz baze
    user_id = None
    tm_examples = []
    wiki_rules_str = ""
    if project_id:
        try:
            from backend.core.database import SessionLocal
            from backend.core.models import Project, TranslationMemory, WikiRule
            db = SessionLocal()
            proj = db.query(Project).filter(Project.id == project_id).first()
            if proj:
                user_id = str(proj.user_id)
                # Učitavamo Translation Memory
                tm_examples = db.query(TranslationMemory).filter(TranslationMemory.user_id == user_id).all()
                print(f"[TRANSLATOR RAG] Učitano {len(tm_examples)} Translation Memory zapisa za korisnika {user_id}", flush=True)
                
                # Učitavamo Wiki pravila
                rules = db.query(WikiRule).filter(
                    (WikiRule.user_id == user_id) | WikiRule.is_global
                ).all()
                if rules:
                    wiki_lines = []
                    for r in rules:
                        wiki_lines.append(f"### {r.title}\n{r.content}")
                    wiki_rules_str = "DODATNA STILSKA I BREND PRAVILA (WIKI):\n" + "\n\n".join(wiki_lines)
                    print(f"[TRANSLATOR WIKI] Učitano {len(rules)} Wiki pravila za korisnika {user_id}", flush=True)
            db.close()
        except Exception as e:
            print(f"[TRANSLATOR RAG/WIKI ERROR] Greška pri učitavanju baze: {e}", flush=True)
    
    # 1. Generisanje globalnog sažetka i glosara za ceo video
    try:
        from backend.worker.translator import generate_video_summary, get_dynamic_glossary
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

    # JSON šema za structured output rečenica (ostaje ista, samo što se ID-jevi odnose na rečenice)
    translator_schema = {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "translated_text": {"type": "string"},
                        "used_terms": {
                            "type": "object",
                            "description": "Dictionary of English terms to used Serbian translations from the glossary"
                        }
                    },
                    "required": ["id", "translated_text"]
                }
            }
        },
        "required": ["segments"]
    }

    # 2. Prevođenje u batch-ovima (batch size = 25 rečenica, sa dinamičkim smanjenjem ako premaši tokene)
    batch_size = 25
    final_segments = []
    
    # Mapiramo maske za rečenice kako bismo znali kako da ih odmaskiramo
    batch_masks_map = {}

    batch_start = 0
    while batch_start < len(grouped_sentences):
        # Očuvanje konteksta preko sliding window-a (poslednje 2 rečenice iz prethodnog batch-a)
        context_history_str = ""
        if batch_start > 0:
            history_sentences = []
            for prev_group in grouped_sentences[max(0, batch_start - 2):batch_start]:
                prev_sent = " ".join([s["text"].strip() for s in prev_group if s.get("text")])
                history_sentences.append(prev_sent)
            context_history_str = "CONTEXT_HISTORY (READ-ONLY, DO NOT TRANSLATE):\n" + "\n".join([f"- {s}" for s in history_sentences])

        # Dinamičko prilagođavanje veličine batch-a da se ne prekorači 4096 tokena (~15000 karaktera)
        current_batch_size = batch_size
        while current_batch_size > 1:
            batch_end = min(batch_start + current_batch_size, len(grouped_sentences))
            batch = grouped_sentences[batch_start:batch_end]
            
            # Formiranje testnog unosa za batch rečenica
            formatted_batch_list = []
            for i, group in enumerate(batch):
                global_idx = batch_start + i
                sentence_text = " ".join([s["text"].strip() for s in group if s.get("text")])
                masked_text, _ = mask_untranslatable(sentence_text)
                char_limit = 0
                for s in group:
                    duration = s["end"] - s["start"]
                    char_limit += int(duration * calculate_dynamic_factor(s, user_avg_speedup))
                char_limit = max(15, char_limit)
                formatted_batch_list.append(f"[Sentence {global_idx}] (Limit: {char_limit} karaktera) ENG: {masked_text}")
            batch_input_str = "\n".join(formatted_batch_list)
            
            # Procena dužine celog prompta
            test_prompt_len = len(context_history_str) + len(batch_input_str) + len(video_summary) + len(dynamic_glossary_str)
            if test_prompt_len < 14000:
                break
            else:
                # Smanjujemo batch size za pola ako je prompt predugačak
                new_size = max(1, current_batch_size // 2)
                print(f"[TRANSLATOR WARNING] Prompt je predugačak ({test_prompt_len} karaktera). Smanjujem sub-batch sa {current_batch_size} na {new_size}", flush=True)
                current_batch_size = new_size

        batch_end = min(batch_start + current_batch_size, len(grouped_sentences))
        batch = grouped_sentences[batch_start:batch_end]
        
        print(f"[TRANSLATOR] Pokrećem batch rečenica od {batch_start} do {batch_end - 1} (veličina batch-a: {len(batch)})...", flush=True)
        if progress_callback:
            progress_callback(detail=f"Prevodim rečenice {batch_start}-{batch_end - 1}... ⏳")

        # Priprema rečenica za slanje uz maskiranje Wi-Fi, GPS, Bluetooth i drugih entiteta
        formatted_batch_list = []
        for i, group in enumerate(batch):
            global_idx = batch_start + i
            
            # Spajamo originalni tekst svih segmenata u grupi u jednu rečenicu
            sentence_text = " ".join([s["text"].strip() for s in group if s.get("text")])
            masked_text, masks = mask_untranslatable(sentence_text)
            batch_masks_map[global_idx] = masks
            
            # Računanje dinamičkog limita karaktera za grupu kao zbir limita njenih segmenata
            char_limit = 0
            for s in group:
                duration = s["end"] - s["start"]
                char_limit += int(duration * calculate_dynamic_factor(s, user_avg_speedup))
            char_limit = max(15, char_limit)
            
            formatted_batch_list.append(
                f"[Sentence {global_idx}] (Limit: {char_limit} karaktera) ENG: {masked_text}"
            )
        batch_input_str = "\n".join(formatted_batch_list)

        # Generisanje trenutnog glossary konteksta
        current_glossary_lines = []
        for eng, srb in full_glossary_dict.items():
            if eng in confirmed_translations:
                current_glossary_lines.append(f'- "{eng}" -> "{confirmed_translations[eng]}" (potvrđeno)')
            else:
                current_glossary_lines.append(f'- "{eng}" -> "{srb}"')
        current_glossary_str = "\n".join(current_glossary_lines) if current_glossary_lines else "Nema termina."

        # RAG pretraga za ceo batch
        rag_context_lines = []
        seen_tm_ids = set()
        if user_id and tm_examples:
            try:
                from backend.services.embedding import embedding_service
                for group in batch:
                    sentence_text = " ".join([s["text"].strip() for s in group if s.get("text")])
                    sentence_emb = embedding_service.get_embedding(sentence_text)
                    if sentence_emb:
                        batch_similar = []
                        for tm in tm_examples:
                            if tm.id in seen_tm_ids:
                                continue
                            sim = embedding_service.calculate_cosine_similarity(sentence_emb, tm.embedding)
                            if sim >= 0.80:
                                batch_similar.append((sim, tm))
                        # Uzimamo do 2 najsličnija za svaku rečenicu da ne opteretimo prompt
                        batch_similar = sorted(batch_similar, key=lambda x: x[0], reverse=True)[:2]
                        for sim, tm in batch_similar:
                            seen_tm_ids.add(tm.id)
                            rag_context_lines.append(f'- ENG: "{tm.source_text}" -> SRB: "{tm.target_text}" (sličnost: {sim:.2f})')
            except Exception as e:
                print(f"[TRANSLATOR RAG ERROR] Greška u RAG pretrazi: {e}", flush=True)

        rag_context_str = ""
        if rag_context_lines:
            rag_context_str = "PRETHODNI PREVODI IZ KORISNIČKE MEMORIJE (RAG):\n" + "\n".join(rag_context_lines)

        # Formiranje prompta za prevođenje
        system_prompt = (
            "You are an expert video translation system. Translate the English transcript sentences to Serbian.\n"
            "Prevodi kao da si iskusni sinhronizator. Rečenice neka zvuče kao da ih izgovara profesionalni voditelj emisije ili narator, a ne profesor lingvistike. Koristi kolokvijalne i prirodne fraze gde god je to adekvatno (npr. 'naravno' umesto 'prirodno', 'evo' umesto 'ovde'), prilagođavajući red reči duhu srpskog govornog jezika.\n"
            "STRICT RULES FOR SERBIAN TRANSLATION:\n"
            "1. Language & Script: Use standard Serbian language in Latin script.\n"
            "2. Dialect: Use strictly Serbian ekavica (e.g. 'deo', 'rešenje', 'promena', 'gde', 'uvek', 'sprečiti'). Do NOT use ijekavica or Croatian regionalisms.\n"
            "3. Tone: Use strictly informal singular address 'ti' (e.g. 'ako želiš', 'poravnaj', 'pogledaj'). Avoid formal address.\n"
            "4. Grammar & Morphology: Strogo vodi računa o morfološkoj tačnosti srpskog jezika. Padežni oblici imenica, prideva i zamenica moraju biti gramatički besprekorni.\n"
            "5. Verb Tenses: Glagolska vremena moraju biti verno i prirodno prenesena. Nemoj koristiti bukvalan prevod engleskih vremena ako zvuči neprirodno na srpskom.\n"
            "6. Hallucinations: Nemoj izmišljati reči (halucinirati). Ako za neki engleski termin ne postoji direktan prevod, koristi opšteprihvaćeni stručni termin u srpskom jeziku.\n"
            "7. Numbers: Write all numbers, years, and percentages strictly in words (e.g. 'dve hiljade dvadeset šesta', 'pet posto'). Never output digits.\n"
            "8. Word limits: Do NOT exceed the character limit specified for each sentence. If you exceed the limit, the speech synthesizer will run out of time.\n"
            "9. Entity & Variable Preservation: Keep placeholder tags like [ENTITY_0], [CODE_1], [URL_0] exactly as they are. Zadrži nepromenjenim sve programske varijable (npr. {user}, {date}), HTML tagove i specijalne karaktere.\n"
            "10. Phonetic names: Write foreign names and brands phonetically (e.g. 'Klod', 'OpenEjAj'). Exceptions: IT acronyms GPS, Wi-Fi, and Bluetooth must remain in original English.\n"
            "11. STROGO ZABRANJENO: Nemoj generisati nikakvo razmišljanje, obrazloženje ili <think>/<thought> tagove. Samo odmah vrati JSON odgovor direktno.\n\n"
            "Respond strictly in JSON format matching the schema."
        )
        if wiki_rules_str:
            system_prompt += f"\n\n{wiki_rules_str}"

        user_prompt = ""
        if context_history_str:
            user_prompt += f"{context_history_str}\n\n"
        user_prompt += (
            f"GLOBAL VIDEO SUMMARY FOR CONTEXT:\n{video_summary}\n\n"
            f"STRIKTNI PREDLOŽENI GLOSAR ZA OVAJ BATCH:\n{current_glossary_str}\n\n"
        )
        if rag_context_str:
            user_prompt += f"{rag_context_str}\n\n"
        user_prompt += (
            "SENTENCES TO TRANSLATE:\n"
            f"{batch_input_str}\n\n"
            "Translate each sentence, strictly respect the character limits, do NOT think or write <think>, and output the JSON object directly."
        )

        url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": "mistral-translator",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
            "guided_json": translator_schema
        }

        # Provera active_lora_path iz Redisa za Blue-Green deployment
        try:
            import redis
            r_client = redis.Redis.from_url(settings.REDIS_URL)
            lora_bytes = r_client.get("active_lora_path")
            if lora_bytes:
                active_lora_path = lora_bytes.decode("utf-8")
                payload["lora_path"] = active_lora_path
                print(f"[BLUE-GREEN] Dodat active_lora_path u payload: {active_lora_path}", flush=True)
        except Exception as e:
            print(f"[BLUE-GREEN WARNING] Greška pri dobavljanju active_lora_path: {e}", flush=True)

        try:
            from backend.worker.translator import call_modal_endpoint
            res = call_modal_endpoint(url=url, payload=payload)
            content = res["choices"][0]["message"]["content"].strip()
            
            data = extract_and_parse_json(content)
            if not data:
                print(f"[TRANSLATOR DEBUG ERROR] Sadržaj koji nije mogao biti parsiran:\n{repr(content)}", flush=True)
                raise ValueError("Nije uspelo parsiranje niti popravljanje JSON-a.")
        except Exception as e:
            print(f"[TRANSLATOR BATCH ERROR] Greška pri prevođenju batch-a {batch_start}: {e}. Koristim fallback.", flush=True)
            data = {"segments": []}

        # Parsiranje rezultata i post-procesiranje (gating, multi-turn self-critique)
        parsed_dict = {}
        
        print(f"[TRANSLATOR DEBUG DATA] Parsirani podaci za batch {batch_start}:\n{json.dumps(data, indent=2, ensure_ascii=False)}", flush=True)
        
        segments_list = []
        if isinstance(data, dict):
            for key in ["segments", "translations", "sentences", "results"]:
                if key in data and isinstance(data[key], list):
                    segments_list = data[key]
                    break
            if not segments_list:
                for val in data.values():
                    if isinstance(val, list):
                        segments_list = val
                        break
        elif isinstance(data, list):
            segments_list = data
            
        if segments_list:
            for idx, item in enumerate(segments_list):
                if not isinstance(item, dict):
                    continue
                
                translated_val = None
                for key in ["translated_text", "translated", "text", "translation", "refined_text"]:
                    if key in item:
                        translated_val = item[key]
                        break
                
                if not translated_val:
                    continue
                
                # 1. Mapiranje preko ID-ja
                id_val = item.get("id")
                if id_val is not None:
                    try:
                        parsed_dict[int(id_val)] = str(translated_val)
                        continue
                    except ValueError:
                        pass
                
                # 2. Mapiranje preko originalnog teksta
                original_val = None
                for key in ["original_text", "original", "english", "orig"]:
                    if key in item:
                        original_val = item[key]
                        break
                        
                if original_val:
                    best_match_idx = -1
                    best_sim = 0.0
                    for b_idx, group in enumerate(batch):
                        sentence_orig = " ".join([s["text"].strip() for s in group if s.get("text")])
                        sim = calculate_jaccard_similarity(original_val, sentence_orig)
                        if sim > best_sim and sim > 0.6:
                            best_sim = sim
                            best_match_idx = b_idx
                    if best_match_idx != -1:
                        global_idx = batch_start + best_match_idx
                        parsed_dict[global_idx] = str(translated_val)
                        continue
                
                # 3. Fallback: mapiranje po redosledu
                if len(segments_list) == len(batch):
                    global_idx = batch_start + idx
                    parsed_dict[global_idx] = str(translated_val)
                    
        # 4. Dodatni fallback ako fale neki ID-jevi a dužine se poklapaju
        if len(parsed_dict) < len(batch) and len(segments_list) == len(batch):
            for idx, item in enumerate(segments_list):
                global_idx = batch_start + idx
                if global_idx not in parsed_dict and isinstance(item, dict):
                    for key in ["translated_text", "translated", "text", "translation", "refined_text"]:
                        if key in item:
                            parsed_dict[global_idx] = str(item[key])
                            break

        # Paralelna prva validacija i pozivanje sudije (Faza 4)
        from concurrent.futures import ThreadPoolExecutor
        
        batch_evals = []
        for idx, group in enumerate(batch):
            global_idx = batch_start + idx
            raw_trans = parsed_dict.get(global_idx, "").strip()
            
            # Spojeni originalni tekst rečenice
            orig_text = " ".join([s["text"].strip() for s in group if s.get("text")])
            
            if not raw_trans:
                print(f"[WARNING] Rečenica {global_idx} nema prevod. Koristim originalni tekst kao fallback.", flush=True)
                raw_trans = orig_text

            # Odmaskiravanje i deterministička ispravka ijekavice pre provere
            unmasked_text = unmask_text(raw_trans, batch_masks_map[global_idx])
            
            # 1. Brza provera negacije i CometKiwi QE skora
            negation_ok = check_negation_preservation(orig_text, unmasked_text)
            qe_score = get_comet_kiwi_score(orig_text, unmasked_text)
            
            char_limit = 0
            for s in group:
                duration = s["end"] - s["start"]
                char_limit += int(duration * calculate_dynamic_factor(s, user_avg_speedup))
            char_limit = max(15, char_limit)
            
            batch_evals.append({
                "global_idx": global_idx,
                "group": group,
                "orig_text": orig_text,
                "unmasked_text": unmasked_text,
                "negation_ok": negation_ok,
                "qe_score": qe_score,
                "char_limit": char_limit,
                "judge_score": 5.0,
                "judge_errors": [],
                "judge_explanation": ""
            })
            
        # Nalazimo sumnjive koji zahtevaju sudiju
        sumnjivi_evals = [e for e in batch_evals if not skip_gating and (not e["negation_ok"] or e["qe_score"] < 0.85)]
        
        if sumnjivi_evals:
            print(f"[PARALLEL LLM JUDGE] Pokrećem paralelno suđenje za {len(sumnjivi_evals)} rečenica...", flush=True)
            with ThreadPoolExecutor(max_workers=len(sumnjivi_evals)) as executor:
                futures = {
                    executor.submit(get_llm_judge_score, e["orig_text"], e["unmasked_text"], limit_char=e["char_limit"]): e
                    for e in sumnjivi_evals
                }
                for future in futures:
                    e = futures[future]
                    try:
                        judge_res = future.result()
                        e["judge_score"] = judge_res["score"]
                        e["judge_errors"] = judge_res["errors"]
                        e["judge_explanation"] = judge_res["explanation"]
                    except Exception as err:
                        print(f"[PARALLEL LLM JUDGE ERROR] Greška pri paralelnom suđenju rečenice {e['global_idx']}: {err}", flush=True)
                        raise err

                        
        for idx, group in enumerate(batch):
            global_idx = batch_start + idx
            e = batch_evals[idx]
            
            orig_text = e["orig_text"]
            unmasked_text = e["unmasked_text"]
            negation_ok = e["negation_ok"]
            qe_score = e["qe_score"]
            char_limit = e["char_limit"]
            judge_score = e["judge_score"]
            judge_errors = e["judge_errors"]
            judge_explanation = e["judge_explanation"]
            
            print(f"[VALIDATION] Rečenica {global_idx}: Negation OK = {negation_ok}, CometKiwi QE Score = {qe_score:.3f}, LLM Judge Score = {judge_score:.1f}", flush=True)
            
            # 3. Automatska re-prevod i samokritika petlja (Multi-turn Critique do 2 pokušaja)
            turn = 0
            max_turns = 2
            while not skip_gating and (not negation_ok or (qe_score < 0.85 and judge_score < 4.0)) and turn < max_turns:
                turn += 1
                hints = []
                if not negation_ok:
                    hints.append("Prevod je izgubio negaciju iz originala. Originalna rečenica ima negaciju (not/never/no/don't itd.), dok tvoj prevod nema. Obavezno ispravi prevod da sadrži negaciju (ne/nikad/nije/nema/nemam).")
                if qe_score < 0.85 and judge_score < 4.0:
                    hints.append(f"Prevod ne zadovoljava standarde kvaliteta (Sudija ocena: {judge_score}/5.0). Uočene greške: {', '.join(judge_errors)}. Objašnjenje sudije: {judge_explanation}.")
                
                # Dodavanje specifičnih heurističkih saveta za samokritiku
                LEAK_PATTERN = re.compile(
                    r'\b(dio|dijel\w*|dvjesto|spriječi\w*|tijekom|sustav\w*|tjedan|tjedn\w*|'
                    r'tisuć\w*|uvjet\w*|utjecaj\w*|sučelj\w*|zaslon\w*|tipkovnic\w*|poveznic\w*|'
                    r'vidjeti|djeluj\w*|riješi\w*|uvijek|gdje|susjed\w*|uput[aeiu]|osjetljiv\w*|'
                    r'kangur\w*|struč(?:ak|ka|ci)|joi)\b', re.IGNORECASE)
                leaks = [m.group(0) for m in LEAK_PATTERN.finditer(unmasked_text)]
                if leaks:
                    hints.append(f"Uočeni su ijekavizmi ili regionalizmi: {', '.join(leaks)}. Prevedi striktno na srpsku ekavicu (deo, sistem, uslov, tokom, hiljada, uvek, gde, videti, rešiti).")
                if re.search(r'\b\d+\b', unmasked_text) and not re.search(r'\b\d+\b', orig_text):
                    hints.append("Prevod sadrži cifre (brojeve). Svi brojevi moraju biti napisani rečima na srpskom (npr. 'dva', 'pet posto').")
                if len(unmasked_text) > char_limit:
                    hints.append(f"Prevod je predugačak ({len(unmasked_text)} karaktera, a limit je {char_limit} karaktera). Skrati rečenicu tako da stane u limit.")

                hint_str = " ".join(hints)
                print(f"[RETRANSLATION NEEDED - TURN {turn}] Rečenica {global_idx} ne zadovoljava kriterijume. Pokrećem self-critique...", flush=True)
                
                # Pokrećemo self-critique u maskiranom modu
                masked_orig, masked_bad, self_critique_masks = mask_segment_pair(orig_text, unmasked_text)
                refined = retranslate_with_self_critique(masked_orig, masked_bad, hint_str)
                unmasked_refined = unmask_text(refined, self_critique_masks)
                
                # Re-evaluacija nakon samokritike
                negation_ok = check_negation_preservation(orig_text, unmasked_refined)
                qe_score = get_comet_kiwi_score(orig_text, unmasked_refined)
                
                if qe_score < 0.85:
                    judge_res = get_llm_judge_score(orig_text, unmasked_refined, limit_char=char_limit)
                    judge_score = judge_res["score"]
                    judge_errors = judge_res["errors"]
                    judge_explanation = judge_res["explanation"]
                else:
                    judge_score = 5.0
                    
                print(f"[VALIDATION AFTER SELF-CRITIQUE TURN {turn}] Rečenica {global_idx}: Negation OK = {negation_ok}, CometKiwi QE Score = {qe_score:.3f}, LLM Judge Score = {judge_score:.1f}", flush=True)
                unmasked_text = unmasked_refined
                
            # 4. Podela prevedene rečenice nazad na originalne segmente
            parts = split_translated_text(unmasked_text, group)
            for p_idx, s in enumerate(group):
                parsed_dict[s.get("id")] = parts[p_idx]
            
        # Ažuriranje confirmed_translations na osnovu used_terms koji je model vratio
        if isinstance(data, dict):
            used_terms = data.get("used_terms")
            if isinstance(used_terms, dict):
                for eng, srb in used_terms.items():
                    if eng and srb:
                        confirmed_translations[eng] = srb

        # Sastavljanje finalnih segmenata za ovaj batch
        for i, group in enumerate(batch):
            for s in group:
                global_idx = s.get("id")
                t_text = parsed_dict.get(global_idx, "").strip()
                if not t_text:
                    print(f"[WARNING] Segment {global_idx} nema prevod. Koristim originalni tekst kao fallback.", flush=True)
                    t_text = s["text"]
                
                # Ponovo računamo maske za ovaj segment radi kompatibilnosti sa daljim tokovima
                _, single_masks = mask_untranslatable(t_text)
                
                final_segments.append({
                    "id": global_idx,
                    "start": s["start"],
                    "end": s["end"],
                    "text": t_text,
                    "original_text": s["text"],
                    "masks": single_masks,
                    "qe_score": float(qe_score) if qe_score is not None else None
                })
        
        # Inkrementiraj batch_start za obrađeni batch
        batch_start += len(batch)

    # Sortiranje finalnih segmenata po ID-u kako bi ostali u pravom redosledu
    final_segments = sorted(final_segments, key=lambda x: x["id"])
    
    # 3. Post-procesiranje i integrisana lektura (unmasking, transliteracija, čišćenje i kompresija)
    for fs in final_segments:
        # Odmaskiranje entiteta
        unmasked = unmask_text(fs["text"], fs["masks"])
        # Transliteracija u latinicu
        lat = to_latin(unmasked)
        # Čišćenje dijalekata, ijekavice i thought tagova
        cleaned = clean_translation_text(lat, qe_score=fs.get("qe_score"))
        
        # Izračunavanje limita dužine i kompresija ako je potrebno
        orig_seg = next((s for s in segments if s.get("id") == fs["id"]), None)
        if orig_seg:
            duration = orig_seg["end"] - orig_seg["start"]
            factor = calculate_dynamic_factor(orig_seg, user_avg_speedup)
            limit_char = max(15, int(duration * factor), int(len(orig_seg['text']) * 0.75))
            
            if len(cleaned) > limit_char * 1.15:
                # Pozivamo kompresiju rečenice preko novog Mistral modela
                cleaned = compress_sentence_via_llm(cleaned, limit_char)
                
            # Evaluacija confidence score-a
            confidence = 5
            if fs.get("qe_score", 1.0) < 0.85:
                confidence -= 1
            if len(cleaned) > limit_char:
                confidence -= 1
            fs["confidence_score"] = max(1, confidence)
            
        fs["text"] = cleaned

    translator_duration = time.time() - t_start_trans

    # 4. Subagent Alpha: Real-time "Tihi Konsenzus" (Perpetual Learning)
    if project_id:
        try:
            from backend.core.database import SessionLocal
            from backend.core.models import TranslationMemory, PendingTranslationMemory, Project
            from backend.services.embedding import embedding_service
            
            db = SessionLocal()
            project_entry = db.query(Project).filter(Project.id == project_id).first()
            if project_entry:
                user_id = project_entry.user_id
                for fs in final_segments:
                    final_text = fs.get("text", "")
                    orig_text = fs.get("original_text", "")
                    if not final_text or not orig_text:
                        continue
                    
                    final_qe = get_comet_kiwi_score(orig_text, final_text)
                    lektor_confidence = fs.get("confidence_score", 5)
                    
                    if final_qe > 0.92 and lektor_confidence > 4.5:
                        exists = db.query(TranslationMemory).filter(
                            TranslationMemory.user_id == user_id,
                            TranslationMemory.source_text == orig_text
                        ).first()
                        if not exists:
                            emb = embedding_service.get_embedding(orig_text)
                            tm_entry = TranslationMemory(
                                user_id=user_id,
                                project_id=project_id,
                                source_text=orig_text,
                                target_text=final_text,
                                embedding=emb,
                                auto_approved=True
                            )
                            db.add(tm_entry)
                            print(f"[ALPHA] Visok kvalitet (QE={final_qe:.3f}, Conf={lektor_confidence}). Direktan upis u TM: '{orig_text}' -> '{final_text}'", flush=True)
                    elif final_qe > 0.85 and lektor_confidence > 3.5:
                        existing_pending = db.query(PendingTranslationMemory).filter(
                            PendingTranslationMemory.user_id == user_id,
                            PendingTranslationMemory.source_text == orig_text
                        ).first()
                        if existing_pending:
                            existing_pending.occurrence_count += 1
                        else:
                            pending_entry = PendingTranslationMemory(
                                user_id=user_id,
                                project_id=project_id,
                                source_text=orig_text,
                                target_text=final_text,
                                occurrence_count=1
                            )
                            db.add(pending_entry)
                db.commit()
                db.close()
        except Exception as e:
            print(f"[ALPHA ERROR] Greška u Perpetual Learning Real-time upisu: {e}", flush=True)

    return {
        "status": "success",
        "translated_segments": final_segments,
        "metrics": {
            "translator_duration": translator_duration,
            "lektor_duration": 0.0
        }
    }
