import os
import sys
import json
import time
import subprocess
import re
from datetime import datetime

# Dodavanje korena projekta u sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Učitavanje konfiguracije
from backend.core.config import settings
from backend.worker.transcriber import transcribe_audio
from backend.worker.segment_optimizer import optimize_segments_for_translation
from backend.worker.translator import translate_segments
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

def run_llm_evaluation(segments, video_name):
    print("[*] Pokrećem LLM-as-a-judge evaluaciju prevoda...")
    
    # Formiranje teksta segmenata za prompt - optimizovana dužina da ne pređe 4096 limit
    segments_text_list = []
    for s in segments:
        duration = s["end"] - s["start"]
        eng = s.get('original_text') or s.get('text') or ""
        srb = s.get('text') or ""
        segments_text_list.append(
            f"[Seg {s['id']}] ({duration:.1f}s) ENG: {eng} | SRB: {srb}"
        )
    segments_text = "\n".join(segments_text_list)
    
    prompt = (
        "You are an expert translation quality controller and linguist.\n"
        "Analyze the following English-to-Serbian translation of a video transcript.\n"
        "Evaluate the translation based on the following criteria:\n"
        "1. Accuracy (Is the meaning preserved? Are there any mistranslations?)\n"
        "2. Tone and Naturalness (Does it sound natural in Serbian? Is the register correct for the genre?)\n"
        "3. Glossary Alignment (Are technical terms, brands, and entities translated correctly and consistently?)\n"
        "4. Segment Length & Speech Tempo (Are there segments that are too long to be spoken comfortably within their duration? Remember, Serbian translations are often 20-30% longer than English.)\n\n"
        "Here are the translated segments with their duration, original English text, and translated Serbian text:\n"
        f"{segments_text}\n\n"
        "Provide a report in Serbian language.\n"
        "Your response MUST start with the quality score section: '## Ocena kvaliteta: X/10' (e.g. 8.5/10).\n"
        "Then include the following sections:\n"
        "- ## Rezime kvaliteta prevoda\n"
        "- ## Detaljna analiza po kriterijumima (Budi sažet, maksimalno 1-2 primera po kriterijumu)\n"
        "- ## Spisak segmenata sa najvažnijim greškama (Navedi maksimalno 3 najvažnija segmenta sa greškama da bi izveštaj stao u limit tokena)\n"
        "- ## Preporuke za unapređenje\n\n"
        "VAŽNO ZA REZONOVANJE: U svom procesu razmišljanja (<think>...</think>) budi izuzetno kratak (do 50 reči). NIKADA nemoj detaljno analizirati segment po segment unutar <think> tagova.\n\n"
        "Write your response in Markdown format. Do not include any tags like <thought> or markdown code blocks around the report itself, just start writing the markdown content."
    )
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1100
    }
    
    try:
        res = call_modal_endpoint(url=url, payload=payload)
        content = res["choices"][0]["message"]["content"].strip()
        
        # Čišćenje thought tagova ako ih ima
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL).strip()
        if content.startswith("```markdown"):
            content = content[11:].strip()
        if content.startswith("```"):
            content = content[3:].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
            
        print("[+] LLM evaluacija uspešno završena.")
        return content
    except Exception as e:
        print(f"[ERROR] Greška pri pozivu LLM sudije: {e}")
        return None

def main():
    print_header("Sinhronizuj.me - Evaluacija Prevoda Videa")
    
    videos = list_test_videos()
    if not videos:
        print("Nema dostupnih test video fajlova u 'Test videos' folderu.")
        return
        
    print("Dostupni test video fajlovi:")
    for idx, video in enumerate(videos):
        video_path = os.path.join(TEST_VIDEOS_DIR, video)
        # Izračunavanje veličine
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"  [{idx + 1}] {video} ({size_mb:.2f} MB)")
        
    try:
        choice = input("\nIzaberite broj videa za testiranje (ili 'q' za izlaz): ").strip()
        if choice.lower() == 'q':
            return
        
        idx = int(choice) - 1
        if idx < 0 or idx >= len(videos):
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
        
        # Prikaz prevoda u konzoli
        print_header("Tabela Prevedenih Segmenata")
        print(f"{'ID':<4} | {'Vreme':<15} | {'Pouzdanost':<10} | {'Prevod (Srpski)'}")
        print("-" * 80)
        for s in translated_segments:
            duration = s["end"] - s["start"]
            time_str = f"{s['start']:.2f}s - {s['end']:.2f}s"
            confidence = f"{s.get('confidence_score', 5)}/5"
            text_preview = s["text"][:50] + "..." if len(s["text"]) > 50 else s["text"]
            print(f"{s['id']:<4} | {time_str:<15} | {confidence:<10} | {text_preview}")
            
        # 5. LLM Sudija Evaluacija
        print("\n[*] Pripremam podatke za LLM sudiju...")
        judge_report = run_llm_evaluation(translated_segments, selected_video)
        
        # Čuvanje rezultata
        # 1. JSON Data
        eval_data = {
            "video_name": selected_video,
            "evaluation_time": datetime.now().isoformat(),
            "pipeline_durations": {
                "asr_sec": duration_asr,
                "translation_sec": duration_trans,
                "total_sec": time.time() - t_start_total
            },
            "segments": translated_segments,
            "metrics": metrics
        }
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, indent=2, ensure_ascii=False)
            
        # 2. Markdown Report
        full_report_md = (
            f"# Izveštaj o Evaluaciji Prevoda Videa\n\n"
            f"**Video:** `{selected_video}`\n"
            f"**Datum evaluacije:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Trajanje obrade:** ASR: {duration_asr:.1f}s | Prevođenje: {duration_trans:.1f}s | Ukupno: {time.time() - t_start_total:.1f}s\n\n"
            f"---\n\n"
        )
        if judge_report:
            full_report_md += judge_report
        else:
            full_report_md += "*Greška prilikom generisanja LLM izveštaja sudije.*"
            
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(full_report_md)
            
        print_header("Izveštaj Generisan!")
        print(f"[+] Detaljan izveštaj sačuvan na: {report_md_path}")
        print(f"[+] Sirovinski JSON podaci sačuvani na: {report_json_path}")
        
        if judge_report:
            print("\nSAŽETAK IZVEŠTAJA SUDIJE:")
            # Prikaz prvih 25 linija izveštaja
            report_lines = judge_report.split("\n")
            for line in report_lines[:30]:
                print(line)
            if len(report_lines) > 30:
                print("\n... (pogledajte kompletan izveštaj u generisanom Markdown fajlu) ...")
                
    finally:
        # Čišćenje privremenog audio fajla
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

if __name__ == "__main__":
    import re
    main()
