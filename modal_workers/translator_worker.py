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
        "qwen-vl-utils",
        "wheel",
        "ninja"
    )
    .run_commands("pip install flash-attn --no-build-isolation")
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
    import os
    from huggingface_hub import snapshot_download
    
    model_path = "/models/qwen-vl-7b-awq"
    model_id = "Qwen/Qwen2-VL-7B-Instruct-AWQ"
    
    # 1. Provera stanja volumena
    if not os.path.exists(model_path) or not os.listdir(model_path):
        print(f"🔄 Model nije pronađen ili je volumen prazan. Započinjem preuzimanje {model_id}...")
        
        # 2. Automatsko preuzimanje modela
        snapshot_download(
            repo_id=model_id,
            local_dir=model_path,
            local_dir_use_symlinks=False,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot"]
        )
        
        # 3. Trajno čuvanje izmena na volumen
        print("💾 Komitujem preuzete podatke na Modal Volume...")
        model_volume.commit()
        print("✅ Model je spreman.")
    else:
        print("📂 Model je pronađen na volumenu. Preskačem preuzimanje.")

    print("====================================================")
    print("🔥 NOVA AUTONOMNA VERZIJA RADNIKA: 15.05.2026. 🔥")
    print("Optimizacije: Marlin, FA2, Auto-Download, No-Stats")
    print("====================================================")
    
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_path,
        "--served-model-name", "qwen-vl",
        "--quantization", "awq_marlin",
        "--trust-remote-code",
        "--gpu-memory-utilization", "0.7",
        "--max-model-len", "12288",
        "--limit-mm-per-prompt", "image=3",
        "--enforce-eager",
        "--disable-frontend-multiprocessing",
        "--disable-log-stats",
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
        snapshot_download(model_id, local_dir=model_path)
        model_volume.commit()
