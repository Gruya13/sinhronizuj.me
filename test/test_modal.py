import os
import json
import time
import base64
import requests
import wave
import argparse
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

parser = argparse.ArgumentParser()
parser.add_argument("--only", choices=["stt", "llm", "tts"])
parser.add_argument("--endpoint", help="Override TTS endpoint")
args = parser.parse_args()

MODAL_STT_LLM_URL = os.getenv("MODAL_STT_LLM_URL")
MODAL_TTS_URL = args.endpoint if args.endpoint else os.getenv("MODAL_TTS_URL")

HEADERS = {"Content-Type": "application/json"}

def test_whisper():
    print("\n--- TEST: Whisper (STT) ---")
    audio_data = b"FAKE_AUDIO_DATA" # U pravoj implementaciji ovde ide pravi audio
    # Za potrebe testa, šaljemo sample request
    payload = {"audio_base64": base64.b64encode(audio_data).decode('utf-8')}
    try:
        r = requests.post(MODAL_STT_LLM_URL, json=payload, timeout=60)
        print(f"Rezultat: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
        return "segments" in r.json()
    except Exception as e:
        print(f"Greška: {e}")
        return False

def test_translator():
    print("\n--- TEST: Qwen (LLM Prevod) ---")
    payload = {"text": "Sadržaj: [0.0|1.0|Zdravo svete!]"}
    try:
        r = requests.post(MODAL_STT_LLM_URL, json=payload, timeout=60)
        print(f"Rezultat: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
        return "translation" in r.json()
    except Exception as e:
        print(f"Greška: {e}")
        return False

def test_tts():
    print("\n--- TEST: Fish Speech (TTS) ---")
    # Generišemo validan mali WAV fajl
    buffer = BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b'\x00' * 1000)
    
    ref_audio = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    payload = {
        "text": "Ovo je test generisanja govora.",
        "reference_audio_base64": ref_audio,
        "reference_text": "Ovo je referenca."
    }
    
    print("Slanje zahteva na Modal (čeka se odgovor)...")
    try:
        r = requests.post(MODAL_TTS_URL, json=payload, timeout=300)
        if r.status_code != 200:
            print(f"Greška HTTP {r.status_code}: {r.text}")
            return False
            
        output = r.json()
        if "error" in output:
            print(f"Greška: {output}")
            return False
            
        if "audio_base64" in output:
            print(f"Uspešno generisan audio. Dužina: {len(output['audio_base64'])}")
            return True
    except Exception as e:
        print(f"Greška: {e}")
        return False
    return False

if __name__ == "__main__":
    if args.only == "stt":
        test_whisper()
    elif args.only == "llm":
        test_translator()
    elif args.only == "tts":
        test_tts()
    else:
        test_whisper()
        test_translator()
        test_tts()
