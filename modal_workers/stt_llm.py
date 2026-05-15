import modal
import os
import time

# Konfiguracija volumena
VOLUME_PATH = "/models"
models_volume = modal.NetworkFileSystem.from_name("sinhronizuj-models", create_if_missing=True)

# Konstante modela - Prelazak na STABILNI 32B AWQ model
STT_MODEL = "Qwen/Qwen2-VL-7B-Instruct"

def download_models():
    from huggingface_hub import snapshot_download
    import os
    
    # Provera STT modela
    stt_dir = f"{VOLUME_PATH}/qwen-vl-7b"
    if not os.path.exists(stt_dir):
        print(f"Preuzimanje STT modela: {STT_MODEL}")
        snapshot_download(STT_MODEL, local_dir=stt_dir)
    

    print("Sve provereno uspesno.")

# Koristimo stabilan vLLM 0.6.4.post1 koji je 'zlatni standard' za AWQ modele
image_base = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6", "python3.11", "python3-pip", "python3.11-dev", "ninja-build")
    .run_commands("ln -s /usr/bin/python3.11 /usr/local/bin/python")
    .run_commands("python -m pip install --upgrade pip")
    .pip_install("torch==2.4.0", "torchvision", "torchaudio", index_url="https://download.pytorch.org/whl/cu124")
    .pip_install(
        "huggingface-hub",
        "accelerate",
        "vllm==0.6.4.post1"
    )
    .run_commands("python -m pip install git+https://github.com/huggingface/transformers.git --force-reinstall")
    .run_function(download_models, network_file_systems={VOLUME_PATH: models_volume})
)

app = modal.App("sm-stt")

@app.cls(
    gpu="A100", 
    network_file_systems={VOLUME_PATH: models_volume}, 
    image=image_base, 
    timeout=600,
    scaledown_window=300
)
class Worker:
    def __init__(self):
        self.stt_path = f"{VOLUME_PATH}/qwen-vl-7b"

    @modal.enter()
    def load_models(self):
        from vllm import LLM
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

