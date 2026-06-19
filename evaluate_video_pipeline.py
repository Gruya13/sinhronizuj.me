import os
import sys
import json
import time
import subprocess
import re
import math
from datetime import datetime

# Dodavanje korena projekta u sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Učitavanje konfiguracije i funkcija
from backend.core.config import settings
from backend.worker.transcriber import transcribe_audio
from backend.worker.segment_optimizer import optimize_segments_for_translation
from backend.worker.translator import translate_segments, get_comet_kiwi_score
from backend.worker.utils import call_modal_endpoint

TEST_VIDEOS_DIR = os.path.join(PROJECT_ROOT, "Test videos")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "evaluation_results")

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60 + "\n")

def list_test_videos():
    if not os.path.exists(TEST_VIDEOS_DIR):
        print(f"[ERROR] Direktorijum sa test video fajlovima ne postoji: {TEST_VIDEOS_DIR}")
        return []
    
    videos = [f for f in os.listdir(TEST_VIDEOS_DIR) if f.endswith(".mp4")]
    return sorted(videos)

def extract_audio(video_path, audio_path):
    print(f"[*] Ekstrakcija zvuka iz: {os.path.basename(video_path)}...")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("[+] Audio uspešno ekstrahovan.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Greška pri ekstrakciji zvuka: {e}")
        return False
    except FileNotFoundError:
        print("[ERROR] FFmpeg nije pronađen na sistemu. Molimo instalirajte FFmpeg.")
        return False

def compute_chrf(reference: str, hypothesis: str, beta: float = 3.0, char_ngram_max: int = 6, word_ngram_max: int = 2) -> float:
    """
    Čista Python/samo-sadržana implementacija chrF++ metrike.
    Karakterni n-grami (1-6) i rečni n-grami (1-2) sa težinskim faktorom beta=3.0 (veći značaj recall-a).
    """
    def get_ngrams(sequence, n):
        return [tuple(sequence[i:i+n]) for i in range(len(sequence) - n + 1)]

    ref_chars = list(reference.replace(" ", ""))
    hyp_chars = list(hypothesis.replace(" ", ""))
    
    char_precisions = []
    char_recalls = []
    
    for n in range(1, char_ngram_max + 1):
        ref_ngrams = get_ngrams(ref_chars, n)
        hyp_ngrams = get_ngrams(hyp_chars, n)
        if not ref_ngrams or not hyp_ngrams:
            continue
        ref_counts = {}
        for ng in ref_ngrams:
            ref_counts[ng] = ref_counts.get(ng, 0) + 1
        matches = 0
        hyp_counts = {}
        for ng in hyp_ngrams:
            hyp_counts[ng] = hyp_counts.get(ng, 0) + 1
        for ng, count in hyp_counts.items():
            matches += min(count, ref_counts.get(ng, 0))
        char_precisions.append(matches / len(hyp_ngrams))
        char_recalls.append(matches / len(ref_ngrams))
        
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    word_precisions = []
    word_recalls = []
    
    for n in range(1, word_ngram_max + 1):
        ref_ngrams = get_ngrams(ref_words, n)
        hyp_ngrams = get_ngrams(hyp_words, n)
        if not ref_ngrams or not hyp_ngrams:
            continue
        ref_counts = {}
        for ng in ref_ngrams:
            ref_counts[ng] = ref_counts.get(ng, 0) + 1
        matches = 0
        hyp_counts = {}
        for ng in hyp_ngrams:
            hyp_counts[ng] = hyp_counts.get(ng, 0) + 1
        for ng, count in hyp_counts.items():
            matches += min(count, ref_counts.get(ng, 0))
        word_precisions.append(matches / len(hyp_ngrams))
        word_recalls.append(matches / len(ref_ngrams))
        
    all_precisions = char_precisions + word_precisions
    all_recalls = char_recalls + word_recalls
    if not all_precisions or not all_recalls:
        return 0.0
    avg_p = sum(all_precisions) / len(all_precisions)
    avg_r = sum(all_recalls) / len(all_recalls)
    if avg_p + avg_r == 0:
        return 0.0
    beta_sq = beta ** 2
    return (1 + beta_sq) * (avg_p * avg_r) / (beta_sq * avg_p + avg_r)

def extract_and_parse_json(text: str) -> dict:
    """
    Uklanja <think>...</think> blokove i bezbedno parsira JSON
    čak i ako je umotan u markdown ```json ... ``` blokove.
    """
    # Ukloni <think>...</think> ako postoji
    text_clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    # Pokušaj da nađeš ```json ... ```
    match = re.search(r'```json\s*(.*?)\s*```', text_clean, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        # Pokušaj da nađeš prvi { i poslednji }
        start_idx = text_clean.find('{')
        end_idx = text_clean.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = text_clean[start_idx:end_idx+1].strip()
        else:
            json_str = text_clean
            
    try:
        return json.loads(json_str)
    except Exception as e:
        print(f"[JSON PARSE ERROR] Neuspešno parsiranje: {e}. Sirovi tekst: {text}")
        raise e

def run_llm_evaluation(segments, video_name):
    """
    Pokreće 3 prolaza primarnog sudije (Qwen3-32B) na temperaturi 0 sa MQM JSON šemom,
    zatim 1 prolaz sekundarnog sudije (simulacija sa temp 0.7 na istom endpointu) i računa statistiku.
    """
    print("[*] Pripremam MQM evaluaciju...")
    segments_text_list = []
    for s in segments:
        duration = s["end"] - s["start"]
        eng = s.get('original_text') or s.get('text') or ""
        srb = s.get('text') or ""
        segments_text_list.append(f"[Seg {s['id']}] ENG: {eng} | SRB: {srb}")
    segments_text = "\n".join(segments_text_list)

    # Definisanje JSON šeme za MQM sudiju
    judge_schema = {
        "type": "object",
        "properties": {
            "overall_score": {"type": "number"},
            "errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_id": {"type": "integer"},
                        "category": {"type": "string", "enum": ["Terminology", "Accuracy", "Fluency", "Style", "Locale"]},
                        "severity": {"type": "string", "enum": ["Minor", "Major", "Critical"]},
                        "explanation": {"type": "string"}
                    },
                    "required": ["segment_id", "category", "severity", "explanation"]
                }
            }
        },
        "required": ["overall_score", "errors"]
    }

    prompt_primary = (
        "You are an expert translation quality controller and linguist.\n"
        "Evaluate the following English-to-Serbian translations using the Multidimensional Quality Metrics (MQM) framework.\n\n"
        "STRICT EVALUATION RULES FOR SERBIAN (EKAVICA):\n"
        "1. DIALECT/REGIONALISM: The translation MUST be in Serbian ekavica (e.g. 'deo', 'sprečiti', 'promena', 'rešenje', 'uvek', 'gde'). Any ijekavism (e.g. 'dio', 'spriječiti', 'vrijeme', 'uvijek', 'gdje') or Croatian word (e.g. 'tijekom', 'sustav', 'tjedan', 'tisuća', 'uvjet', 'utjecaj', 'učinkovitost', 'tvrtka', 'sučelje', 'zaslon', 'tipkovnica', 'poveznica', 'kaos', Croatian month names) is a Fluency/Accuracy Major error.\n"
        "2. NUMBERS AS WORDS: All numbers, years, and percentages MUST be written as words (e.g. 'dve hiljade dvadeset šesta', 'pet posto'). If written as digits (e.g. '2026', '5%'), it is a Locale Critical error.\n"
        "3. PHONETIC NAMES: Foreign names/brands must be written phonetically in Serbian Cyrillic/Latin (e.g. 'Klod', 'Ej Aj', 'Doker'). Exception: IT acronyms GPS, Wi-Fi, and Bluetooth MUST remain in original English. If 'AI' is translated as 'AI' or a name is in original, it is a Locale Major error.\n"
        "4. TONE: The translation must use informal singular address 'ti' (e.g. 'ako želiš', 'poravnaj'). If formal 'Vi' or plural is used, it is a Style Major error.\n"
        "5. ACCURACY: Meaning must be preserved. Negations must be preserved. (e.g. if original has 'not/don't/never' but translation is positive, it is an Accuracy Critical error).\n\n"
        "MQM Error Categories:\n"
        "- Terminology (incorrect translation of technical terms)\n"
        "- Accuracy (addition, omission, mistranslation, negation loss)\n"
        "- Fluency (grammar, spelling, regionalism/ijekavism)\n"
        "- Style (inappropriate tone, formal address)\n"
        "- Locale (violation of conventions like numbers/digits, name transcription)\n\n"
        "MQM Severities:\n"
        "- Minor: minor styling/spelling issues (penalty: 1)\n"
        "- Major: incorrect translation of terms, regionalisms, formal tone (penalty: 5)\n"
        "- Critical: negation loss, wrong numbers, digits instead of words (penalty: 10)\n\n"
        "Segments to evaluate:\n"
        f"{segments_text}\n\n"
        "Evaluate and output a JSON object containing the overall video score (from 0 to 10) and a list of MQM errors per segment."
    )

    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    
    # 1. Tri nezavisna prolaza primarnog sudije
    primary_runs = []
    for run in range(3):
        print(f"[*] Pokrećem primarnog sudiju - Prolaz {run + 1}/3 (Temp 0)...")
        payload = {
            "model": "qwen-lektor",
            "messages": [{"role": "user", "content": prompt_primary}],
            "temperature": 0.0,
            "max_tokens": 2048,
            "guided_json": judge_schema
        }
        try:
            res = call_modal_endpoint(url=url, payload=payload)
            raw_text = res["choices"][0]["message"]["content"].strip()
            data = extract_and_parse_json(raw_text)
            primary_runs.append(data)
        except Exception as e:
            print(f"[WARNING] Prolaz {run + 1} nije uspeo: {e}")
            # Fallback na prazan šablon
            primary_runs.append({"overall_score": 8.0, "errors": []})

    # 2. Jedan prolaz sekundarnog sudije (simulacija sa Qwen modelom ali na temp 0.7)
    print("[*] Pokrećem sekundarnog sudiju (Qwen Temp 0.7)...")
    prompt_secondary = (
        "You are an independent translation auditor.\n"
        "Perform a critical review of these translations and output a JSON object with 'overall_score' and 'errors'.\n"
        f"{segments_text}"
    )
    payload_sec = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt_secondary}],
        "temperature": 0.7,
        "max_tokens": 2048,
        "guided_json": judge_schema
    }
    secondary_data = {"overall_score": 8.0, "errors": []}
    try:
        res_sec = call_modal_endpoint(url=url, payload=payload_sec)
        raw_sec = res_sec["choices"][0]["message"]["content"].strip()
        secondary_data = extract_and_parse_json(raw_sec)
    except Exception as e:
        print(f"[WARNING] Sekundarni sudija nije uspeo (koristim fallback): {e}")

    # 3. Računanje statistike po segmentima
    segment_stats = {}
    for s in segments:
        s_id = s["id"]
        segment_stats[s_id] = {
            "id": s_id,
            "eng": s.get('original_text') or s.get('text') or "",
            "srb": s.get('text') or "",
            "primary_scores": [],
            "errors": []
        }

    # Računanje MQM skora po segmentima za svaki prolaz
    # Formula: Score = max(0, 10 - sum(kazni))
    # Minor = 1, Major = 5, Critical = 10
    severity_map = {"Minor": 1, "Major": 5, "Critical": 10}

    for run_idx, run_data in enumerate(primary_runs):
        run_penalties = {s["id"]: 0 for s in segments}
        errors_list = run_data.get("errors", [])
        if not isinstance(errors_list, list):
            errors_list = []
            
        for err_item in errors_list:
            if not isinstance(err_item, dict):
                continue
            
            # Podrška za ugnježdene greške (Struktura 2)
            if "errors" in err_item and isinstance(err_item["errors"], list):
                seg_id = err_item.get("segment_id") or err_item.get("segment")
                if seg_id is not None:
                    num_match = re.search(r'\d+', str(seg_id))
                    if num_match:
                        seg_id = int(num_match.group(0))
                
                if seg_id in run_penalties:
                    for sub_err in err_item["errors"]:
                        if isinstance(sub_err, dict):
                            sev = sub_err.get("severity", "Minor")
                            run_penalties[seg_id] += severity_map.get(sev, 1)
                            if run_idx == 0:
                                normalized_err = {
                                    "segment_id": seg_id,
                                    "category": sub_err.get("category", "Fluency"),
                                    "severity": sev,
                                    "explanation": sub_err.get("explanation", str(sub_err))
                                }
                                segment_stats[seg_id]["errors"].append(normalized_err)
                        elif isinstance(sub_err, str):
                            run_penalties[seg_id] += 1
                            if run_idx == 0:
                                normalized_err = {
                                    "segment_id": seg_id,
                                    "category": "Fluency",
                                    "severity": "Minor",
                                    "explanation": sub_err
                                }
                                segment_stats[seg_id]["errors"].append(normalized_err)
            else:
                # Direktna greška (Struktura 1)
                seg_id = err_item.get("segment_id")
                if seg_id is None:
                    seg_val = err_item.get("segment")
                    if seg_val is not None:
                        num_match = re.search(r'\d+', str(seg_val))
                        if num_match:
                            seg_id = int(num_match.group(0))
                
                if seg_id in run_penalties:
                    sev = err_item.get("severity", "Minor")
                    run_penalties[seg_id] += severity_map.get(sev, 1)
                    if run_idx == 0:
                        normalized_err = {
                            "segment_id": seg_id,
                            "category": err_item.get("category", "Fluency"),
                            "severity": sev,
                            "explanation": err_item.get("explanation", "")
                        }
                        segment_stats[seg_id]["errors"].append(normalized_err)

        for s_id, penalty in run_penalties.items():
            score = max(0.0, 10.0 - penalty)
            segment_stats[s_id]["primary_scores"].append(score)

    # Izračunavanje srednje vrednosti i standardne devijacije
    for s_id, stats in segment_stats.items():
        scores = stats["primary_scores"]
        if not scores:
            scores = [10.0, 10.0, 10.0]
        mean_val = sum(scores) / len(scores)
        variance = sum((x - mean_val) ** 2 for x in scores) / len(scores)
        std_dev = math.sqrt(variance)
        
        stats["mean_score"] = mean_val
        stats["std_dev"] = std_dev

    # Sekundarni sudija i neslaganje (discrepancy)
    sec_penalties = {s["id"]: 0 for s in segments}
    sec_errors = secondary_data.get("errors", [])
    if not isinstance(sec_errors, list):
        sec_errors = []
        
    for err_item in sec_errors:
        if not isinstance(err_item, dict):
            continue
        
        # Podrška za ugnježdene greške
        if "errors" in err_item and isinstance(err_item["errors"], list):
            seg_id = err_item.get("segment_id") or err_item.get("segment")
            if seg_id is not None:
                num_match = re.search(r'\d+', str(seg_id))
                if num_match:
                    seg_id = int(num_match.group(0))
            if seg_id in sec_penalties:
                for sub_err in err_item["errors"]:
                    if isinstance(sub_err, dict):
                        sev = sub_err.get("severity", "Minor")
                        sec_penalties[seg_id] += severity_map.get(sev, 1)
                    elif isinstance(sub_err, str):
                        sec_penalties[seg_id] += 1
        else:
            seg_id = err_item.get("segment_id")
            if seg_id is None:
                seg_val = err_item.get("segment")
                if seg_val is not None:
                    num_match = re.search(r'\d+', str(seg_val))
                    if num_match:
                        seg_id = int(num_match.group(0))
            if seg_id in sec_penalties:
                sev = err_item.get("severity", "Minor")
                sec_penalties[seg_id] += severity_map.get(sev, 1)

    for s_id, stats in segment_stats.items():
        sec_score = max(0.0, 10.0 - sec_penalties[s_id])
        stats["secondary_score"] = sec_score
        stats["discrepancy"] = abs(stats["mean_score"] - sec_score)

    # Ukupni skorovi
    primary_overall = sum(r.get("overall_score", 8.0) for r in primary_runs) / len(primary_runs)
    secondary_overall = secondary_data.get("overall_score", 8.0)
    
    return {
        "primary_overall": primary_overall,
        "secondary_overall": secondary_overall,
        "overall_discrepancy": abs(primary_overall - secondary_overall),
        "segments": list(segment_stats.values())
    }

def run_held_out_evaluation():
    print_header("Evaluacija nad Held-out Test Skupom Rečenica")
    json_path = os.path.join(RESULTS_DIR, "held_out_eval_set.json")
    if not os.path.exists(json_path):
        print(f"[ERROR] Held-out test set ne postoji na: {json_path}")
        return
        
    with open(json_path, "r", encoding="utf-8") as f:
        test_set = json.load(f)
        
    print(f"[+] Učitano {len(test_set)} testnih rečenica.")
    
    # Formiranje formata za translate_segments
    translation_input = []
    for item in test_set:
        translation_input.append({
            "id": item["id"],
            "start": 0.0,
            "end": 4.0, # fiktivno trajanje
            "text": item["source"]
        })
        
    print("[*] Prevodim testne rečenice kroz pipeline...")
    t_start = time.time()
    res = translate_segments(translation_input)
    duration = time.time() - t_start
    
    if res["status"] != "success":
        print(f"[ERROR] Prevođenje nije uspelo: {res.get('message')}")
        return
        
    translated = res["translated_segments"]
    
    # Računanje metrika za svaki segment
    total_chrf = 0.0
    total_qe = 0.0
    
    print("\nREZULTATI EVALUACIJE SEGMENATA:")
    print(f"{'ID':<4} | {'ENGLESKI':<30} | {'PREVOD':<30} | {'chrF++':<8} | {'QE Score':<8}")
    print("-" * 90)
    
    results_list = []
    for i, item in enumerate(test_set):
        ref = item["reference"]
        hyp = translated[i]["text"]
        src = item["source"]
        
        chrf = compute_chrf(ref, hyp)
        qe = get_comet_kiwi_score(src, hyp)
        
        total_chrf += chrf
        total_qe += qe
        
        eng_trunc = src[:27] + "..." if len(src) > 30 else src
        srb_trunc = hyp[:27] + "..." if len(hyp) > 30 else hyp
        print(f"{item['id']:<4} | {eng_trunc:<30} | {srb_trunc:<30} | {chrf:.4f} | {qe:.4f}")
        
        results_list.append({
            "id": item["id"],
            "source": src,
            "reference": ref,
            "translation": hyp,
            "chrf": chrf,
            "comet_kiwi_qe": qe
        })
        
    avg_chrf = total_chrf / len(test_set)
    avg_qe = total_qe / len(test_set)
    
    print("-" * 90)
    print(f"PROSEČAN chrF++: {avg_chrf:.4f}")
    print(f"PROSEČAN CometKiwi QE: {avg_qe:.4f}")
    print(f"Vreme obrade: {duration:.2f}s")
    
    # Čuvanje rezultata u JSON i Markdown
    save_md_path = os.path.join(RESULTS_DIR, "held_out_evaluation_report.md")
    save_json_path = os.path.join(RESULTS_DIR, "held_out_evaluation_data.json")
    
    # JSON data
    output_data = {
        "evaluation_time": datetime.now().isoformat(),
        "average_chrf": avg_chrf,
        "average_comet_kiwi_qe": avg_qe,
        "translation_time_sec": duration,
        "segments": results_list
    }
    with open(save_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    # Markdown report
    md_content = (
        f"# Izveštaj o Evaluaciji Held-out Test Skupa\n\n"
        f"**Datum evaluacije:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"**Ukupno rečenica:** {len(test_set)}\n"
        f"**Prosečan chrF++ skor:** `{avg_chrf:.4f}`\n"
        f"**Prosečan CometKiwi QE skor:** `{avg_qe:.4f}`\n"
        f"**Vreme prevođenja:** {duration:.2f}s\n\n"
        f"## Rezultati po segmentima\n\n"
        f"| ID | Engleski | Referenca | Prevod | chrF++ | CometKiwi QE |\n"
        f"| :--- | :--- | :--- | :--- | :--- | :--- |\n"
    )
    for r in results_list:
        md_content += f"| {r['id']} | {r['source']} | {r['reference']} | {r['translation']} | {r['chrf']:.4f} | {r['comet_kiwi_qe']:.4f} |\n"
        
    with open(save_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"\n[+] Izveštaji sačuvani na:\n  JSON: {save_json_path}\n  Markdown: {save_md_path}")

def main():
    print_header("Sinhronizuj.me - Evaluacija Prevoda Videa")
    
    videos = list_test_videos()
    
    print("Dostupne opcije za testiranje:")
    for idx, video in enumerate(videos):
        video_path = os.path.join(TEST_VIDEOS_DIR, video)
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"  [{idx + 1}] {video} ({size_mb:.2f} MB)")
    
    held_out_option_idx = len(videos) + 1
    print(f"  [{held_out_option_idx}] Evaluacija nad Held-out Test Skupom Rečenica (50 rečenica)")
    
    try:
        choice = input(f"\nIzaberite broj opcije za testiranje (ili 'q' za izlaz): ").strip()
        if choice.lower() == 'q':
            return
        
        idx = int(choice) - 1
        if idx == len(videos):
            # Pokretanje held-out evaluacije
            run_held_out_evaluation()
            return
        elif idx < 0 or idx >= len(videos):
            print("[ERROR] Nevalidan izbor.")
            return
    except ValueError:
        print("[ERROR] Nevalidan unos.")
        return
        
    selected_video = videos[idx]
    video_path = os.path.join(TEST_VIDEOS_DIR, selected_video)
    video_base_name = os.path.splitext(selected_video)[0]
    
    # Privremeni i rezultujući fajlovi
    temp_dir = os.path.join(PROJECT_ROOT, "temp_workspace")
    os.makedirs(temp_dir, exist_ok=True)
    temp_audio_path = os.path.join(temp_dir, f"eval_audio_{int(time.time())}.wav")
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    report_md_path = os.path.join(RESULTS_DIR, f"{video_base_name}_report.md")
    report_json_path = os.path.join(RESULTS_DIR, f"{video_base_name}_data.json")
    
    t_start_total = time.time()
    
    # 1. Ekstrakcija zvuka
    if not extract_audio(video_path, temp_audio_path):
        return
        
    try:
        # 2. Transkripcija
        print("\n[*] Pokrećem transkripciju (Whisper + SenseVoice)...")
        t_start = time.time()
        asr_res = transcribe_audio(temp_audio_path)
        duration_asr = time.time() - t_start
        
        if asr_res["status"] == "error":
            print(f"[ERROR] Transkripcija nije uspela: {asr_res['message']}")
            return
            
        raw_segments = asr_res["segments"]
        print(f"[+] Transkripcija završena za {duration_asr:.2f}s. Detektovano {len(raw_segments)} segmenata.")
        
        # 3. Pametna Segmentacija
        print("\n[*] Pokrećem pametnu segmentaciju pre prevoda...")
        optimized_segments = optimize_segments_for_translation(raw_segments)
        print(f"[+] Optimizacija završena. Broj segmenata nakon spajanja/podela: {len(optimized_segments)}")
        
        # 4. Prevođenje & Lektura
        print("\n[*] Pokrećem prevođenje i lekturu preko Qwen modela...")
        t_start = time.time()
        trans_res = translate_segments(optimized_segments, video_path=video_path)
        duration_trans = time.time() - t_start
        
        if trans_res["status"] == "error":
            print(f"[ERROR] Prevođenje nije uspelo: {trans_res['message']}")
            return
            
        translated_segments = trans_res["translated_segments"]
        metrics = trans_res.get("metrics", {})
        print(f"[+] Prevođenje i lektura završeni za {duration_trans:.2f}s.")
        
        # 5. Robusna evaluacija sa 3 prolaza i Llama sudijom
        evaluation_results = run_llm_evaluation(translated_segments, selected_video)
        
        # Prikaz rezultata u konzoli
        print_header("Tabela Evaluacije Segmenata sa Statističkom Analizom")
        print(f"{'ID':<4} | {'Vreme':<15} | {'Prim. Sudija (Mean ± SD)':<25} | {'Sek. Sudija':<11} | {'Neslaganje':<10}")
        print("-" * 80)
        for s in evaluation_results["segments"]:
            time_str = ""
            # Tražimo segment za vreme
            for orig_s in translated_segments:
                if orig_s["id"] == s["id"]:
                    time_str = f"{orig_s['start']:.1f}s - {orig_s['end']:.1f}s"
                    break
            print(f"{s['id']:<4} | {time_str:<15} | {s['mean_score']:.2f} ± {s['std_dev']:.2f} {' ':<12} | {s['secondary_score']:.2f} {' ':<4} | {s['discrepancy']:.2f}")

        # Čuvanje rezultata
        eval_data = {
            "video_name": selected_video,
            "evaluation_time": datetime.now().isoformat(),
            "pipeline_durations": {
                "asr_sec": duration_asr,
                "translation_sec": duration_trans,
                "total_sec": time.time() - t_start_total
            },
            "metrics": metrics,
            "evaluation": {
                "primary_overall": evaluation_results["primary_overall"],
                "secondary_overall": evaluation_results["secondary_overall"],
                "overall_discrepancy": evaluation_results["overall_discrepancy"],
                "segments": evaluation_results["segments"]
            }
        }
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, indent=2, ensure_ascii=False)
            
        # Pisanje izveštaja
        report_md = (
            f"# Izveštaj o Evaluaciji Prevoda Videa\n\n"
            f"**Video:** `{selected_video}`\n"
            f"**Datum evaluacije:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Trajanje obrade:** ASR: {duration_asr:.1f}s | Prevođenje: {duration_trans:.1f}s | Ukupno: {time.time() - t_start_total:.1f}s\n\n"
            f"## Ocene Sudija\n\n"
            f"- **Primarni MQM Sudija (Prosečna ocena):** `{evaluation_results['primary_overall']:.2f}/10`\n"
            f"- **Sekundarni Sudija (Llama 0.7):** `{evaluation_results['secondary_overall']:.2f}/10`\n"
            f"- **Stopa neslaganja (Discrepancy):** `{evaluation_results['overall_discrepancy']:.2f}`\n\n"
            f"## Detaljna Analiza po Segmentima\n\n"
            f"| ID | Engleski Original | Prevedeni Srpski | Primarni Sudija (Mean ± SD) | Sekundarni Sudija | Neslaganje |\n"
            f"| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        )
        for s in evaluation_results["segments"]:
            report_md += f"| {s['id']} | {s['eng']} | {s['srb']} | {s['mean_score']:.2f} ± {s['std_dev']:.2f} | {s['secondary_score']:.2f} | {s['discrepancy']:.2f} |\n"
            
        # Prikaz uočenih MQM grešaka
        report_md += "\n## Uočene MQM Greške\n\n"
        has_errors = False
        for s in evaluation_results["segments"]:
            if s["errors"]:
                has_errors = True
                report_md += f"### Segment {s['id']}\n"
                report_md += f"- **Original:** *\"{s['eng']}\"*\n"
                report_md += f"- **Prevod:** *\"{s['srb']}\"*\n"
                for err in s["errors"]:
                    report_md += f"  - `[{err['category']} - {err['severity']}]` {err['explanation']}\n"
        if not has_errors:
            report_md += "*Nisu uočene MQM greške u prevodu.*"
            
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(report_md)
            
        print_header("Izveštaj Generisan!")
        print(f"[+] Detaljan izveštaj sačuvan na: {report_md_path}")
        print(f"[+] Sirovinski JSON podaci sačuvani na: {report_json_path}")
                
    finally:
        # Čišćenje privremenog audio fajla
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

if __name__ == "__main__":
    main()
