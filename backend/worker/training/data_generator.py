import os
import re
import json
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.models import Segment, Project

def generate_paraphrases(text: str) -> list:
    """
    Poziva Qwen model za generisanje 3 različite i prirodne parafraze.
    """
    if not text:
        return []

    if not settings.MODAL_TRANSLATOR_URL:
        print("[DATA GENERATOR WARNING] MODAL_TRANSLATOR_URL nije konfigurisan. Preskačem parafraziranje.", flush=True)
        return [text, text, text]

    url = f"{settings.MODAL_TRANSLATOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "Ovo je prevod na srpski jezik:\n"
        f"\"{text}\"\n\n"
        "Generiši tačno 3 različite, prirodne i tačne parafraze ovog prevoda na srpskom jeziku (ekavica, latinica).\n"
        "Rečenice neka zvuče prirodno za govor. Izbegavaj krute i robotske prevode.\n"
        "Vrati isključivo JSON listu sa 3 stringa.\n"
    )
    payload = {
        "model": "qwen-translator",
        "messages": [
            {"role": "system", "content": "Ti si stručni lingvistički parafrazer za srpski jezik. Vrati isključivo validan JSON listu sa 3 stringa."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 1000,
        "guided_json": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3
        }
    }

    try:
        from backend.worker.utils import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=45)
        content = res["choices"][0]["message"]["content"].strip()
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL).strip()
        
        from backend.worker.translation.lektor import extract_and_parse_json
        data = extract_and_parse_json(content)
        if isinstance(data, list) and len(data) == 3:
            return data
    except Exception as e:
        print(f"[DATA GENERATOR WARNING] Greška pri parafraziranju: {e}", flush=True)
    return [text, text, text]

def run_data_generation(user_id: str = None):
    """
    Ekstrahuje 'Zlatne' prevode i korisničke ispravke, parafrazira ih i kreira dataset.
    Ako je prosleđen user_id, izoluje podatke samo za tog korisnika.
    """
    print(f"[DATA GENERATOR] Započinjem generisanje skupa podataka za finetuning (user_id={user_id})...", flush=True)
    db = SessionLocal()
    try:
        if user_id:
            import uuid
            if isinstance(user_id, str):
                try:
                    user_uuid = uuid.UUID(user_id)
                except ValueError:
                    user_uuid = user_id
            else:
                user_uuid = user_id

            # Filtriramo samo segmente koji pripadaju projektima datog korisnika
            segments = db.query(Segment).join(Project).filter(
                Project.user_id == user_uuid,
                (((Segment.qe_score > 0.92) & (Segment.confidence_score > 4.5)) |
                 (Segment.status == 'edited'))
            ).all()
        else:
            # Zlatni parovi: qe_score > 0.92 i confidence_score > 4.5
            # Korisničke ispravke: status == 'edited'
            segments = db.query(Segment).filter(
                ((Segment.qe_score > 0.92) & (Segment.confidence_score > 4.5)) |
                (Segment.status == 'edited')
            ).all()

        print(f"[DATA GENERATOR] Pronađeno {len(segments)} adekvatnih segmenata u bazi.", flush=True)
        if not segments:
            return {"status": "success", "examples_generated": 0, "message": "Nema segmenata koji ispunjavaju kriterijume."}

        # Sakupimo jedinstvene prevode radi optimizacije (deduplikacije) i paralelnog rada
        unique_translations = list(set(s.translated for s in segments if s.original and s.translated))
        
        # Paralelno parafraziranje pomoću ThreadPoolExecutor-a
        from concurrent.futures import ThreadPoolExecutor
        paraphrases_map = {}
        max_workers = min(16, len(unique_translations)) if unique_translations else 1
        
        if unique_translations:
            print(f"[DATA GENERATOR] Parafraziram {len(unique_translations)} jedinstvenih prevoda sa {max_workers} thread-ova...", flush=True)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_text = {executor.submit(generate_paraphrases, text): text for text in unique_translations}
                for future in future_to_text:
                    text = future_to_text[future]
                    try:
                        paraphrases_map[text] = future.result()
                    except Exception as e:
                        print(f"[DATA GENERATOR WARNING] Greška u threadu za parafraze: {e}", flush=True)
                        paraphrases_map[text] = [text, text, text]

        system_prompt = (
            "Prevodi kao da si iskusni sinhronizator. Rečenice neka zvuče kao da ih izgovara "
            "profesionalni voditelj emisije ili narator, a ne profesor lingvistike. Koristi kolokvijalne "
            "i prirodne fraze gde god je to adekvatno (npr. 'naravno' umesto 'prirodno', 'evo' umesto 'ovde'), "
            "prilagođavajući red reči duhu srpskog govornog jezika."
        )

        output_dir = "/models/training" if os.path.exists("/models") else os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../scratch"))
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "training_data.jsonl")

        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for s in segments:
                if not s.original or not s.translated:
                    continue

                # Uzmi originalni prevod + 3 parafraze
                targets = [s.translated]
                paraphrases = paraphrases_map.get(s.translated, [s.translated, s.translated, s.translated])
                targets.extend(paraphrases)

                for t in set(targets):
                    if not t:
                        continue
                    item = {
                        "system": system_prompt,
                        "instruction": "Prevedi na srpski",
                        "input": s.original,
                        "output": t
                    }
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    count += 1

        if os.path.exists("/models"):
            try:
                import modal
                vol = modal.Volume.from_name("sinhronizuj-models")
                vol.commit()
                print("[DATA GENERATOR] Commitovan Modal Volume 'sinhronizuj-models'", flush=True)
            except Exception as e:
                print(f"[DATA GENERATOR WARNING] Nije uspeo commit na Modal Volume: {e}", flush=True)

        print(f"[DATA GENERATOR SUCCESS] Skup podataka uspešno kreiran. Ukupno primera: {count}. Lokacija: {output_path}", flush=True)
        return {"status": "success", "examples_generated": count, "output_path": output_path}
    except Exception as e:
        print(f"[DATA GENERATOR ERROR] Greška u run_data_generation: {e}", flush=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
