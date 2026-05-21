import requests
import base64
import json

audio_path = "backend/assets/serbian_female.wav"
stt_url = "https://gruyo89--sm-stt-only-sttworker-task.modal.run"

with open(audio_path, "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode('utf-8')

payload = {"task": "transcribe", "audio_base64": audio_b64}
print("Sending request to Modal STT...")
resp = requests.post(stt_url, json=payload, timeout=60)
print("Response status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print("Full result:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("Transcribed text:")
    print(data.get("text", ""))
else:
    print("Error:", resp.text)
