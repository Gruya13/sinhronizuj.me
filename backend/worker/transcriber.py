import os
import base64
import re
from backend.core.config import settings

def segment_by_sentences(segments):
    if not segments:
        return []
        
    # 1. Izvlačimo sve reči u jedan linearan niz radi lakše analize pauza
    all_words = []
    for s in segments:
        if "words" in s and s["words"]:
            all_words.extend(s["words"])
        else:
            # Fallback ako nema word_timestamps: podeli tekst segmenta na reči (manje precizno)
            words = s["text"].split()
            if not words: continue
            dur = (s["end"] - s["start"]) / len(words)
            for i, w in enumerate(words):
                all_words.append({
                    "start": s["start"] + i*dur,
                    "end": s["start"] + (i+1)*dur,
                    "word": w
                })

    if not all_words:
        return []

    # 2. Grupišemo reči u rečenice na osnovu interpunkcije I pauza
    sentence_segments = []
    curr_words = []
    
    for i in range(len(all_words)):
        w = all_words[i]
        curr_words.append(w)
        
        word_text = w["word"].strip()
        
        # Provera interpunkcije na samoj reči
        has_punct = any(word_text.endswith(p) for p in ['.', '!', '?', '...'])
        
        # Provera pauze do sledeće reči
        has_pause = False
        if i < len(all_words) - 1:
            pause_duration = all_words[i+1]["start"] - w["end"]
            if pause_duration > 0.45: # Pauza duža od 0.45s je obično kraj rečenice
                has_pause = True
        
        # Opušteniji limit: režemo tek na 40 reči ako baš nema ni tačke ni pauze.
        # Ako ima zarez a prešli smo 20 reči, režemo tu da sprečimo gigantske segmente.
        is_too_long = len(curr_words) >= 40
        has_comma_and_long = word_text.endswith(',') and len(curr_words) >= 20
        
        if has_punct or has_pause or is_too_long or has_comma_and_long:
            text = " ".join([cw["word"].strip() for cw in curr_words])
            sentence_segments.append({
                "start": round(curr_words[0]["start"], 2),
                "end": round(curr_words[-1]["end"], 2),
                "text": text
            })
            curr_words = []
            
    # Dodajemo preostale reči
    if curr_words:
        text = " ".join([cw["word"].strip() for cw in curr_words])
        sentence_segments.append({
            "start": round(curr_words[0]["start"], 2),
            "end": round(curr_words[-1]["end"], 2),
            "text": text
        })
        
    return sentence_segments

def transcribe_audio(audio_path: str, progress_callback=None) -> dict:
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronađen: {audio_path}"}

    try:
        with open(audio_path, "rb") as audio_file:
            audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')
    except Exception as e:
        return {"status": "error", "message": f"Greška pri čitanju audia: {e}"}

    from backend.worker.utils import call_modal_endpoint
    payload = {"task": "transcribe", "audio_base64": audio_base64}

    try:
        output = call_modal_endpoint(
            url=settings.MODAL_STT_URL, 
            payload=payload, 
            timeout_seconds=900,
            progress_callback=progress_callback
        )
        
        raw_segments = output.get("segments", [])
        sentence_segments = segment_by_sentences(raw_segments)
        
        return {
            "status": "success",
            "language": output.get("language", "unknown"),
            "full_text": " ".join([s["text"] for s in sentence_segments]),
            "segments": sentence_segments
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
