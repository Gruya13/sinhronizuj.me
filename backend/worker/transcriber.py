import os
import base64
from backend.core.config import settings

def transcribe_audio(audio_path: str, progress_callback=None) -> dict:
    """
    Poziva Modal STT/LLM webhook za transkripciju.
    Šalje audio u base64 formatu.
    """
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronađen: {audio_path}"}

    # 1. Konverzija u Base64 (umesto MinIO uploada)
    if progress_callback:
        progress_callback(detail="Priprema audio fajla za Modal...")
        
    try:
        with open(audio_path, "rb") as audio_file:
            audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')
    except Exception as e:
        return {"status": "error", "message": f"Greška pri čitanju audia: {e}"}

    # 2. Poziv Modal-a
    if not settings.MODAL_STT_LLM_URL:
        print("[WARNING] MODAL_STT_LLM_URL nije definisan. Koristim mock transkripciju.")
        return {
            "status": "success",
            "language": "en",
            "full_text": "This is a mock transcription.",
            "segments": [{"start": 0.0, "end": 2.0, "text": "This is a mock transcription."}]
        }

    from backend.worker.utils import call_modal_endpoint
    
    payload = {
        "task": "transcribe",
        "audio_base64": audio_base64
    }

    print(f"[TRANSCRIBER V2] Pozivam Modal STT...")
    
    try:
        output = call_modal_endpoint(
            url=settings.MODAL_STT_LLM_URL, 
            payload=payload, 
            timeout_seconds=300,
            progress_callback=progress_callback
        )
        
        return {
            "status": "success",
            "language": output.get("language", "unknown"),
            "full_text": " ".join([s["text"] for s in output.get("segments", [])]),
            "segments": output.get("segments", [])
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
