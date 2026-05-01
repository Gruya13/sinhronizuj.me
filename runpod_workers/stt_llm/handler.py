import os
import runpod
from huggingface_hub import snapshot_download

VOLUME_PATH = "/runpod-volume/models"
WHISPER_MODEL = "Systran/faster-whisper-large-v3"
QWEN_MODEL = "Qwen/Qwen2-VL-7B-Instruct-AWQ"

def ensure_model_exists(repo_id, local_dir):
    full_path = os.path.join(VOLUME_PATH, local_dir)
    if not os.path.exists(full_path):
        print(f"[{repo_id}] Model nije pronadjen na volume-u. Zapocinjem preuzimanje...")
        # Preuzimamo model sa HF
        snapshot_download(repo_id=repo_id, local_dir=full_path, max_workers=8)
        print(f"[{repo_id}] Preuzimanje zavrseno.")
    else:
        print(f"[{repo_id}] Model vec postoji na putanji {full_path}.")
    return full_path

# Provera pri startu kontejnera (Cold Start)
whisper_path = ensure_model_exists(WHISPER_MODEL, "faster-whisper-v3")
qwen_path = ensure_model_exists(QWEN_MODEL, "qwen2-vl-7b-awq")

def handler(job):
    job_input = job.get('input', {})
    
    # TODO: Inicijalizacija vLLM i FasterWhisper pipeline-a pomocu whisper_path i qwen_path
    
    return {"status": "success", "message": "Ovo je testni STT/LLM handler. Modeli su učitani!"}

runpod.serverless.start({"handler": handler})
