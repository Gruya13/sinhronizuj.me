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
        "vllm==0.6.6.post1",
        "huggingface-hub",
        "transformers==4.46.3"
    )
)

app = modal.App("sinhronizuj-lektor")

@app.function(
    gpu="A100-80GB",
    image=image,
    volumes={"/root/.cache/huggingface": huggingface_cache},
    scaledown_window=1800, # Kontejner ostaje topao 30 minuta nakon poslednjeg zahteva
    timeout=3600,
    env={"VLLM_WORKER_MULTIPROC_METHOD": "spawn", "VLLM_USE_V1": "0"}
)
@modal.web_server(port=8000, startup_timeout=600)
def serve():
    """
    Pokreće vLLM OpenAI-kompatibilan server koji služi Qwen 2.5 32B Instruct model.
    """
    import subprocess
    from modal.experimental import stop_fetching_inputs

    # Komanda za pokretanje vLLM servera sa traženim optimizacijama za A100-80GB
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", "Qwen/Qwen2.5-32B-Instruct",
        "--served-model-name", "qwen-lektor",
        "--tensor-parallel-size", "1",
        "--gpu-memory-utilization", "0.95",
        "--max-model-len", "32768",
        "--enable-prefix-caching",
        "--enable-chunked-prefill",
        "--port", "8000"
    ]

    print(f"Pokretanje vLLM servera za model: Qwen/Qwen2.5-32B-Instruct")
    
    try:
        subprocess.run(cmd, check=True)
    except RuntimeError as e:
        error_msg = str(e)
        if "Xid 94" in error_msg or "CUDA" in error_msg:
            print(f"Kritična CUDA greška detektovana: {error_msg}")
            stop_fetching_inputs()
        raise e
    except Exception as e:
        print(f"Sistemska greška u radniku: {e}")
        raise e

if __name__ == "__main__":
    app.run()
