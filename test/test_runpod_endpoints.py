import os
import json
import time
import base64
import requests
import wave
from io import BytesIO
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

API_KEY = os.getenv("RUNPOD_API_KEY")
STT_LLM_ID = os.getenv("RUNPOD_WHISPER_ID")
TTS_ID = os.getenv("RUNPOD_TTS_ID")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def generate_sample_audio_base64():
    """Generiše prazan (tihi) 1-sekundni WAV fajl u memoriji i vraća base64 string."""
    buffer = BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        # 1 sekunda tišine
        wav.writeframes(b'\x00' * 16000 * 2)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def generate_sample_image_base64():
    """Generiše 1x1 piksel prazan PNG."""
    # Hardkodovan minimalan 1x1 providni PNG
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    return base64.b64encode(png_data).decode('utf-8')

def wait_for_job(endpoint_id, job_id):
    """Pita RunPod za status dok se posao ne završi."""
    url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    print(f"[*] Cekam na zavrsetak posla {job_id}...")
    
    start_time = time.time()
    while True:
        if time.time() - start_time > 900: # 15 min timeout (Cold start)
            return {"error": "Timeout"}
            
        try:
            res = requests.get(url, headers=HEADERS)
            data = res.json()
            status = data.get("status")
            print(f"    Status: {status}")
            
            if status == "COMPLETED":
                return data.get("output", {})
            elif status in ["FAILED", "CANCELLED"]:
                return {"error": f"Posao je {status}", "details": data}
                
        except Exception as e:
            print(f"Greska pri polling-u: {e}")
            
        time.sleep(3)

def test_whisper():
    print("\n--- TEST: Whisper (STT) ---")
    url = f"https://api.runpod.ai/v2/{STT_LLM_ID}/run"
    audio_b64 = generate_sample_audio_base64()
    
    payload = {
        "input": {
            "task": "transcribe",
            "audio_base64": audio_b64
        }
    }
    
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code != 200:
        print(f"GREŠKA pri slanju zahteva: {res.text}")
        return False
        
    job_id = res.json().get("id")
    output = wait_for_job(STT_LLM_ID, job_id)
    print("Rezultat:", json.dumps(output, indent=2, ensure_ascii=False))
    return "error" not in output

def test_translator():
    print("\n--- TEST: Qwen (LLM Prevod) ---")
    url = f"https://api.runpod.ai/v2/{STT_LLM_ID}/run"
    img_b64 = generate_sample_image_base64()
    
    payload = {
        "input": {
            "task": "translate",
            "segments": [
                {"id": 0, "start": 0.0, "end": 1.0, "text": "Hello, world!"}
            ],
            "visual_context_url": [f"data:image/png;base64,{img_b64}"]
        }
    }
    
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code != 200:
        print(f"GREŠKA pri slanju zahteva: {res.text}")
        return False
        
    job_id = res.json().get("id")
    output = wait_for_job(STT_LLM_ID, job_id)
    print("Rezultat:", json.dumps(output, indent=2, ensure_ascii=False))
    return "error" not in output

def test_tts():
    print("\n--- TEST: Fish Speech (TTS) ---")
    url = f"https://api.runpod.ai/v2/{TTS_ID}/run"
    audio_b64 = generate_sample_audio_base64()
    
    payload = {
        "input": {
            "text": "Zdravo, ovo je test sistem za sinhronizaciju.",
            "reference_audio": audio_b64,
            "speaker_name": "Speaker_0",
            "language": "sr"
        }
    }
    
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code != 200:
        print(f"GREŠKA pri slanju zahteva: {res.text}")
        return False
        
    job_id = res.json().get("id")
    output = wait_for_job(TTS_ID, job_id)
    
    if "error" in output:
        print("Greška:", output)
        return False
        
    if "audio_base64" in output:
        # Prikazujemo samo pocetak base64 stringa da ne spamujemo terminal
        print(f"Uspešno generisan audio. Dužina base64: {len(output['audio_base64'])}")
        return True
    return False

if __name__ == "__main__":
    if not API_KEY:
        print("RUNPOD_API_KEY nije definisan!")
        exit(1)
        
    print(f"Testiram STT_LLM Endpoint: {STT_LLM_ID}")
    print(f"Testiram TTS Endpoint: {TTS_ID}")
    
    # Napomena: Ovi testovi ce okinuti 'cold start' ako modeli nisu na volume-u
    
    res1 = test_whisper()
    res2 = test_translator()
    res3 = test_tts()
    
    print("\n=== REZIME TESTOVA ===")
    print(f"Whisper: {'✅ PASS' if res1 else '❌ FAIL'}")
    print(f"Qwen:    {'✅ PASS' if res2 else '❌ FAIL'}")
    print(f"TTS:     {'✅ PASS' if res3 else '❌ FAIL'}")
