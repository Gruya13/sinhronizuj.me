import os
import runpod
from huggingface_hub import snapshot_download

VOLUME_PATH = "/runpod-volume/models"
FISH_MODEL = "fishaudio/fish-speech-1.5"

def ensure_model_exists(repo_id, local_dir):
    full_path = os.path.join(VOLUME_PATH, local_dir)
    if not os.path.exists(full_path):
        print(f"[{repo_id}] Model nije pronadjen na volume-u. Zapocinjem preuzimanje...")
        snapshot_download(repo_id=repo_id, local_dir=full_path, max_workers=8)
        print(f"[{repo_id}] Preuzimanje zavrseno.")
    else:
        print(f"[{repo_id}] Model vec postoji na putanji {full_path}.")
    return full_path

# Provera pri startu kontejnera
fish_path = ensure_model_exists(FISH_MODEL, "fish-speech-1.5")

def handler(job):
    job_input = job.get('input', {})
    
    # TODO: Inicijalizacija Fish Speech modela pomocu fish_path
    
    return {"status": "success", "message": "Ovo je testni TTS handler. Model je učitan!"}

runpod.serverless.start({"handler": handler})
