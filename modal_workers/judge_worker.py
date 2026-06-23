import modal

# Inicijalizacija perzistentnog volumena za keširanje modela sa Hugging Face-a
huggingface_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)

# Definicija slike kontejnera optimizovana za vLLM i NVIDIA A10G hardver
image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6")
    .pip_install("torch==2.5.1", "torchvision", index_url="https://download.pytorch.org/whl/cu124")
    .pip_install(
        "vllm",
        "huggingface-hub",
        "transformers",
        "git+https://github.com/nicta/pyairports.git"
    )
)

app = modal.App("sinhronizuj-judge")

@app.function(
    gpu="A10G",
    image=image,
    volumes={"/root/.cache/huggingface": huggingface_cache},
    scaledown_window=1800, # Kontejner ostaje topao 30 minuta nakon poslednjeg zahteva
    timeout=3600,
    env={"VLLM_WORKER_MULTIPROC_METHOD": "spawn", "VLLM_USE_V1": "0"},
    secrets=[modal.Secret.from_dotenv()]
)
@modal.web_server(port=8000, startup_timeout=600)
def serve():
    """
    Pokreće vLLM OpenAI-kompatibilan server koji služi Meta-Llama-3.1-8B-Instruct model.
    """
    import subprocess
    import os

    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", "meta-llama/Llama-3.1-8B-Instruct",
        "--served-model-name", "llama-judge",
        "--tensor-parallel-size", "1",
        "--gpu-memory-utilization", "0.90",
        "--max-model-len", "4096",
        "--enable-prefix-caching",
        "--port", "8000"
    ]

    api_key = os.environ.get("MODAL_API_KEY")
    if api_key:
        print("[JUDGE-WORKER] Aktiviram vLLM API autentifikaciju sa ključem.")
        cmd.extend(["--api-key", api_key])

    print("Pokretanje vLLM servera za model: meta-llama/Llama-3.1-8B-Instruct")
    subprocess.Popen(cmd)

if __name__ == "__main__":
    app.run()
