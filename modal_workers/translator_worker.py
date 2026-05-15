import modal
import os

# Definicija slike sa svim potrebnim zavisnostima
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "git-lfs")
    .pip_install(
        "vllm==0.6.3.post1",
        "transformers==4.45.2",
        "accelerate==1.1.1",
        "sentencepiece",
        "requests",
        "qwen-vl-utils"
    )
)

app = modal.App("sm-translator")

# Volumen za čuvanje modela
model_volume = modal.Volume.from_name("sinhronizuj-models", create_if_missing=True)

@app.function(
    image=vllm_image,
    volumes={"/models": model_volume},
    gpu="A100",
    timeout=1800,
    scaledown_window=300,
    env={
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
    }
)
@modal.web_server(port=8000, startup_timeout=600)
def serve():
    import subprocess
    import time
    
    model_path = "/models/qwen-vl-7b-awq"
    
    print(f"Pokretanje optimizovanog vLLM 0.6.3 servera za Translator (Qwen2-VL)")
    
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_path,
        "--served-model-name", "qwen-vl",
        "--quantization", "awq_marlin",  # Optimizovano prema instrukcijama
        "--trust-remote_code",
        "--gpu-memory-utilization", "0.7",
        "--max-model-len", "12288",       # Zadržavamo stabilan context
        "--limit-mm-per-prompt", "image=3", # Zadržavamo stabilan broj slika
        "--enforce-eager",
        "--disable-frontend-multiprocessing", # Rešava problem duplog pokretanja
        "--disable-log-stats",                # Utišava periodične metrike (0.0 tokens/s)
        "--port", "8000"
    ]
    
    subprocess.run(cmd, check=True)

@app.function(
    image=vllm_image,
    volumes={"/models": model_volume},
    timeout=3600
)
def download_vlm():
    from huggingface_hub import snapshot_download
    
    model_id = "Qwen/Qwen2-VL-7B-Instruct-AWQ"
    model_path = "/models/qwen-vl-7b-awq"
    
    if not os.path.exists(model_path):
        print(f"Preuzimanje modela {model_id}...")
        snapshot_download(
            model_id,
            local_dir=model_path,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot"]
        )
        model_volume.commit()
    else:
        print("Model već postoji na volumenu.")
