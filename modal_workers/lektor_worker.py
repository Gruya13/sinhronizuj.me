import modal

# Inicijalizacija perzistentnog volumena za keširanje modela sa Hugging Face-a
# Montira se na /root/.cache/huggingface kako bi se izbeglo ponovno preuzimanje težina (cca 65GB+)
huggingface_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)

# Definicija slike kontejnera optimizovana za vLLM i NVIDIA A100 hardver
# Koristi se CUDA 12.9.0 i Python 3.12 za maksimalne performanse i kompatibilnost
image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
    .uv_pip_install(
        "vllm==0.19.1",
        "huggingface-hub==1.5.0",
        "transformers==5.5.1"
    )
)

app = modal.App("sinhronizuj-lektor")

@app.function(
    gpu="A100-80GB",
    image=image,
    volumes={"/root/.cache/huggingface": huggingface_cache},
    scaledown_window=1800, # Kontejner ostaje topao 30 minuta nakon poslednjeg zahteva
    timeout=3600,
)
@modal.web_server(port=8000, startup_timeout=600)
def serve():
    """
    Pokreće vLLM OpenAI-kompatibilan server koji služi Qwen 2.5 32B Instruct model.
    Implementirana je robusna obrada grešaka za CUDA Xid 94 događaje.
    """
    import subprocess
    from modal.experimental import stop_fetching_inputs

    # Komanda za pokretanje vLLM servera sa traženim optimizacijama za A100-80GB
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", "Qwen/Qwen2.5-32B-Instruct",
        "--tensor-parallel-size", "1",
        "--gpu-memory-utilization", "0.95",
        "--max-model-len", "32768",
        "--enable-prefix-caching",
        "--enable-chunked-prefill",
        "--port", "8000"
    ]

    print(f"Pokretanje vLLM servera za model: Qwen/Qwen2.5-32B-Instruct")
    
    try:
        # Pokretanje servera i čekanje na završetak ili grešku
        subprocess.run(cmd, check=True)
    except RuntimeError as e:
        # Specifično hvatanje CUDA grešaka (npr. Xid 94) prema zahtevu
        error_msg = str(e)
        if "Xid 94" in error_msg or "CUDA" in error_msg:
            print(f"Kritična CUDA greška detektovana: {error_msg}")
            # Modal procedura za oporavak: prestani sa preuzimanjem novih inputa i dozvoli gašenje instance
            stop_fetching_inputs()
        raise e
    except Exception as e:
        # Opšta obrada ostalih kritičnih grešaka
        print(f"Sistemska greška u radniku: {e}")
        raise e

if __name__ == "__main__":
    app.run()
