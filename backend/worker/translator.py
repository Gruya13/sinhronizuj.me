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
        "Ti si ekspert za prevođenje video titlova. Tvoj zadatak je da prevedeš transkript na SRPSKI jezik (EKAVICA). \n"
        "PRAVILA:\n"
        "1. MORAŠ zadržati TOON format: [start|end|prevedeni tekst].\n"
        "2. Prevod mora biti DOSLOVAN (rečenica po rečenica), ne smeš prepričavati niti sažimati tekst.\n"
        "3. Koristi priložene slike da odrediš pol govornika (npr. 'Ja sam video' vs 'Ja sam videla').\n"
        "4. Celokupan izlaz mora biti samo TOON lista, bez ikakvog dodatnog teksta.\n"
        "5. Reč 'preoccupied' prevedi kao 'zaokupljeni' ili 'opsednuti'.\n\n"
        "PRIMER FORMATA:\n"
        "ULAZ: [1.20|3.50|I am working on AI agent named Luna]\n"
        "IZLAZ: [1.20|3.50|Radim na AI agentu po imenu Luna]\n\n"
        f"TRANSKRIPT ZA PREVOD:\n{' '.join(toon_input)}"
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
        # Parsiranje TOON formata nazad u JSON objekte
        import re
        # Pokušavamo da nađemo sve što liči na [vreme|vreme|tekst]
        matches = re.findall(r'\[?\d+\.?\d*\|\d+\.?\d*\|[^\]\n]+\]?', translated_toon_text)
        
        final_segments = []
        for match in matches:
            try:
                # Čistimo zagrade ako postoje
                clean_match = match.strip("[]")
                parts = clean_match.split("|")
                if len(parts) >= 3:
                    final_segments.append({
                        "start": float(parts[0]),
                        "end": float(parts[1]),
                        "text": "|".join(parts[2:]).strip()
                    })
            except:
                continue
                
        # Ako regex ne izvuče dovoljno segmenata, pokušavamo fallback po linijama
        if len(final_segments) < len(segments) * 0.5:
            print(f"[WARNING] TOON parsiranje dalo samo {len(final_segments)} segmenata od očekivanih {len(segments)}. Fallback na inteligentnu podelu.")
            
            # Ako je vratio bar nešto teksta, probajmo da ga razbijemo po rečenicama
            raw_sentences = re.split(r'(?<=[.!?])\s+', translated_toon_text.replace("[", "").replace("]", ""))
            raw_sentences = [s.strip() for s in raw_sentences if s.strip() and "|" not in s]
            
            if raw_sentences and len(raw_sentences) >= len(segments) * 0.5:
                # Imamo rečenice! Mapirajmo ih na originalne segmente
                final_segments = []
                for i, orig in enumerate(segments):
                    text = raw_sentences[i] if i < len(raw_sentences) else ""
                    final_segments.append({
                        "start": orig["start"],
                        "end": orig["end"],
                        "text": text
                    })
            else:
                # Baš ništa nije uspelo, ostaje nam samo da vratimo originalne tajminge sa celim tekstom u prvom
                print("[ERROR] Potpuni neuspeh parsiranja prevoda.")
                return {
                    "status": "success",
                    "translated_segments": [
                        {"start": s["start"], "end": s["end"], "text": translated_toon_text if i == 0 else ""}
                        for i, s in enumerate(segments)
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
