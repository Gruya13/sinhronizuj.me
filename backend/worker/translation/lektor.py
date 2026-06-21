import re
import time
import json
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

# Uvoženje iz lokalnih modula
from .masking import mask_untranslatable, unmask_text
from .transliter import to_latin
from .dialect import clean_translation_text, clean_thought_tags

# Odloženi uvoz kako bismo izbegli cirkularne zavisnosti
def get_calculate_dynamic_factor():
    from .translate import calculate_dynamic_factor
    return calculate_dynamic_factor

def get_generate_video_summary():
    from backend.worker.translator import generate_video_summary
    return generate_video_summary

def get_dynamic_glossary_func():
    from backend.worker.translator import get_dynamic_glossary
    return get_dynamic_glossary

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
    
    # Pokušaj 1: direktan loads
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # Pokušaj 2: popravka novih redova unutar stringova
    try:
        fixed_text = fix_json_newlines(text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        pass
    
    # Pokušaj 3: Traženje JSON bloka unutar ```json i ```
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

    # Pokušaj 4: popravka celog teksta ako je odsečen i onda ponovni pokušaj loads
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
            
    # Pokušaj 5: Traženje prvog '[' i poslednjeg ']' ili '{' i '}' i popravka
    start_arr = text.find('[')
    if start_arr != -1:
        json_content = text[start_arr:]
        # Ako postoji i zatvarajući, uzmi do njega, inače uzmi do kraja i popravi
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

def regex_parse_json_segments(text: str, text_key: str = "translated_text") -> dict:
    parsed = {}
    id_matches = list(re.finditer(r'"id"\s*:\s*(\d+)', text))
    for i, id_match in enumerate(id_matches):
        start_pos = id_match.start()
        end_pos = id_matches[i+1].start() if i + 1 < len(id_matches) else len(text)
        segment_chunk = text[start_pos:end_pos]
        idx = int(id_match.group(1))
        
        # Tražimo tekstualni sadržaj
        text_match = re.search(rf'"{text_key}"\s*:\s*"([^"]*)"', segment_chunk)
        if not text_match:
            text_match = re.search(r'"(?:translated_text|refined_text|text)"\s*:\s*"([^"]*)"', segment_chunk)
        if text_match:
            val = text_match.group(1).strip()
            parsed[idx] = val
        else:
            text_match_lazy = re.search(rf'"{text_key}"\s*:\s*"([\s\S]*?)"(?=\s*,\s*"|\s*\}})', segment_chunk)
            if text_match_lazy:
                val = text_match_lazy.group(1).strip().replace('\n', ' ')
                parsed[idx] = val
    return parsed

def lektor_segments(original_segments, translated_segments, progress_callback=None, translator_duration=0.0, dynamic_glossary_str=None, video_summary=None, user_avg_speedup: float = 1.0, skip_deduplication: bool = False):
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
        
    # 0. Near-duplicate deduplikacija za susedne segmente
    if not skip_deduplication:
        for i in range(1, len(translated_segments)):
            orig_prev = original_segments[i-1].get("text", "")
            orig_curr = original_segments[i].get("text", "")
            trans_prev = translated_segments[i-1].get("text", "")
            trans_curr = translated_segments[i].get("text", "")
            
            eng_sim = calculate_jaccard_similarity(orig_prev, orig_curr)
            trans_sim = calculate_jaccard_similarity(trans_prev, trans_curr)
            
            if eng_sim >= 0.85 or trans_sim >= 0.85:
                print(f"[DEDUP] Pronađen near-duplicate na segmentu {i}. Uklanjam ponavljanje.", flush=True)
                translated_segments[i]["text"] = ""

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
            video_summary = get_generate_video_summary()(transcript_text)
        except Exception:
            video_summary = "No context available."

    if not dynamic_glossary_str:
        try:
            transcript_text = " ".join([seg["orig_text"] for seg in unique_segments])
            dynamic_glossary_str = get_dynamic_glossary_func()(transcript_text)
        except Exception as e:
            print(f"[WARNING] Greška pri kreiranju dinamičkog glosara: {e}. Koristim prazan glosar.")
            dynamic_glossary_str = "Nema specifičnih termina za ovaj video."

    # JSON šema za structured output lektora
    lektor_schema = {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "refined_text": {"type": "string"}
                    },
                    "required": ["id", "refined_text"]
                }
            }
        },
        "required": ["segments"]
    }

    batch_size = 5
    parsed_lektor_dict = {}
    lektor_masks_map = {}
    lektor_duration = 0.0
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    t_start_lektor = time.time()
    
    calculate_dynamic_factor = get_calculate_dynamic_factor()
    
    for batch_idx, batch_start in enumerate(range(0, len(unique_segments), batch_size)):
        batch_translated = unique_segments[batch_start:batch_start + batch_size]
        
        print(f"[LEKTOR] Pokrećem Lektor batch {batch_idx + 1} (segmenti {batch_start} do {batch_start + len(batch_translated) - 1})...", flush=True)
        
        lektor_input = ""
        for j, seg in enumerate(batch_translated):
            global_idx = batch_start + j
            duration = seg["duration"]
            
            # 1. Programsko rešavanje mikro-segmenata i obrisanih duplikata
            if duration < 0.5 or seg.get("translated_text", "") == "":
                print(f"[LEKTOR] Segment {global_idx} je mikro-segment ili obrisan duplikat (trajanje: {duration:.2f}s). Programski postavljam prazan prevod.", flush=True)
                parsed_lektor_dict[global_idx] = ""
                continue
                
            factor = calculate_dynamic_factor(seg, user_avg_speedup)
            limit_char = max(15, int(duration * factor), int(len(seg['orig_text']) * 0.75))
            
            # Maskiramo pre slanja lektoru radi zaštite entiteta
            masked_orig, _ = mask_untranslatable(seg['orig_text'])
            masked_trans, masks = mask_untranslatable(to_latin(seg['translated_text']))
            lektor_masks_map[global_idx] = masks
            
            lektor_input += f"[seg-{global_idx}] (trajanje: {duration:.1f}s, LIMIT: {limit_char} karaktera) ENG: {masked_orig} | SRB: {masked_trans}\n"
            
        if not lektor_input.strip():
            print(f"[LEKTOR] Svi segmenti u batch-u {batch_idx + 1} su mikro-segmenti. Preskačem API poziv.", flush=True)
            continue
            
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
            "Ti si glavni urednik i lektor za srpski jezik. Pregledaj grubi prevod (SRB) u odnosu na original (ENG) i trajanje segmenta, ispravi greške i vrati tečan srpski prevod na ekavici i latinici.\n\n"
            "VAŽNO: STROGO JE ZABRANJENO generisanje <think> ili <thought> tagova i bilo kakvog razmišljanja. Samo odmah vrati JSON odgovor direktno.\n\n"
            f"{history_section}"
            "PRAVILA ZA UREĐIVANJE:\n"
            "1. PIŠI ISKLJUČIVO SRPSKOM LATINICOM. Koristi jedninsko neformalno obraćanje 'ti' (npr. 'poravnaj').\n"
            "2. STRIKTNI GLOSAR: Za engleske stručne pojmove OBAVEZNO koristi ponuđene prevode iz glosara (prilagodi ih gramatički padežu):\n"
            f"{dynamic_glossary_str}\n\n"
            "3. STRIKTNA EKAVICA I PRAVOPIS: Zameni sve ijekavske oblike (dio->deo, spriječiti->sprečiti, dvjesto->dvesta, promijeniti->promeniti, riješiti->rešiti, uvjek->uvek) i hrvatske reči (tijekom->tokom, tjedan->nedelja, tisuća->hiljada, sustav->sistem, uvjet->uslov, utjecaj->uticaj, učinkovitost->efikasnost, tvrtka->firma, sučelje->interfejs, zaslon->ekran, tipkovnica->tastatura, poveznica->link, kaos->haos, nazive meseci) srpskim ekavskim ekvivalentima.\n"
            "4. IT akronime GPS, Wi-Fi i Bluetooth piši u originalnom obliku. Izbegavaj pasivne konstrukcije sa 'od strane'.\n"
            "5. MORFOLOGIJA: Strogo pazi na morfološko slaganje (npr. 'drveni komad', a ne 'komad drveta'; 'jednake cilindriće'; 'zavar je gladak').\n"
            "6. LIMIT KARAKTERA: Prevod (refined_text) mora biti kraći ili igualan prosleđenom LIMITU.\n"
            "7. ID segmenta u objektu MORA biti ceo broj koji tačno odgovara indeksu segmenta iz ulaza (npr. za '[seg-5]' id mora biti 5. NIKADA ne koristi fiktivne ID-jeve 9999 ili 99999 iz šablona).\n\n"
            "FORMAT ODGOVORA:\n"
            "Odgovori isključivo u validnom JSON formatu prema sledećoj šemi, bez uvodnog ili pratećeg teksta:\n"
            "{\n"
            "  \"segments\": [\n"
            "    {\n"
            "      \"id\": 9999,\n"
            "      \"refined_text\": \"Lekturisani i korigovani srpski prevod za segment 9999.\"\n"
            "    },\n"
            "    {\n"
            "      \"id\": 99999,\n"
            "      \"refined_text\": \"Lekturisani i korigovani srpski prevod za segment 99999.\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "VAŽNO: Tvoj JSON odgovor mora sadržati lekturisane verzije svih segmenata iz sekcije TEKST ZA LEKTURU sa njihovim tačnim ID-jevima. Nemoj kopirati fiktivne ID-jeve 9999 ili 99999 iz šablona.\n\n"
            f"TEKST ZA LEKTURU:\n{lektor_input}"
        )

        try:
            lektor_payload = {
                "model": "qwen-lektor",
                "messages": [
                    {
                        "role": "system",
                        "content": "Ti si glavni urednik i lektor za srpski jezik. Lekturiši grubi prevod i vrati isključivo validan JSON prema šemi. STROGO JE ZABRANJENO generisanje <think> ili <thought> tagova i bilo kakvog razmišljanja. Odmah vrati JSON."
                    },
                    {
                        "role": "user",
                        "content": lektor_prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
                "presence_penalty": 0.5,
                "enable_thinking": False
            }
            
            from backend.worker.translator import call_modal_endpoint
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

            # Čišćenje thought tagova
            lektor_raw_clean = clean_thought_tags(lektor_raw)
            print(f"[DEBUG] BATCH {batch_idx + 1} LEKTOR CLEANED OUTPUT:\n{lektor_raw_clean}", flush=True)
            
            # Parsiranje
            data = extract_and_parse_json(lektor_raw_clean)
            batch_parsed_lektor = {}
            non_micro_segments = [s for s in batch_translated if s["duration"] >= 0.5]
            
            if data:
                segments_list = data if isinstance(data, list) else data.get("segments", [])
                if isinstance(segments_list, list):
                    valid_items = []
                    for item in segments_list:
                        if isinstance(item, dict):
                            idx = item.get("id")
                            text = None
                            for key in ["refined_text", "translated_text", "text"]:
                                if key in item:
                                    text = item[key]
                                    break
                            if text is not None:
                                valid_items.append((idx, str(text).strip()))
                                
                    # 1. Mapiranje po redosledu
                    if len(valid_items) == len(non_micro_segments):
                        print(f"[LEKTOR] Broj segmenata se poklapa ({len(valid_items)}). Mapiram po redosledu.", flush=True)
                        for i, (orig_id, text) in enumerate(valid_items):
                            global_idx = non_micro_segments[i]["unique_id"]
                            batch_parsed_lektor[global_idx] = text
                    else:
                        # 2. Mapiranje po ID-jevima
                        for orig_id, text in valid_items:
                            if orig_id is not None:
                                try:
                                    idx_val = int(orig_id)
                                    if batch_start <= idx_val < batch_start + len(batch_translated):
                                        batch_parsed_lektor[idx_val] = text
                                    else:
                                        if 0 <= idx_val < len(non_micro_segments):
                                            g_idx = non_micro_segments[idx_val]["unique_id"]
                                            batch_parsed_lektor[g_idx] = text
                                        elif 1 <= idx_val <= len(non_micro_segments):
                                            g_idx = non_micro_segments[idx_val - 1]["unique_id"]
                                            batch_parsed_lektor[g_idx] = text
                                except ValueError:
                                    continue
                                
            # Regex fallback
            if len(batch_parsed_lektor) < len(batch_translated):
                import logging
                logging.error(f"[LEKTOR] JSON parser/guided decoding vratio samo {len(batch_parsed_lektor)} od {len(batch_translated)} segmenata. Pokrećem robusni regex JSON fallback...")
                regex_parsed = regex_parse_json_segments(lektor_raw_clean, "refined_text")
                for idx, text in regex_parsed.items():
                    if idx not in batch_parsed_lektor:
                        batch_parsed_lektor[idx] = text
                            
            # Spajanje
            for idx, text in batch_parsed_lektor.items():
                if batch_start <= idx < batch_start + len(batch_translated):
                    unmasked_text = unmask_text(text, lektor_masks_map.get(idx, {}))
                    parsed_lektor_dict[idx] = unmasked_text
                    print(f"[LEKTOR] Segment {idx} lekturisan: {unmasked_text[:60]}...", flush=True)
                    
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
                        
                        analysis = ""
                        if data and isinstance(data, dict):
                            s_list = data.get("segments", [])
                            if isinstance(s_list, list):
                                for item in s_list:
                                    if isinstance(item, dict) and item.get("id") == idx_int:
                                        analysis = item.get("analysis") or ""
                                        break
                                        
                        confidence = 5
                        confidence_triggers = ["idiom", "unclear", "ambiguous", "colloquial", "cultural reference", "wordplay", "humor", "slang"]
                        for trigger in confidence_triggers:
                            if trigger in str(analysis).lower():
                                confidence -= 1
                        
                        overshoot = len(str(unmasked_text)) / limit_char
                        if overshoot > 1.2:
                            confidence -= 1
                        confidence = max(1, confidence)
                        
                        orig_seg["confidence_score"] = confidence
                        
                        import logging
                        compliance_logger = logging.getLogger("translation_compliance")
                        compliance_stats = {
                            "segment_id": idx_int,
                            "duration": duration,
                            "limit_char": limit_char,
                            "actual_char": len(str(unmasked_text)),
                            "compliance": len(str(unmasked_text)) <= limit_char,
                            "overshoot_pct": max(0.0, (len(str(unmasked_text)) - limit_char) / limit_char * 100)
                        }
                        compliance_logger.info(f"[COMPLIANCE] {json.dumps(compliance_stats)}")
                    
        except Exception as batch_err:
            print(f"[WARNING] Greška u Lektor batchu {batch_idx + 1}: {batch_err}")

    lektor_duration = time.time() - t_start_lektor
    print(f"[LEKTOR] Lektura završena za {lektor_duration:.2f}s. Uspešno lekturisano {len(parsed_lektor_dict)} od {len(unique_segments)} jedinstvenih segmenata.", flush=True)
    
    # 3. Zatvorena petlja (TTS-Aware Compression)
    for u_seg in unique_segments:
        idx = u_seg["unique_id"]
        if idx in parsed_lektor_dict:
            lektorised_text = parsed_lektor_dict[idx]
            if not lektorised_text:
                continue
            duration = u_seg["duration"]
            factor = calculate_dynamic_factor(u_seg, user_avg_speedup)
            limit_char = max(15, int(duration * factor), int(len(u_seg['orig_text']) * 0.75))
            
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
        
    LEAK_PATTERN = re.compile(
        r'\b(dio|dijel\w*|dvjesto|spriječi\w*|tijekom|sustav\w*|tjedan|tjedn\w*|'
        r'tisuć\w*|uvjet\w*|utjecaj\w*|sučelj\w*|zaslon\w*|tipkovnic\w*|poveznic\w*|'
        r'vidjeti|djeluj\w*|riješi\w*|uvijek|gdje|provjer\w*|vjer\w*|mjer\w*|svijet\w*|'
        r'vijest\w*|tijel\w*|obavijest\w*|susjed\w*|uput[aeiu]|osjetljiv\w*|'
        r'kangur\w*|struč(?:ak|ka|ci)|joi)\b', re.IGNORECASE)
    for seg in translated_segments:
        if "text" in seg:
            seg["text"] = unmask_text(seg["text"], seg.get("masks", {}))
            seg["text"] = to_latin(seg["text"])
            seg["text"] = clean_translation_text(seg["text"])
            
            # Leak guard check
            leak = LEAK_PATTERN.search(seg["text"])
            if leak:
                import logging
                logging.error(f"[LEAK] Dijalekat procurio u finalni izlaz seg {seg.get('id')}: '{leak.group(0)}' u '{seg['text']}'")
                seg["text"] = clean_translation_text(to_latin(seg["text"]))
            
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
        "3. Tvoj odgovor mora sadržati isključivo skraćenu rečenicu, bez ikakvog dodatnog teksta, komentara, navodnika, objašnjenja ili think tagova.\n"
        "4. STROGO ZABRANJENO: Nemoj generisati nikakvo razmišljanje, obrazloženje ili <think> tag. Samo odmah ispiši skraćeni tekst.\n"
        "5. Ukoliko je limit karaktera prekratak da bi se zadržao ceo smisao, izostavi manje bitne detalje ili zadrži samo ključne reči.\n\n"
        f"REČENICA ZA SKRAĆIVANJE: {text}"
    )
    
    payload = {
        "model": "qwen-lektor",
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
