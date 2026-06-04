import modal

# Inicijalizacija perzistentnog volumena za keširanje modela sa Hugging Face-a
huggingface_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)

# Definicija slike kontejnera optimizovana za vLLM i NVIDIA A100 hardver
# Koristimo stabilne verzije biblioteka
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

app = modal.App("sinhronizuj-lektor")

@app.function(
    gpu="A10G",
    image=image,
    volumes={"/root/.cache/huggingface": huggingface_cache},
    scaledown_window=1800, # Kontejner ostaje topao 30 minuta nakon poslednjeg zahteva
    timeout=3600,
    env={"VLLM_WORKER_MULTIPROC_METHOD": "spawn", "VLLM_USE_V1": "0"}
)
@modal.web_server(port=8000, startup_timeout=600)
def serve():
    """
    Pokreće vLLM OpenAI-kompatibilan server koji služi Qwen 2.5 32B Instruct AWQ model.
    """
    import subprocess
    from modal.experimental import stop_fetching_inputs

    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", "Qwen/Qwen2.5-14B-Instruct-AWQ",
        "--quantization", "awq_marlin",
        "--served-model-name", "qwen-lektor",
        "--tensor-parallel-size", "1",
        "--gpu-memory-utilization", "0.90",
        "--max-model-len", "4096",
        "--enable-prefix-caching",
        "--enable-chunked-prefill",
        "--port", "8000"
    ]

    print(f"Pokretanje vLLM servera za model: Qwen/Qwen2.5-14B-Instruct-AWQ")
    subprocess.Popen(cmd)

if __name__ == "__main__":
    app.run()
