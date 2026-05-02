import os
import requests
import uuid
import base64
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint
from backend.worker.preprocessor import upload_to_minio

def synthesize_audio(vocals_path: str, translated_segments: list, progress_callback=None) -> dict:
    """
    Poziva RunPod Serverless Fish Speech (TTS) koristeći requests.
    """
    if not translated_segments:
        return {"status": "error", "message": "Nema segmenata za sintezu."}

    if not settings.MODAL_TTS_URL:
        print("[WARNING] MODAL_TTS_URL nije definisan. Preskačem sintezu.")
        return {"status": "error", "message": "MODAL_TTS_URL nedostaje."}

    # 1. Konverzija vocals_path u Base64
    if progress_callback:
        progress_callback(detail="Priprema referentnog audia za kloniranje glasa...")
    
    try:
        with open(vocals_path, "rb") as f:
            ref_b64 = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        return {"status": "error", "message": f"Greška pri čitanju referentnog audia: {e}"}

    # Sastavljanje celokupnog prevoda
    full_text = " ".join([s["text"] for s in translated_segments])
    
    payload = {
        "text": full_text,
        "reference_audio_base64": ref_b64,
        "reference_text": "Ovo je originalni glas iz videa." # Idealno bi bilo proslediti deo originalnog transkripta
    }

    print(f"[TTS V2] Pozivam Modal Fish Speech (Sinhrono) za {len(translated_segments)} segmenata...")
    
    try:
        output = call_modal_endpoint(
            url=settings.MODAL_TTS_URL, 
            payload=payload, 
            timeout_seconds=600,
            progress_callback=progress_callback
        )
        
        generated_b64 = output.get("audio_base64")
        if not generated_b64:
            return {"status": "error", "message": "Modal nije vratio audio_base64."}
            
        # Cuvanje u lokalni fajl
        local_filename = f"dubbed_{uuid.uuid4().hex[:8]}.wav"
        local_path = os.path.join(settings.TEMP_WORKSPACE, local_filename)
        
        audio_data = base64.b64decode(generated_b64)
        with open(local_path, "wb") as f:
            f.write(audio_data)
                    
        return {
            "status": "success",
            "dubbed_audio_path": local_path
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
