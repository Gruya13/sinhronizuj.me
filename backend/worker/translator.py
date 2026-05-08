import requests
import json
import cv2
import base64
import os
import time
import re
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

    # Priprema tekstualnog ulaza umesto JSON-a za bolju pouzdanost modela
    transcript_text = ""
    for i, s in enumerate(segments):
        transcript_text += f"{i}|{s['text']}\n"
    
    # Ekstrakcija frejmova za vizuelni kontekst
    frames_b64 = []
    if video_path:
        if progress_callback:
            progress_callback(detail="Analiza vizuelnog konteksta (ekstrakcija frejmova)...")
        frames_b64 = extract_video_frames(video_path)

    # Priprema multimodalnog content-a
    prompt_text = (
        "Ti si vrhunski profesionalni prevodilac za video titlove. Tvoj zadatak je da prevedeš priloženi transkript na SRPSKI jezik (EKAVICA).\n\n"
        "PRAVILA ZA PREVOD:\n"
        "1. Prevod mora biti potpuno PRIRODAN u duhu srpskog jezika. Zadrži originalno značenje bez prepričavanja.\n"
        "2. TEHNIČKI TERMINI: Imena kompanija, alata i IT termina (npr. AI agent, Zoom, LinkedIn, startup) zadrži u originalu. Nemoj ih prevoditi bukvalno.\n"
        "3. POL GOVORNIKA: Pažljivo pogledaj priložene slike iz videa. Ako priča ženska osoba, glagole u prošlom vremenu prebaci u ženski rod (npr. 'rekla je', a ne 'rekao je').\n\n"
        "PRAVILA ZA FORMAT:\n"
        "1. ZABRANJEN JE JSON. Odgovor mora biti ISKLJUČIVO red po red, u sledećem formatu: ID|Prevedeni tekst\n"
        f"2. Tvoj odgovor mora sadržati TAČNO {len(segments)} redova, isto koliko ih ima na ulazu (od 0 do {len(segments)-1}).\n"
        "3. Ne dodaj nikakav uvod, objašnjenje niti zaključak. Vrati samo prevedene redove.\n\n"
        f"TRANSKRIPT ZA PREVOD:\n{transcript_text}"
    )

    payload = {
        "task": "translate",
        "prompt": prompt_text,
        "frames_base64": frames_b64
    }

    print(f"[TRANSLATOR VL] Šaljem {len(segments)} segmenata na Modal (Tekst format)...")
    
    try:
        output = call_modal_endpoint(
            url=settings.MODAL_STT_LLM_URL, 
            payload=payload, 
            timeout_seconds=300,
            progress_callback=progress_callback
        )
        
        raw_output = output.get("translation", "")
        print(f"[DEBUG] RAW TRANSLATION OUTPUT: {raw_output[:500]}...", flush=True)
        
        # Parsiranje tekstualnog izlaza (ID|Tekst)
        try:
            translated_data = {}
            for line in raw_output.split('\n'):
                line = line.strip()
                if not line or '|' not in line:
                    continue
                # Razdvajamo po prvom '|'
                parts = line.split('|', 1)
                if len(parts) == 2:
                    idx_str, text = parts
                    try:
                        idx = int(idx_str.strip())
                        translated_data[idx] = text.strip()
                    except ValueError:
                        continue
                        
            final_segments = []
            for i, orig in enumerate(segments):
                # Ako LLM nije preveo dati ID, radimo fallback na originalni tekst
                t_text = translated_data.get(i, "")
                final_segments.append({
                    "start": orig["start"],
                    "end": orig["end"],
                    "text": t_text or orig["text"]
                })
            
            return {"status": "success", "translated_segments": final_segments}
            
        except Exception as parse_err:
            print(f"[WARNING] Parsiranje teksta nije uspelo: {parse_err}. Fallback na originalni tekst.")
            return {
                "status": "success",
                "translated_segments": [
                    {"start": s["start"], "end": s["end"], "text": s["text"]}
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
