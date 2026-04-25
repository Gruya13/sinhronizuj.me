import os
import requests
import uuid
from backend.core.config import settings
from backend.worker.preprocessor import upload_to_minio

def synthesize_audio(vocals_path: str, translated_segments: list) -> dict:
    """
    Poziva RunPod Serverless Fish Speech (TTS) koristeći requests.
    """
    if not translated_segments:
        return {"status": "error", "message": "Nema segmenata za sintezu."}

    # 1. Upload reference (vocals) na MinIO
    ref_url = upload_to_minio(vocals_path, bucket_name="references")
    if not ref_url:
        return {"status": "error", "message": "MinIO upload reference nije uspeo."}

    if not settings.RUNPOD_TTS_ID:
        print("[WARNING] RUNPOD_TTS_ID nije definisan. Preskačem sintezu.")
        return {"status": "error", "message": "RUNPOD_TTS_ID nedostaje."}

    from backend.worker.utils import wait_for_runpod_result
    
    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_TTS_ID}/run"
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": {
            "text_segments": [s["text"] for s in translated_segments],
            "reference_audio": ref_url,
            "language": "sr",
            "format": "wav"
        }
    }

    print(f"[TTS V2] Pozivam RunPod Fish Speech (Asinhrono) za {len(translated_segments)} segmenata...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["id"]
        
        # Čekamo rezultat (polling)
        output = wait_for_runpod_result(job_id, settings.RUNPOD_TTS_ID)
        
        audio_url = output["audio_url"]
        
        # Preuzimamo generisani audio lokalno za Muxing fazu
        local_filename = f"dubbed_{uuid.uuid4().hex[:8]}.wav"
        local_path = os.path.join(settings.TEMP_WORKSPACE, local_filename)
        
        with requests.get(audio_url, stream=True) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
        return {
            "status": "success",
            "dubbed_audio_path": local_path
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
