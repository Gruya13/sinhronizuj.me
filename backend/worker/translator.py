import requests
import json
from typing import List, Dict
from backend.core.config import settings

def translate_segments(segments: list) -> dict:
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
    
    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_TRANSLATOR_ID}/runsync"
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

    print(f"[TRANSLATOR V2] Šaljem {len(segments)} segmenata na RunPod Qwen...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "COMPLETED":
            translated_toon = result["output"]["translated_segments"]
            
            # Parsiranje TOON formata nazad u JSON objekte
            # Očekivani format: "[start|end|prevod]"
            final_segments = []
            for toon_str in translated_toon:
                try:
                    # Uklanjamo zagrade i splitujemo po |
                    clean = toon_str.strip("[]")
                    parts = clean.split("|")
                    if len(parts) >= 3:
                        final_segments.append({
                            "start": float(parts[0]),
                            "end": float(parts[1]),
                            "text": "|".join(parts[2:]) # u slučaju da prevod sadrži |
                        })
                except:
                    continue
                    
            return {
                "status": "success",
                "translated_segments": final_segments
            }
        else:
            raise Exception(f"RunPod Translator greška: {result}")
            
    except Exception as e:
        return {"status": "error", "message": str(e)}
