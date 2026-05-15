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

def extract_video_frames(video_path: str, num_frames: int = 10) -> List[str]:
    """
    Izvlači num_frames frejmova iz videa i vraća ih kao Base64 stringove.
    Povećano na 10 frejmova za bolji multimodalni kontekst.
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
    Poziva Modal Serverless Translator (Qwen2-VL) koristeći vLLM OpenAI Vision format.
    """
    if not segments:
        return {"status": "success", "translated_segments": []}

    if not settings.MODAL_TRANSLATOR_URL:
        print("[WARNING] MODAL_TRANSLATOR_URL nije definisan. Vraćam originalni tekst.")
        return {
            "status": "success", 
            "translated_segments": [
                {"start": s["start"], "end": s["end"], "text": s["text"]} 
                for s in segments
            ]
        }

    # Priprema tekstualnog ulaza
    transcript_text = ""
    for i, s in enumerate(segments):
        transcript_text += f"{i}|{s['text']}\n"
    
    # Ekstrakcija frejmova za vizuelni kontekst
    frames_b64 = []
    if video_path:
        if progress_callback:
            progress_callback(detail="Analiza vizuelnog konteksta (ekstrakcija frejmova)...")
        frames_b64 = extract_video_frames(video_path, num_frames=10)

    # Priprema multimodalnog content-a za Qwen2-VL (OpenAI format)
    prompt_text = (
        "Ti si vrhunski profesionalni prevodilac i lektor za srpski jezik. Tvoj zadatak je da prevedeš priloženi transkript sa engleskog na SRPSKI jezik (EKAVICA).\n\n"
        "PRAVILA ZA PREVOD:\n"
        "1. ZNAČENJE, A NE BUKVALNI PREVOD: Prevod mora zvučati 100% prirodno. Koristi srpske idiome i termine (npr. 'articles of incorporation' su 'osnivački akti').\n"
        "2. GRAMATIKA I PADEŽI: Strogo pazi na rod, broj i padeže! Sve rečenice moraju biti gramatički ispravne.\n"
        "3. TEHNIČKI TERMINI: Zadrži IT termine i imena u originalu (AI agent, Zoom, LinkedIn).\n"
        "4. KONTEKST CELINE: Transkript je jedna povezana priča. Razumi ceo kontekst pre nego što prevedeš pojedinačni red.\n"
        "5. POL GOVORNIKA: Prilagodi glagole u prošlom vremenu u zavisnosti od pola (vidi priložene slike).\n\n"
        "PRAVILA ZA FORMAT:\n"
        "1. Odgovor mora biti ISKLJUČIVO red po red, u formatu: ID|Prevedeni tekst\n"
        f"2. Tvoj odgovor mora sadržati TAČNO {len(segments)} redova (0 do {len(segments)-1}).\n"
        "3. Ne dodaj nikakav uvod ni zaključak.\n\n"
        f"TRANSKRIPT ZA PREVOD:\n{transcript_text}"
    )

    content = [{"type": "text", "text": prompt_text}]
    for f in frames_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{f}"}})

    payload = {
        "model": "qwen-vl",
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 4096
    }

    print(f"[TRANSLATOR VL] Šaljem {len(segments)} segmenata na Modal Translator: {settings.MODAL_TRANSLATOR_URL}")
    
    try:
        url = f"{settings.MODAL_TRANSLATOR_URL.rstrip('/')}/chat/completions"
        output = call_modal_endpoint(
            url=url, 
            payload=payload, 
            timeout_seconds=900,
            progress_callback=progress_callback
        )
        
        try:
            raw_output = output["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raw_output = str(output)

        print(f"[DEBUG] RAW TRANSLATION OUTPUT: {raw_output[:500]}...", flush=True)
        
        # Parsiranje tekstualnog izlaza
        parsed_lines = []
        for line in raw_output.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 1)
            if len(parts) == 2:
                text = parts[1].strip()
                if text:
                    parsed_lines.append(text)
                        
        final_segments = []
        for i, orig in enumerate(segments):
            t_text = parsed_lines[i] if i < len(parsed_lines) else ""
            final_segments.append({
                "start": orig["start"],
                "end": orig["end"],
                "text": t_text or orig["text"]
            })
            
        # POKRETANJE LEKTOR FAZE (KORAK 4.D)
        return lektor_segments(segments, final_segments, progress_callback=progress_callback)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

def lektor_segments(original_segments, translated_segments, progress_callback=None):
    """
    Druga faza: Qwen 2.5 32B (Lektor) lekturiše grubi prevod.
    """
    if not settings.MODAL_LEKTOR_URL:
        return {"status": "success", "translated_segments": translated_segments}
        
    print(f"[LEKTOR] Pokrećem Lektor fazu na {settings.MODAL_LEKTOR_URL}...")
    if progress_callback:
        progress_callback(detail="Lektura i poliranje prevoda (Qwen 32B)...")
        
    lektor_input = ""
    for i, seg in enumerate(translated_segments):
        lektor_input += f"{i}|ENG: {original_segments[i]['text']} | SRB: {seg['text']}\n"
        
    lektor_prompt = (
        "Ti si glavni lektor i korektor za srpski jezik (ekavica). Tvoj jedini zadatak je da pregledaš grubi prevod i ispraviš gramatiku, padeže, idiome i neprirodne izraze.\n\n"
        "PRAVILA ZA LEKTURU:\n"
        "1. Engleski tekst je dat kao kontekst. Tvoj izlaz mora biti SAMO korigovani SRPSKI tekst.\n"
        "2. Ispravi rogobatne prevode (npr. 'člankovi u korporaciju' -> 'osnivački akti', 'objavila zaposlenja' -> 'objavila oglase za posao').\n"
        "3. Zadrži isti broj linija. Svaka linija mora početi sa ID| (npr. 0|Korigovani prevod).\n"
        "4. Vrati SAMO korigovane redove.\n\n"
        f"TEKST ZA LEKTURU:\n{lektor_input}"
    )
    
    try:
        lektor_payload = {
            "model": "qwen-lektor", # Model name is set in lektor_worker.py
            "messages": [{"role": "user", "content": lektor_prompt}],
            "temperature": 0.2,
            "max_tokens": 4096
        }
        
        url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
        lektor_output = call_modal_endpoint(
            url=url,
            payload=lektor_payload,
            timeout_seconds=900,
            progress_callback=None
        )
        
        try:
            lektor_raw = lektor_output["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            lektor_raw = str(lektor_output)

        print(f"[DEBUG] LEKTOR OUTPUT: {lektor_raw[:500]}...", flush=True)
        
        parsed_lektor = []
        for line in lektor_raw.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 1)
            if len(parts) == 2:
                text = parts[1].strip()
                if text:
                    parsed_lektor.append(text)
                    
        if len(parsed_lektor) > 0:
            for i, seg in enumerate(translated_segments):
                seg["text"] = parsed_lektor[i] if i < len(parsed_lektor) else seg["text"]
                
    except Exception as lektor_err:
        print(f"[WARNING] Lektor faza nije uspela: {lektor_err}. Nastavljam sa grubim prevodom.")
        
    return {"status": "success", "translated_segments": translated_segments}
