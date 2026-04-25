import requests
import json
from typing import List, Dict
from backend.core.config import settings

def translate_segments(segments: list, progress_callback=None) -> dict:
    """
    Poziva RunPod Serverless Translator (Qwen 32B) koristeći TOON format.
    """
    if not segments:
        return {"status": "success", "translated_segments": []}

    if not settings.RUNPOD_TRANSLATOR_ID:
        print("[WARNING] RUNPOD_TRANSLATOR_ID nije definisan. Vraćam originalni tekst.")
        return {
            "status": "success", 
            "translated_segments": [
                {"start": s["start"], "end": s["end"], "text": s["text"]} 
                for s in segments
            ]
        }

    # TOON (Token Optimized Object Notation) formatiranje
    # [start|end|text] format za uštedu ~40% tokena
    toon_input = [
        f"[{s['start']:.2f}|{s['end']:.2f}|{s['text']}]" 
        for s in segments
    ]
    
    from backend.worker.utils import wait_for_runpod_result
    
    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_TRANSLATOR_ID}/run"
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": {
            "segments": toon_input,
            "target_lang": "sr-Latn",
            "format": "toon"
        }
    }

    print(f"[TRANSLATOR V2] Šaljem {len(segments)} segmenata na RunPod Qwen (Asinhrono)...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["id"]
        
        # Čekamo rezultat (polling)
        output = wait_for_runpod_result(job_id, settings.RUNPOD_TRANSLATOR_ID, progress_callback=progress_callback)
        
        translated_toon = output["translated_segments"]
        
        # Parsiranje TOON formata nazad u JSON objekte
        final_segments = []
        for toon_str in translated_toon:
            try:
                clean = toon_str.strip("[]")
                parts = clean.split("|")
                if len(parts) >= 3:
                    final_segments.append({
                        "start": float(parts[0]),
                        "end": float(parts[1]),
                        "text": "|".join(parts[2:])
                    })
            except:
                continue
                
        return {
            "status": "success",
            "translated_segments": final_segments
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
