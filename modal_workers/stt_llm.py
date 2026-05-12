import modal
import os
import time

# Konfiguracija volumena
VOLUME_PATH = "/models"
models_volume = modal.NetworkFileSystem.from_name("sinhronizuj-models", create_if_missing=True)

# Konstante modela
STT_MODEL = "Qwen/Qwen2-VL-7B-Instruct"
LEKTOR_MODEL = "Qwen/Qwen3.6-27B-FP8"

def download_models():
    from huggingface_hub import snapshot_download
    import os
    import traceback

    try:
        # Provera STT modela
        stt_dir = f"{VOLUME_PATH}/qwen-vl-7b"
        if not os.path.exists(stt_dir):
            print(f"Preuzimanje STT modela: {STT_MODEL}")
            snapshot_download(STT_MODEL, local_dir=stt_dir)
        else:
            print("STT model vec postoji, preskacem download.")
        
        # Provera Lektor modela (27B FP8)
        lektor_dir = f"{VOLUME_PATH}/qwen-27b-fp8"
        if not os.path.exists(os.path.join(lektor_dir, "config.json")):
            print(f"Preuzimanje Lektor modela: {LEKTOR_MODEL}")
            os.makedirs(lektor_dir, exist_ok=True)
            snapshot_download(repo_id=LEKTOR_MODEL, local_dir=lektor_dir, cache_dir="/tmp/hf_cache")
            print("Download Lektora zavrsen.")
        else:
            print("Lektor model vec postoji, preskacem download.")
            
        print("Sve provereno uspesno.")
    except Exception as e:
        print("GRESKA TOKOM DOWNLOAD-A:")
        traceback.print_exc()
        if "File exists" not in str(e):
            raise e

image_stt = (
    modal.Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu22.04")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6", "python3.11", "python3-pip", "python3.11-dev")
    .run_commands("ln -s /usr/bin/python3.11 /usr/local/bin/python")
    .run_commands("python -m pip install --upgrade pip")
    .pip_install(
        "torch==2.4.0",
        "vllm==0.6.3.post1",
        "huggingface-hub",
        "accelerate"
    )
    .run_commands("python -m pip install git+https://github.com/huggingface/transformers.git --force-reinstall")
)

image_lektor = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6", "python3.11", "python3-pip", "python3.11-dev", "ninja-build")
    .run_commands("ln -s /usr/bin/python3.11 /usr/local/bin/python")
    .run_commands("python -m pip install --upgrade pip")
    .pip_install("torch==2.4.0", "torchvision", "torchaudio", index_url="https://download.pytorch.org/whl/cu124")
    .pip_install(
        "huggingface-hub",
        "accelerate",
        "vllm>=0.7.0"
    )
    .run_commands("python -m pip install git+https://github.com/huggingface/transformers.git --force-reinstall")
    .run_function(download_models, network_file_systems={VOLUME_PATH: models_volume})
)

app = modal.App("sm-stt")

@app.cls(
    gpu="A100",  # Vraceno na standardni A100 radi ustede
    network_file_systems={VOLUME_PATH: models_volume}, 
    image=image_stt, 
    timeout=600,
    scaledown_window=300
)
class Worker:
    def __init__(self):
        self.stt_path = f"{VOLUME_PATH}/qwen-vl-7b"

    @modal.enter()
    def load_models(self):
        from vllm import LLM
        print("Inicijalizacija vLLM STT modela...")
        self.llm = LLM(
            model=self.stt_path,
            trust_remote_code=True,
            gpu_memory_utilization=0.9,
            max_model_len=4096,
            limit_mm_per_prompt={"image": 1, "video": 0}
        )

    @modal.method()
    def handle_translate(self, prompt: str, frames_base64: list):
        from vllm import SamplingParams
        content = [{"type": "text", "text": prompt}]
        for f in frames_base64:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{f}"}})
        messages = [{"role": "user", "content": content}]
        sampling_params = SamplingParams(temperature=0.1, max_tokens=1024)
        outputs = self.llm.chat(messages, sampling_params=sampling_params)
        return {"translation": outputs[0].outputs[0].text}

    @modal.fastapi_endpoint(method="POST")
    def task(self, data: dict):
        if data.get("task") == "translate":
            return self.handle_translate(data.get("prompt"), data.get("frames_base64", []))
        return {"error": "Unknown task"}

@app.cls(
    gpu="A100", # Najjeftinija opcija
    network_file_systems={VOLUME_PATH: models_volume}, 
    image=image_lektor, 
    timeout=1200,
    scaledown_window=300,
    env={
        "VLLM_USE_V1": "0", # KLJUČNO: Koristimo stabilni V0 engine
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn", 
        "VLLM_ENGINE_READY_TIMEOUT_S": "1200"
    }
)
class LektorWorker:
    def __init__(self):
        self.lektor_path = f"{VOLUME_PATH}/qwen-27b-fp8"

    @modal.enter()
    def load_models(self):
        from vllm import LLM
        print("Inicijalizacija vLLM Lektor modela (27B FP8) na A100...")
        self.llm = LLM(
            model=self.lektor_path,
            trust_remote_code=True,
            gpu_memory_utilization=0.8, # Konzervativno radi sprecavanja OOM
            max_model_len=4096,
            quantization="fp8",
            enforce_eager=True # Smanjuje memorijski peak
        )

    @modal.method()
    def handle_lektor(self, prompt: str):
        from vllm import SamplingParams
        messages = [{"role": "user", "content": prompt}]
        sampling_params = SamplingParams(temperature=0.2, max_tokens=2048)
        outputs = self.llm.chat(messages, sampling_params=sampling_params)
        return {"translation": outputs[0].outputs[0].text}

    @modal.fastapi_endpoint(method="POST")
    def task(self, data: dict):
        if data.get("task") == "lektor":
            return self.handle_lektor(data.get("prompt"))
        return {"error": "Unknown task"}

@app.local_entrypoint()
def test_lektor_init():
    lektor = LektorWorker()
    try:
        result = lektor.handle_lektor.remote("test")
        print(f"USPEH! Rezultat: {result}")
    except Exception as e:
        print(f"GRESKA: {e}")
