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
        "Ti si vrhunski profesionalni prevodilac i lektor za srpski jezik. Tvoj zadatak je da prevedeš priloženi transkript sa engleskog na SRPSKI jezik (EKAVICA).\n\n"
        "PRAVILA ZA PREVOD:\n"
        "1. ZNAČENJE, A NE BUKVALNI PREVOD: Prevod mora zvučati 100% prirodno izvornom govorniku srpskog jezika. Nikada ne prevodi idiome i pravne izraze bukvalno (npr. 'articles of incorporation' su 'osnivački akti' ili 'dokumentacija za firmu', a 'job listings' su 'oglasi za posao'). Prevedi smisao, a ne reč po reč.\n"
        "2. GRAMATIKA I PADEŽI: Strogo pazi na rod, broj i padeže! Na primer, reč 'kompanija' je ženskog roda ('OVA kompanija', a ne 'ovaj kompanija'). 'AI agent' je muškog roda ('AI agentu', 'njemu'). Sve rečenice moraju biti gramatički ispravne.\n"
        "3. TEHNIČKI TERMINI: Zadrži IT termine i imena u originalu (AI agent, Zoom, LinkedIn, Claude, Andon Labs).\n"
        "4. KONTEKST CELINE: Transkript je jedna povezana priča. Razumi ceo kontekst pre nego što prevedeš pojedinačni red.\n"
        "5. POL GOVORNIKA I LIKOVA: Prilagodi glagole u prošlom vremenu u zavisnosti od pola onoga ko govori ili o kome se govori (prema slikama i kontekstu).\n\n"
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
        
        # Parsiranje tekstualnog izlaza (Ignorišemo ID koji LLM vrati, uzimamo redom)
        try:
            parsed_lines = []
            for line in raw_output.split('\n'):
                line = line.strip()
                if not line or '|' not in line:
                    continue
                # Razdvajamo po prvom '|'
                parts = line.split('|', 1)
                if len(parts) == 2:
                    text = parts[1].strip()
                    if text:
                        parsed_lines.append(text)
                        
            final_segments = []
            for i, orig in enumerate(segments):
                # Uzimamo prevedene linije redom, bez obzira da li je LLM krenuo od 0 ili 1
                t_text = parsed_lines[i] if i < len(parsed_lines) else ""
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

def lektor_segments(original_segments, translated_segments, progress_callback=None):
    """
    Druga faza: Qwen 35B lekturiše grubi prevod iz prve faze.
    """
    if not hasattr(settings, 'MODAL_LEKTOR_URL') or not settings.MODAL_LEKTOR_URL:
        return translated_segments
        
    print(f"[TRANSLATOR VL] Pokrećem Lektor fazu na {settings.MODAL_LEKTOR_URL}...")
    if progress_callback:
        progress_callback(detail="Lektura prevoda (Qwen 35B)...")
        
    lektor_input = ""
    for i, seg in enumerate(translated_segments):
        lektor_input += f"{i}|ENG: {original_segments[i]['text']} | SRB: {seg['text']}\n"
        
    lektor_prompt = (
        "Ti si glavni lektor i korektor za srpski jezik (ekavica). Tvoj jedini zadatak je da pregledaš grubi prevod i ispraviš gramatiku, padeže, idiome i neprirodne izraze.\n\n"
        "PRAVILA ZA LEKTURU:\n"
        "1. Engleski tekst je dat samo kao kontekst. Tvoj izlaz mora biti SAMO korigovani SRPSKI tekst.\n"
        "2. Ispravi rogobatne prevode (npr. 'člankovi u korporaciju' prepravi u 'osnivački akti/dokumenta', a 'objavila zaposlenja' u 'objavila oglase za posao').\n"
        "3. Zadrži isti broj linija. Svaka linija mora početi sa ID| (npr. 0|Korigovani prevod).\n"
        "4. ZABRANJENO je objašnjavanje, vrati samo čiste korigovane redove.\n\n"
        f"TEKST ZA LEKTURU:\n{lektor_input}"
    )
    
    try:
        lektor_payload = {
            "task": "lektor",
            "prompt": lektor_prompt
        }
        from backend.worker.utils import call_modal_endpoint
        lektor_output = call_modal_endpoint(
            url=settings.MODAL_LEKTOR_URL,
            payload=lektor_payload,
            timeout_seconds=300,
            progress_callback=None
        )
        
        lektor_raw = lektor_output.get("translation", "")
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
        
    return translated_segments
