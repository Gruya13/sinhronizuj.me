import requests
import json
import cv2
import base64
import os
import time
from typing import List, Dict
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

def extract_video_frames(video_path: str, num_frames: int = 5) -> List[str]:
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

    # TOON (Token Optimized Object Notation) formatiranje
    toon_input = [
        f"[{s['start']:.2f}|{s['end']:.2f}|{s['text']}]" 
        for s in segments
    ]
    
    # Ekstrakcija frejmova za vizuelni kontekst
    frames_b64 = []
    if video_path:
        if progress_callback:
            progress_callback(detail="Analiza vizuelnog konteksta (ekstrakcija frejmova)...")
        frames_b64 = extract_video_frames(video_path)

    # Priprema multimodalnog content-a (Modal worker interno pakuje ovo)
    prompt_text = (
        f"Ovo je transkript videa: {' '.join(toon_input)}. "
        "Prevedi ga na srpski (latinica) koristeći isti [start|end|tekst] TOON format. "
        "Koristi priložene frejmove kao vizuelni kontekst za tačan prevod (pol govornika, emocije, objekti u sceni)."
    )

    payload = {
        "task": "translate",
        "prompt": prompt_text,
        "frames_base64": frames_b64
    }

    print(f"[TRANSLATOR VL] Šaljem {len(segments)} segmenata + {len(frames_b64)} frejmova na Modal (Sinhrono)...")
    
    try:
        output = call_modal_endpoint(
            url=settings.MODAL_STT_LLM_URL, 
            payload=payload, 
            timeout_seconds=300,
            progress_callback=progress_callback
        )
        
        translated_toon_text = output.get("translation", "")
        # Parsiranje TOON formata nazad u JSON objekte (vLLM obično vraća pun string, potrebno je parsirati)
        # Očekujemo da prevod ima strukturu [0.0|2.0|Tekst] ...
        import re
        matches = re.findall(r'\[([^\]]+)\]', translated_toon_text)
        
        final_segments = []
        for match in matches:
            try:
                parts = match.split("|")
                if len(parts) >= 3:
                    final_segments.append({
                        "start": float(parts[0]),
                        "end": float(parts[1]),
                        "text": "|".join(parts[2:])
                    })
            except:
                continue
                
        # Ako regex ne izvuče ništa, možda je vratio bez zagrada, fallback:
        if not final_segments and segments:
            # U slučaju pada parsiranja, vracamo originalni sa translation string-om celim
            print("[WARNING] Nije uspelo TOON parsiranje, koristimo raw text.")
            return {
                "status": "success",
                "translated_segments": [
                    {"start": segments[0]["start"], "end": segments[-1]["end"], "text": translated_toon_text}
                ]
            }
                
        return {
            "status": "success",
            "translated_segments": final_segments
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
