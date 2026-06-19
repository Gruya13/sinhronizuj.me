import os
import json

# Definisanje putanja
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "evaluation_results")
HELD_OUT_PATH = os.path.join(RESULTS_DIR, "held_out_eval_set.json")
LORA_OUTPUT_PATH = os.path.join(RESULTS_DIR, "lora_train_dataset.jsonl")

SYSTEM_PROMPT = (
    "You are an expert English to Serbian translator.\n"
    "Translate the following English segment to Serbian. Follow these rules:\n"
    "1. Serbian language: Use strictly Latin script.\n"
    "2. Dialect: Use strictly Serbian ekavica (e.g., 'deo', 'sprečiti', 'promena', 'rešenje', 'uvek', 'gde'). Avoid ijekavisms and Croatian terms.\n"
    "3. Tone: Use informal, friendly tone with singular address 'ti' (e.g., 'ako želiš', 'poravnaj').\n"
    "4. Numbers: Convert all numbers, years, and percentages to words (e.g., 'dve hiljade dvadeset šesta', 'pet posto').\n"
    "5. Foreign names/brands: Write them phonetically (e.g., 'Klod', 'Ej Aj'). Exception: GPS, Wi-Fi, and Bluetooth must remain in original English."
)

def main():
    print("=" * 60)
    print(" Sinhronizuj.me - Priprema LoRA skupa podataka za Fine-Tune ")
    print("=" * 60)

    if not os.path.exists(HELD_OUT_PATH):
        print(f"[ERROR] Held-out test set ne postoji na: {HELD_OUT_PATH}")
        return

    with open(HELD_OUT_PATH, "r", encoding="utf-8") as f:
        test_set = json.load(f)

    print(f"[+] Učitano {len(test_set)} rečenica iz held-out skupa.")

    # Formiranje JSONL podataka
    dataset_records = []
    for item in test_set:
        source_text = item["source"]
        reference_text = item["reference"]

        record = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": source_text},
                {"role": "assistant", "content": reference_text}
            ]
        }
        dataset_records.append(record)

    # Čuvanje u JSONL formatu
    with open(LORA_OUTPUT_PATH, "w", encoding="utf-8") as f:
        for record in dataset_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[+] LoRA dataset je uspešno generisan!")
    print(f"  Putanja: {LORA_OUTPUT_PATH}")
    print(f"  Ukupno zapisa: {len(dataset_records)}")
    
    # Prikaz jednog primera
    if dataset_records:
        print("\nPrimer zapisa u dataset-u:")
        print(json.dumps(dataset_records[0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
