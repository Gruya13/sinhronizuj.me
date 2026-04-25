import os
import requests
from typing import Dict, Any
from backend.core.config import settings
from backend.worker.preprocessor import upload_to_minio

def transcribe_audio(audio_path: str, progress_callback=None) -> dict:
    """
    Poziva RunPod Serverless Whisper endpoint za transkripciju koristeći requests (stabilnije od httpx).
    """
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronađen: {audio_path}"}

    print(f"[TRANSCRIBER V2] Pripremam upload na MinIO za transkripciju...")
    
    # 1. Upload fajla na MinIO (RunPod-u treba URL)
    audio_url = upload_to_minio(audio_path, bucket_name="input-audio")
    
    if not audio_url:
        return {"status": "error", "message": "MinIO upload nije uspeo."}

    # 2. Poziv RunPod-a
    if not settings.RUNPOD_WHISPER_ID:
        print("[WARNING] RUNPOD_WHISPER_ID nije definisan. Koristim mock transkripciju.")
        return {
            "status": "success",
            "language": "en",
            "full_text": "This is a mock transcription.",
            "segments": [{"start": 0.0, "end": 2.0, "text": "This is a mock transcription."}]
        }

    from backend.worker.utils import wait_for_runpod_result
    
    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_WHISPER_ID}/run"
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": {
            "audio": audio_url,
            "model": "large-v3"
        }
    }

    print(f"[TRANSCRIBER V2] Pozivam RunPod Whisper (Asinhrono, ID: {settings.RUNPOD_WHISPER_ID})...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["id"]
        
        # Čekamo rezultat (polling)
        output = wait_for_runpod_result(job_id, settings.RUNPOD_WHISPER_ID, progress_callback=progress_callback)
        
        return {
            "status": "success",
            "language": output.get("language", "unknown"),
            "full_text": output.get("text", ""),
            "segments": output.get("segments", [])
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
