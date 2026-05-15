import os
import base64
import re
from backend.core.config import settings

def segment_by_sentences(segments):
    if not segments:
        return []
        
    # 1. Prvo splitujemo segmente koji sadrže interpunkciju
    flat_pieces = []
    for s in segments:
        text = s["text"].strip()
        if not text:
            continue
            
        parts = re.split(r'(?<=[.!?])\s+', text)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) == 1:
            flat_pieces.append(s)
        else:
            duration = s["end"] - s["start"]
            total_chars = sum(len(p) for p in parts)
            curr_start = s["start"]
            for p in parts:
                p_dur = (len(p) / total_chars) * duration if total_chars > 0 else 0
                flat_pieces.append({
                    "start": curr_start,
                    "end": curr_start + p_dur,
                    "text": p
                })
                curr_start += p_dur
                
    # 2. Spajamo delove u rečenice, ali dodajemo limit na dužinu (max 15 reči ili 8 sekundi)
    sentence_segments = []
    curr_start = None
    curr_end = None
    curr_text = ""
    
    for p in flat_pieces:
        if curr_start is None:
            curr_start = p["start"]
            
        curr_text += (" " + p["text"] if curr_text else p["text"])
        curr_end = p["end"]
        
        word_count = len(curr_text.split())
        duration = curr_end - curr_start
        
        # Uslovi za kraj segmenta: 
        # a) Ima tačku/upitnik/uzvičnik na kraju
        # b) Predugačko je (više od 15 reči)
        # c) Predugo traje (više od 8 sekundi)
        has_punctuation = any(curr_text.strip().endswith(punct) for punct in ['.', '!', '?'])
        is_too_long = word_count >= 15
        is_too_timed = duration >= 8.0
        
        if has_punctuation or is_too_long or is_too_timed:
            sentence_segments.append({
                "start": round(curr_start, 2),
                "end": round(curr_end, 2),
                "text": curr_text.strip()
            })
            curr_start = None
            curr_text = ""
            
    # Dodajemo preostali tekst
    if curr_text:
        sentence_segments.append({
            "start": round(curr_start, 2),
            "end": round(curr_end, 2),
            "text": curr_text.strip()
        })
        
    return sentence_segments

def transcribe_audio(audio_path: str, progress_callback=None) -> dict:
    """
    Poziva Modal STT/LLM webhook za transkripciju.
    Šalje audio u base64 formatu.
    """
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronađen: {audio_path}"}

    try:
        with open(audio_path, "rb") as audio_file:
            audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')
    except Exception as e:
        return {"status": "error", "message": f"Greška pri čitanju audia: {e}"}

    from backend.worker.utils import call_modal_endpoint
    
    payload = {
        "task": "transcribe",
        "audio_base64": audio_base64
    }

    try:
        output = call_modal_endpoint(
            url=settings.MODAL_STT_URL, 
            payload=payload, 
            timeout_seconds=900,
            progress_callback=progress_callback
        )
        
        raw_segments = output.get("segments", [])
        # Koristimo unapređenu funkciju za pametniju segmentaciju
        sentence_segments = segment_by_sentences(raw_segments)
        
        return {
            "status": "success",
            "language": output.get("language", "unknown"),
            "full_text": " ".join([s["text"] for s in sentence_segments]),
            "segments": sentence_segments
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
