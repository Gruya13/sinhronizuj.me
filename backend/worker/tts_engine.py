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

    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_TTS_ID}/runsync"
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }

    # Pripremamo payload za batch sintezu (Fish Speech podržava listu rečenica)
    payload = {
        "input": {
            "text_segments": [s["text"] for s in translated_segments],
            "reference_audio": ref_url,
            "language": "sr",
            "format": "wav"
        }
    }

    print(f"[TTS V2] Pozivam RunPod Fish Speech za {len(translated_segments)} segmenata...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=600)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "COMPLETED":
            # Fish Speech vraća URL ka spojenom audio fajlu ili listu URL-ova
            audio_url = result["output"]["audio_url"]
            
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
        else:
            raise Exception(f"RunPod TTS greška: {result}")
            
    except Exception as e:
        return {"status": "error", "message": str(e)}
