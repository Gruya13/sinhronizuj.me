import requests
import json
import cv2
import base64
import os
import time
from typing import List, Dict
from backend.core.config import settings
from backend.worker.utils import wait_for_runpod_result

def extract_video_frames(video_path: str, num_frames: int = 10) -> List[str]:
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
    Poziva RunPod Serverless Translator (Qwen-VL) koristeći multimodalni OpenAI Vision format.
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

    # Priprema multimodalnog content-a (OpenAI Vision format)
    prompt_text = (
        f"Ovo je transkript videa: {' '.join(toon_input)}. "
        "Prevedi ga na srpski (latinica) koristeći isti [start|end|tekst] TOON format. "
        "Koristi priložene frejmove kao vizuelni kontekst za tačan prevod (pol govornika, emocije, objekti u sceni)."
    )

    content = [{"type": "text", "text": prompt_text}]
    for b64 in frames_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })

    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_TRANSLATOR_ID}/run"
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": {
            "messages": [
                {"role": "user", "content": content}
            ],
            "target_lang": "sr-Latn",
            "format": "toon"
        }
    }

    print(f"[TRANSLATOR VL] Šaljem {len(segments)} segmenata + {len(frames_b64)} frejmova na RunPod (Asinhrono)...")
    
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
