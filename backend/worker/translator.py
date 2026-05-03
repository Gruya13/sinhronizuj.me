import requests
import json
import cv2
import base64
import os
import time
from typing import List, Dict
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

def extract_video_frames(video_path: str, num_frames: int = 1) -> List[str]:
    """
    Izvlači num_frames frejmova iz videa i vraća ih kao Base64 stringove.
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
    print(f"[MULTIMODAL] Izvučeno {len(frames_b64)} frejmova za vizuelni kontekst.")
    return frames_b64

def translate_segments(segments: list, video_path: str = None, progress_callback=None) -> dict:
    """
    Poziva Modal Serverless Translator (Qwen-VL) koristeći multimodalni OpenAI Vision format.
    """
    if not segments:
        return {"status": "success", "translated_segments": []}

    if not settings.MODAL_STT_LLM_URL:
        print("[WARNING] MODAL_STT_LLM_URL nije definisan. Vraćam originalni tekst.")
        return {
            "status": "success", 
            "translated_segments": [
                {"start": s["start"], "end": s["end"], "text": s["text"]} 
                for s in segments
            ]
        }

    # Priprema JSON ulaza za bolju pouzdanost
    json_input = [
        {"id": i, "text": s["text"]} 
        for i, s in enumerate(segments)
    ]
    
    # Ekstrakcija frejmova za vizuelni kontekst
    frames_b64 = []
    if video_path:
        if progress_callback:
            progress_callback(detail="Analiza vizuelnog konteksta (ekstrakcija frejmova)...")
        frames_b64 = extract_video_frames(video_path)

    # Priprema multimodalnog content-a
    prompt_text = (
        "Ti si ekspert za prevođenje video titlova. Tvoj zadatak je da prevedeš transkript na SRPSKI jezik (EKAVICA). \n"
        "PRAVILA:\n"
        "1. MORAŠ vratiti odgovor kao JSON LISTU OBJEKATA: [{\"id\": 0, \"text\": \"prevod\"}, ...]\n"
        "2. Prevod mora biti DOSLOVAN (rečenica po rečenica), ne smeš prepričavati niti sažimati tekst.\n"
        "3. Zadrži isti broj elemenata u listi kao u ulazu (tačno 17 segmenata).\n"
        "4. Koristi priložene slike da odrediš pol govornika.\n"
        "5. Odgovori ISKLJUČIVO sa JSON nizom, bez ikakvog dodatnog teksta.\n\n"
        f"TRANSKRIPT ZA PREVOD (JSON):\n{json.dumps(json_input, ensure_ascii=False)}"
    )

    payload = {
        "task": "translate",
        "prompt": prompt_text,
        "frames_base64": frames_b64
    }

    print(f"[TRANSLATOR VL] Šaljem {len(segments)} segmenata na Modal (JSON format)...")
    
    try:
        output = call_modal_endpoint(
            url=settings.MODAL_STT_LLM_URL, 
            payload=payload, 
            timeout_seconds=300,
            progress_callback=progress_callback
        )
        
        raw_output = output.get("translation", "")
        print(f"[DEBUG] RAW TRANSLATION OUTPUT: {raw_output[:500]}...", flush=True)
        
        # Pokušaj parsiranja JSON-a
        try:
            # Čistimo eventualni markdown kod blok ako ga model ubaci
            json_str = re.search(r'\[\s*\{.*\}\s*\]', raw_output, re.DOTALL)
            if json_str:
                translated_data = json.loads(json_str.group(0))
            else:
                translated_data = json.loads(raw_output)
                
            final_segments = []
            for i, orig in enumerate(segments):
                # Tražimo prevod po ID-u ili po indexu
                t_text = ""
                if i < len(translated_data):
                    t_text = translated_data[i].get("text", "")
                
                final_segments.append({
                    "start": orig["start"],
                    "end": orig["end"],
                    "text": t_text or orig["text"] # Fallback na original ako fali prevod
                })
            
            return {"status": "success", "translated_segments": final_segments}
            
        except Exception as json_err:
            print(f"[WARNING] JSON parsiranje nije uspelo: {json_err}. Fallback na TOON/Text.")
            # Ovde ostavljamo stari fallback ili prosto vraćamo originalne sa raw textom
            return {
                "status": "success",
                "translated_segments": [
                    {"start": s["start"], "end": s["end"], "text": raw_output if i == 0 else ""}
                    for i, s in enumerate(segments)
                ]
            }
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
                
        return {
            "status": "success",
            "translated_segments": final_segments
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
