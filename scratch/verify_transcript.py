import os
import base64
import requests
import json

video_path = "/home/gruya/Projektri/sinhronizuj.me/temp_workspace/demucs_output/htdemucs/Why is an AI agent managing this store in San Francisco_ 🤔 #trendingshorts #ai #tech #future.publer.com/vocals.wav"

if not os.path.exists(video_path):
    print(f"Vocals fajl ne postoji na putanji: {video_path}")
    exit(1)

print(f"Učitavam vokal: {video_path}...")
with open(video_path, "rb") as f:
    audio_data = base64.b64encode(f.read()).decode("utf-8")

# Privremeni Modal dev endpoint
url = "https://gruyo89--sm-stt-only-sttworker-task-dev.modal.run"
headers = {"Content-Type": "application/json"}
payload = {
    "audio_base64": audio_data
}

print("Šaljem vokal na Modal dev STT worker...")
response = requests.post(url, headers=headers, json=payload)
if response.status_code == 200:
    res_data = response.json()
    if "error" in res_data:
        print("Greška iz workera:", res_data["error"])
    else:
        print("\n=== REZULTATI SA MODAL STT WORKER-A ===")
        print(f"Jezik: {res_data.get('language')}")
        segments = res_data.get("segments", [])
        for i, s in enumerate(segments):
            print(f"[{i}] ({s['start']:.2f}s - {s['end']:.2f}s): {s['text']}")
else:
    print(f"Greška {response.status_code}:", response.text)
