import modal
import os
import time

# Konfiguracija volumena
VOLUME_PATH = "/models"
models_volume = modal.NetworkFileSystem.from_name("sinhronizuj-models", create_if_missing=True)

# Konstante modela - Prelazak na STABILNI 32B AWQ model
STT_MODEL = "Qwen/Qwen2-VL-7B-Instruct"
WHISPER_MODEL = "Systran/faster-whisper-large-v3"

def download_models():
    from huggingface_hub import snapshot_download
    import os
    
    # Provera STT modela
    stt_dir = f"{VOLUME_PATH}/qwen-vl-7b"
    if not os.path.exists(stt_dir):
        print(f"Preuzimanje STT modela: {STT_MODEL}")
        snapshot_download(STT_MODEL, local_dir=stt_dir)
        
    # Provera Whisper modela
    whisper_dir = f"{VOLUME_PATH}/faster-whisper-v3"
    if not os.path.exists(whisper_dir):
        print(f"Preuzimanje Whisper modela: {WHISPER_MODEL}")
        snapshot_download(WHISPER_MODEL, local_dir=whisper_dir)

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
        "vllm==0.6.4.post1",
        "faster-whisper",
        "opencv-python-headless",
        "transformers==4.46.1"
    )
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
        self.whisper_path = f"{VOLUME_PATH}/faster-whisper-v3"

    @modal.enter()
    def load_models(self):
        from faster_whisper import WhisperModel
        from vllm import LLM
        
        print("Inicijalizacija vLLM Qwen modela...")
        self.llm = LLM(
            model=self.stt_path,
            trust_remote_code=True,
            gpu_memory_utilization=0.8,
            max_model_len=4096,
            limit_mm_per_prompt={"image": 1, "video": 0}
        )

        print("Inicijalizacija Faster-Whisper modela...")
        self.whisper_model = WhisperModel(self.whisper_path, device="cuda", compute_type="float16")

    def handle_transcribe(self, audio_b64: str):
        import base64
        import tempfile
        import os
        
        audio_data = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            tmp_audio.write(audio_data)
            tmp_audio_path = tmp_audio.name
        
        segments, info = self.whisper_model.transcribe(tmp_audio_path, language=None, beam_size=5)
        result = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        
        os.remove(tmp_audio_path)
        return {"language": info.language, "segments": result}

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
        task_type = data.get('task')
        try:
            if task_type == "transcribe":
                audio_b64 = data.get("audio_base64")
                if not audio_b64:
                    return {"error": "Nedostaje audio_base64"}
                return self.handle_transcribe(audio_b64)
                
            elif task_type == "translate":
                prompt = data.get("prompt")
                frames_b64 = data.get("frames_base64", [])
                if not prompt:
                    return {"error": "Nedostaje prompt"}
                return self.handle_translate(prompt, frames_b64)
                
            elif task_type == "both":
                audio_b64 = data.get("audio_base64")
                prompt_template = data.get("prompt_template", "Prevedi ovaj srpski transkript na engleski uzimajuci u obzir vizuelni kontekst: {transcript}")
                frames_b64 = data.get("frames_base64", [])
                
                stt_result = self.handle_transcribe(audio_b64)
                transcript = " ".join([s["text"] for s in stt_result["segments"]])
                
                prompt = prompt_template.replace("{transcript}", transcript)
                translation_result = self.handle_translate(prompt, frames_b64)
                
                return {
                    "transcript": stt_result["segments"],
                    "translation": translation_result["translation"]
                }
            else:
                return {"error": f"Unknown task: {task_type}"}
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

