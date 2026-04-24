import os
import uuid
import httpx
import asyncio
import base64
from pydub import AudioSegment
from typing import List, Dict, Any
from backend.core.config import settings
from backend.worker.preprocessor import upload_to_minio

def create_reference_audio(vocals_path: str) -> str:
    """Iseca kratak uzorak originalnog vokala (5s) za kloniranje glasa."""
    audio = AudioSegment.from_wav(vocals_path)
    start_ms = 1000
    end_ms = 6000
    ref_audio = audio[start_ms:end_ms] if len(audio) > end_ms else audio
    
    ref_path = os.path.join(settings.TEMP_WORKSPACE, f"ref_{uuid.uuid4().hex[:6]}.wav")
    ref_audio.export(ref_path, format="wav")
    return ref_path

async def synthesize_segment_runpod(text: str, ref_audio_url: str, segment_id: int) -> Dict[str, Any]:
    """Generiše jedan segment glasa preko RunPod-a."""
    if not settings.RUNPOD_TTS_ID:
        # Mock za testiranje
        return {"id": segment_id, "audio_b64": None, "status": "mock"}

    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_TTS_ID}/runsync"
    headers = {"Authorization": f"Bearer {settings.RUNPOD_API_KEY}"}
    
    payload = {
        "input": {
            "text": text,
            "reference_audio": ref_audio_url,
            "format": "wav"
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "COMPLETED":
            return {
                "id": segment_id,
                "audio_b64": result["output"].get("audio_b64"),
                "status": "success"
            }
        return {"id": segment_id, "status": "error"}

async def synthesize_audio_async(vocals_path: str, translated_segments: list) -> dict:
    """Glavna asinhrona funkcija za hibridnu TTS sintezu."""
    print(f"[TTS V2] Započinjem hibridnu sintezu ({len(translated_segments)} segmenata)...")
    
    # 1. Priprema i upload reference
    ref_path = create_reference_audio(vocals_path)
    ref_url = upload_to_minio(ref_path, bucket_name="references")
    
    # 2. Paralelna sinteza svih segmenata
    tasks = []
    for i, seg in enumerate(translated_segments):
        if len(seg["text"].strip()) > 1:
            tasks.append(synthesize_segment_runpod(seg["text"], ref_url, i))
    
    results = await asyncio.gather(*tasks)
    
    # 3. Slaganje u finalni audio (stitching)
    # Određujemo trajanje na osnovu poslednjeg segmenta
    max_end = max([s["end"] for s in translated_segments])
    final_audio = AudioSegment.silent(duration=int(max_end * 1000) + 2000)
    
    output_dir = os.path.join(settings.TEMP_WORKSPACE, "generated_speech")
    os.makedirs(output_dir, exist_ok=True)

    for res in results:
        if res["status"] == "success" and res["audio_b64"]:
            seg_idx = res["id"]
            orig_seg = translated_segments[seg_idx]
            
            # Dekodiramo audio iz b64
            audio_content = base64.b64decode(res["audio_b64"])
            temp_path = os.path.join(output_dir, f"seg_{seg_idx}.wav")
            with open(temp_path, "wb") as f:
                f.write(audio_content)
            
            seg_audio = AudioSegment.from_wav(temp_path)
            
            # Audio-fit (ubrzavanje ako je predugačko)
            target_ms = int((orig_seg["end"] - orig_seg["start"]) * 1000)
            if len(seg_audio) > target_ms * 1.1:
                speed = len(seg_audio) / target_ms
                seg_audio = seg_audio.speedup(playback_speed=min(speed, 1.5))
            
            final_audio = final_audio.overlay(seg_audio, position=int(orig_seg["start"] * 1000))
            os.remove(temp_path)

    final_output_path = os.path.join(settings.TEMP_WORKSPACE, f"runpod_sinhronizuj_{uuid.uuid4().hex[:6]}.wav")
    final_audio.export(final_output_path, format="wav")
    
    # Čišćenje reference
    if os.path.exists(ref_path): os.remove(ref_path)
    
    return {
        "status": "success",
        "dubbed_audio_path": final_output_path
    }

def synthesize_audio(vocals_path: str, translated_segments: list, original_segments: list = None, progress_callback=None) -> dict:
    """Wrapper za sinhroni poziv."""
    return asyncio.run(synthesize_audio_async(vocals_path, translated_segments))
