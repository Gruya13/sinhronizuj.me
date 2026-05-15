import modal
import os

VOLUME_PATH = "/models"
models_volume = modal.NetworkFileSystem.from_name("sinhronizuj-models", create_if_missing=True)

MODEL_NAME = "Qwen/Qwen2-VL-7B-Instruct-AWQ"

def download_vlm():
    from huggingface_hub import snapshot_download
    import os
    stt_dir = f"{VOLUME_PATH}/qwen-vl-7b-awq"
    if not os.path.exists(stt_dir):
        print(f"Preuzimanje VLM modela: {MODEL_NAME}")
        snapshot_download(MODEL_NAME, local_dir=stt_dir)

image_vlm = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6", "python3.11", "python3-pip", "ninja-build")
    .run_commands("ln -s /usr/bin/python3.11 /usr/local/bin/python")
    # Prelazak na provereno stabilnu kombinaciju verzija za Qwen2-VL
    .pip_install("torch==2.4.0", "torchvision", "xformers==0.0.27.post2", index_url="https://download.pytorch.org/whl/cu124")
    .pip_install(
        "vllm==0.6.3.post1",
        "transformers==4.45.2",
        "opencv-python-headless",
        "huggingface-hub",
        "fastapi",
        "uvicorn"
    )
    .run_function(download_vlm, network_file_systems={VOLUME_PATH: models_volume})
)

app = modal.App("sm-translator")

@app.function(
    gpu="A100", 
    network_file_systems={VOLUME_PATH: models_volume}, 
    image=image_vlm, 
    timeout=3600,
    scaledown_window=300,
    env={
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn", 
        "VLLM_USE_V1": "0",
        "VLLM_ATTENTION_BACKEND": "XFORMERS"
    }
)
@modal.web_server(port=8000, startup_timeout=600)
def serve():
    import subprocess
    
    stt_path = f"{VOLUME_PATH}/qwen-vl-7b-awq"
    
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", stt_path,
        "--served-model-name", "qwen-vl",
        "--quantization", "awq", # Vraćamo na awq jer 0.6.3 možda nema punu podršku za marlin na Qwen2-VL
        "--trust-remote_code",
        "--gpu-memory-utilization", "0.8",
        "--max-model-len", "4096", # Smanjeno na 4096 radi uštede memorije i stabilnosti
        "--limit-mm-per-prompt", "image=10",
        "--port", "8000"
    ]
    
    print(f"Pokretanje stabilnog vLLM 0.6.3 servera za Translator (Qwen2-VL)")
    subprocess.run(cmd, check=True)
