import os
import httpx
import asyncio
from typing import Dict, Any
from backend.core.config import settings
from backend.worker.preprocessor import upload_to_minio

async def transcribe_audio_async(audio_path: str) -> dict:
    """
    Poziva RunPod Serverless Whisper endpoint za transkripciju.
    """
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronađen: {audio_path}"}

    print(f"[TRANSCRIBER V2] Pripremam upload na MinIO za transkripciju...")
    
    # 1. Upload fajla na MinIO (RunPod-u treba URL)
    audio_url = upload_to_minio(audio_path, bucket_name="input-audio")
    
    # 2. Poziv RunPod-a
    if not settings.RUNPOD_WHISPER_ID:
        print("[WARNING] RUNPOD_WHISPER_ID nije definisan. Koristim mock transkripciju.")
        return {
            "status": "success",
            "language": "en",
            "full_text": "This is a mock transcription.",
            "segments": [{"start": 0.0, "end": 2.0, "text": "This is a mock transcription."}]
        }

    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_WHISPER_ID}/runsync"
    print(f"[DEBUG] Koristim API ključ (prvih 10 karaktera): {settings.RUNPOD_API_KEY[:10]}...")
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": {
            "audio": audio_url,
            "model": "large-v3",
            "task": "transcribe"
        }
    }

    print(f"[TRANSCRIBER V2] Pozivam RunPod Whisper (ID: {settings.RUNPOD_WHISPER_ID})...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=600)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "COMPLETED":
            output = result["output"]
            return {
                "status": "success",
                "language": output.get("language", "unknown"),
                "full_text": output.get("text", ""),
                "segments": output.get("segments", [])
            }
        else:
            raise Exception(f"RunPod Whisper greška: {result}")

def transcribe_audio(audio_path: str, model_size: str = "large-v3") -> dict:
    """Wrapper za sinhroni poziv."""
    return asyncio.run(transcribe_audio_async(audio_path))
