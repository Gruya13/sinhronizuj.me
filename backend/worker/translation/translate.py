import time
import os
import re
import cv2
import json
import base64
from typing import List

from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

# Uvoženje iz lokalnih modula
from .masking import mask_untranslatable, unmask_text, mask_segment_pair
from .transliter import to_latin
from .dialect import clean_translation_text, clean_thought_tags
from .glossary import parse_glossary_to_dict
from .qe import get_comet_kiwi_score, check_negation_preservation, get_llm_judge_score

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
    for l in orig_lens:
        running_sum += l
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
        "model": "qwen-lektor",
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
        "temperature": 0.2,
        "max_tokens": 1500
    }
    
    try:
        from backend.worker.translator import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        cleaned = clean_thought_tags(content).strip().strip('"\'')
        if cleaned:
            print(f"[SELF-CRITIQUE SUCCESS] Prethodni: {bad_translation} -> Novi: {cleaned}", flush=True)
            return cleaned
    except Exception as e:
        print(f"[SELF-CRITIQUE ERROR] Greška prilikom re-prevoda sa samokritikom: {e}", flush=True)
        
    return bad_translation

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

def translate_segments(segments: list, video_path: str = None, progress_callback=None, user_avg_speedup: float = 1.0, skip_lektor: bool = False, skip_gating: bool = False, skip_deduplication: bool = False) -> dict:
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

    # 2. Prevođenje u batch-ovima (batch size = 12 rečenica)
    batch_size = 12
    final_segments = []
    
    # Mapiramo maske za rečenice kako bismo znali kako da ih odmaskiramo
    batch_masks_map = {}

    for batch_start in range(0, len(grouped_sentences), batch_size):
        batch_end = min(batch_start + batch_size, len(grouped_sentences))
        batch = grouped_sentences[batch_start:batch_end]
        
        print(f"[TRANSLATOR] Pokrećem batch rečenica od {batch_start} do {batch_end - 1}...", flush=True)
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

        # Formiranje prompta za prevođenje
        system_prompt = (
            "You are an expert video translation system. Translate the English transcript sentences to Serbian.\n"
            "STRICT RULES FOR SERBIAN TRANSLATION:\n"
            "1. Language & Script: Use standard Serbian language in Latin script.\n"
            "2. Dialect: Use strictly Serbian ekavica (e.g. 'deo', 'rešenje', 'promena', 'gde', 'uvek', 'sprečiti'). Do NOT use ijekavica or Croatian regionalisms.\n"
            "3. Tone: Use strictly informal singular address 'ti' (e.g. 'ako želiš', 'poravnaj', 'pogledaj'). Avoid formal address.\n"
            "4. Numbers: Write all numbers, years, and percentages strictly in words (e.g. 'dve hiljade dvadeset šesta', 'pet posto'). Never output digits.\n"
            "5. Word limits: Do NOT exceed the character limit specified for each sentence. If you exceed the limit, the speech synthesizer will run out of time.\n"
            "6. Entity Preservation: Keep placeholder tags like [ENTITY_0], [CODE_1], [URL_0] exactly as they are. Do not translate or change them.\n"
            "7. Phonetic names: Write foreign names and brands phonetically (e.g. 'Klod', 'OpenEjAj'). Exceptions: IT acronyms GPS, Wi-Fi, and Bluetooth must remain in original English.\n"
            "8. STROGO ZABRANJENO: Nemoj generisati nikakvo razmišljanje, obrazloženje ili <think>/<thought> tagove. Samo odmah vrati JSON odgovor direktno.\n\n"
            "Respond strictly in JSON format matching the schema."
        )

        user_prompt = (
            f"GLOBAL VIDEO SUMMARY FOR CONTEXT:\n{video_summary}\n\n"
            f"STRIKTNI PREDLOŽENI GLOSAR ZA OVAJ BATCH:\n{current_glossary_str}\n\n"
            "SENTENCES TO TRANSLATE:\n"
            f"{batch_input_str}\n\n"
            "Translate each sentence, strictly respect the character limits, do NOT think or write <think>, and output the JSON object directly."
        )

        url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": "qwen-lektor",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 2048,
            "guided_json": translator_schema
        }

        try:
            from backend.worker.translator import call_modal_endpoint
            res = call_modal_endpoint(url=url, payload=payload)
            content = res["choices"][0]["message"]["content"].strip()
            
            from backend.worker.translation.lektor import extract_and_parse_json
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
        
        from backend.worker.translation.lektor import calculate_jaccard_similarity
        
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
            
            # 2. Hibridni LLM-as-a-Judge gating ako je CometKiwi nizak ili ako negacija fali
            judge_score = 5.0
            judge_errors = []
            judge_explanation = ""
            
            char_limit = 0
            for s in group:
                duration = s["end"] - s["start"]
                char_limit += int(duration * calculate_dynamic_factor(s, user_avg_speedup))
            char_limit = max(15, char_limit)
            
            if not skip_gating and (not negation_ok or qe_score < 0.85):
                print(f"[LLM JUDGE ACTIVATION] Gating sumnjiv za rečenicu {global_idx} (CometKiwi QE: {qe_score:.3f}, Negation OK: {negation_ok}). Pozivam LLM-as-a-Judge...", flush=True)
                judge_res = get_llm_judge_score(orig_text, unmasked_text, limit_char=char_limit)
                judge_score = judge_res["score"]
                judge_errors = judge_res["errors"]
                judge_explanation = judge_res["explanation"]
            
            print(f"[VALIDATION] Rečenica {global_idx}: Negation OK = {negation_ok}, CometKiwi QE Score = {qe_score:.3f}, LLM Judge Score = {judge_score:.1f}", flush=True)
            
            # 3. Automatska re-prevod i samokritika petlja (Multi-turn Critique do 3 pokušaja)
            turn = 0
            max_turns = 3
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
        used_terms_found = False
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
                    "masks": single_masks
                })

    # Sortiranje finalnih segmenata po ID-u kako bi ostali u pravom redosledu
    final_segments = sorted(final_segments, key=lambda x: x["id"])
    translator_duration = time.time() - t_start_trans

    # Pokretanje Lektor faze sa prosleđenim parametrima
    try:
        if skip_lektor:
            # Ako preskačemo lektora, moramo odraditi unmasking i prevođenje u latinicu i clean_translation_text za finalne segmente
            for fs in final_segments:
                unmasked = unmask_text(fs["text"], fs["masks"])
                lat = to_latin(unmasked)
                cleaned = clean_translation_text(lat)
                fs["text"] = cleaned
            return {
                "status": "success",
                "translated_segments": final_segments,
                "metrics": {
                    "translator_duration": translator_duration,
                    "lektor_duration": 0.0
                }
            }
        
        from backend.worker.translator import lektor_segments
        return lektor_segments(
            segments, 
            final_segments, 
            progress_callback=progress_callback, 
            translator_duration=translator_duration,
            dynamic_glossary_str=dynamic_glossary_str,
            video_summary=video_summary,
            user_avg_speedup=user_avg_speedup,
            skip_deduplication=skip_deduplication
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
