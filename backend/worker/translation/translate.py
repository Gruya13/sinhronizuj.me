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
from .qe import get_comet_kiwi_score, check_negation_preservation

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
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [
            {
                "role": "system",
                "content": "Ti si stručni prevodilac i lektor. Vrati isključivo ispravljeni prevod na srpski jezik bez ikakvog dodatnog teksta ili komentara."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 500
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
    Uvedeni: globalni sažetak, klizni prozor konteksta, Chain-of-Thought analiza,
             dužinska svesnost i running glossary Running Glossary.
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

    print(f"[TRANSLATOR] Pokrećem prevođenje {len(segments)} segmenata koristeći Qwen3-32B Lektor endpoint.", flush=True)
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

    # JSON šema za structured output
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

    # 2. Prevođenje u batch-ovima (batch size = 30)
    batch_size = 30
    final_segments = []
    
    # Mapiramo maske za celokupne segmente kako bismo znali kako da ih odmaskiramo
    batch_masks_map = {}

    for batch_start in range(0, len(segments), batch_size):
        batch_end = min(batch_start + batch_size, len(segments))
        batch = segments[batch_start:batch_end]
        
        print(f"[TRANSLATOR] Pokrećem batch od segmenta {batch_start} do {batch_end - 1}...", flush=True)
        if progress_callback:
            progress_callback(detail=f"Prevodim segmente {batch_start}-{batch_end - 1}... ⏳")

        # Priprema segmenata za slanje uz maskiranje Wi-Fi, GPS, Bluetooth i drugih entiteta
        formatted_batch_list = []
        for i, s in enumerate(batch):
            global_idx = batch_start + i
            masked_text, masks = mask_untranslatable(s["text"])
            batch_masks_map[global_idx] = masks
            
            # Računanje dinamičkog limita karaktera za prevod u odnosu na brzinu čitanja i trajanje segmenta
            duration = s["end"] - s["start"]
            char_limit = int(duration * calculate_dynamic_factor(s, user_avg_speedup))
            
            formatted_batch_list.append(
                f"[Segment {global_idx}] (Limit: {char_limit} karaktera) ENG: {masked_text}"
            )
        batch_input_str = "\n".join(formatted_batch_list)

        # Generisanje trenutnog glossary konteksta
        current_glossary_lines = []
        for eng, srb in full_glossary_dict.items():
            # Ako je termin već potvrđen u prethodnim batch-ovima, šaljemo ga kao potvrđenog
            if eng in confirmed_translations:
                current_glossary_lines.append(f'- "{eng}" -> "{confirmed_translations[eng]}" (potvrđeno)')
            else:
                current_glossary_lines.append(f'- "{eng}" -> "{srb}"')
        current_glossary_str = "\n".join(current_glossary_lines) if current_glossary_lines else "Nema termina."

        # Formiranje prompta za prevođenje
        system_prompt = (
            "You are an expert video translation system. Translate the English transcript segments to Serbian.\n"
            "STRICT RULES FOR SERBIAN TRANSLATION:\n"
            "1. Language & Script: Use standard Serbian language in Latin script.\n"
            "2. Dialect: Use strictly Serbian ekavica (e.g. 'deo', 'rešenje', 'promena', 'gde', 'uvek', 'sprečiti'). Do NOT use ijekavica or Croatian regionalisms.\n"
            "3. Tone: Use strictly informal singular address 'ti' (e.g. 'ako želiš', 'poravnaj', 'pogledaj'). Avoid formal address.\n"
            "4. Numbers: Write all numbers, years, and percentages strictly in words (e.g. 'dve hiljade dvadeset šesta', 'pet posto'). Never output digits.\n"
            "5. Word limits: Do NOT exceed the character limit specified for each segment. If you exceed the limit, the speech synthesizer will run out of time.\n"
            "6. Entity Preservation: Keep placeholder tags like [ENTITY_0], [CODE_1], [URL_0] exactly as they are. Do not translate or change them.\n"
            "7. Phonetic names: Write foreign names and brands phonetically (e.g. 'Klod', 'OpenEjAj'). Exceptions: IT acronyms GPS, Wi-Fi, and Bluetooth must remain in original English.\n\n"
            "Respond strictly in JSON format matching the schema."
        )

        user_prompt = (
            f"GLOBAL VIDEO SUMMARY FOR CONTEXT:\n{video_summary}\n\n"
            f"STRIKTNI PREDLOŽENI GLOSAR ZA OVAJ BATCH:\n{current_glossary_str}\n\n"
            "SEGMENTS TO TRANSLATE:\n"
            f"{batch_input_str}\n\n"
            "Translate each segment, strictly respect the character limits, and output the JSON object."
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
            content = clean_thought_tags(content)
            
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\n', '', content)
                content = re.sub(r'\n```$', '', content)
            
            data = json.loads(content)
        except Exception as e:
            print(f"[TRANSLATOR BATCH ERROR] Greška pri prevođenju batch-a {batch_start}: {e}. Koristim fallback.", flush=True)
            # Fallback rečnik
            data = {"segments": []}

        # Parsiranje rezultata i post-procesiranje (gating, self-critique)
        parsed_dict = {}
        for s in data.get("segments", []):
            parsed_dict[s["id"]] = s["translated_text"]

        for idx in range(batch_start, batch_end):
            raw_trans = parsed_dict.get(idx, "").strip()
            if not raw_trans:
                print(f"[WARNING] Segment {idx} nema prevod. Koristim originalni tekst kao fallback.", flush=True)
                raw_trans = segments[idx]["text"]

            # Odmaskiravanje i deterministička ispravka ijekavice pre provere
            unmasked_text = unmask_text(raw_trans, batch_masks_map[idx])
            
            # Provera i verifikacija (negacije i semantika)
            orig_segment = segments[idx]
            orig_text = orig_segment["text"]
            
            negation_ok = check_negation_preservation(orig_text, unmasked_text)
            # Zamena starog kosinusnog gejtinga CometKiwi skorom sa kalibrisanim pragom
            qe_score = get_comet_kiwi_score(orig_text, unmasked_text)
            print(f"[VALIDATION] Segment {idx}: Negation OK = {negation_ok}, CometKiwi QE Score = {qe_score:.3f}", flush=True)
            
            # Automatska re-prevod i samokritika petlja ako validacija ne prođe
            if not skip_gating and (not negation_ok or qe_score < 0.75):
                hints = []
                if not negation_ok:
                    hints.append("Prevod je izgubio negaciju iz originala. Originalna rečenica ima negaciju (not/never/no/don't itd.), dok tvoj prevod nema. Obavezno ispravi prevod da sadrži negaciju (ne/nikad/nije/nema/nemam).")
                if qe_score < 0.75:
                    hints.append("Prevod ima nizak kvalitet ili odstupa od standarda projekta (ekavica, bez regionalizama, brojevi rečima, fonetska imena). Zadrži tačan smisao rečenice i striktno poštuj pravila prevoda.")
                
                hint_str = " ".join(hints)
                print(f"[RETRANSLATION NEEDED] Segment {idx} ne zadovoljava kriterijume. Pokrećem self-critique...", flush=True)
                
                # Pokrećemo self-critique u maskiranom modu
                masked_orig, masked_bad, self_critique_masks = mask_segment_pair(orig_text, unmasked_text)
                refined = retranslate_with_self_critique(masked_orig, masked_bad, hint_str)
                unmasked_refined = unmask_text(refined, self_critique_masks)
                
                negation_ok_2 = check_negation_preservation(orig_text, unmasked_refined)
                qe_score_2 = get_comet_kiwi_score(orig_text, unmasked_refined)
                print(f"[VALIDATION AFTER SELF-CRITIQUE] Segment {idx}: Negation OK = {negation_ok_2}, CometKiwi QE Score = {qe_score_2:.3f}", flush=True)
                
                unmasked_text = unmasked_refined
                
            parsed_dict[idx] = unmasked_text
            
        # Ažuriranje confirmed_translations na osnovu used_terms koji je model vratio
        used_terms_found = False
        if isinstance(data, dict):
            used_terms = data.get("used_terms")
            if isinstance(used_terms, dict):
                for eng, srb in used_terms.items():
                    if eng and srb:
                        confirmed_translations[eng] = srb

        # Sastavljanje finalnih segmenata za ovaj batch
        for i, orig in enumerate(batch):
            global_idx = batch_start + i
            t_text = parsed_dict.get(global_idx, "").strip()
            if not t_text:
                print(f"[WARNING] Segment {global_idx} nema prevod. Koristim originalni engleski tekst kao fallback.", flush=True)
                t_text = orig["text"]
                
            final_segments.append({
                "id": orig.get("id", global_idx),
                "start": orig["start"],
                "end": orig["end"],
                "text": t_text,
                "original_text": orig["text"],
                "masks": batch_masks_map.get(global_idx, {})
            })

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
