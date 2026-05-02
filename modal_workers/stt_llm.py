import modal
import os
import base64
import tempfile

app = modal.App("sinhronizuj-me-stt-llm")

# Volume for caching Hugging Face models
models_volume = modal.Volume.from_name("sinhronizuj-models", create_if_missing=True)
VOLUME_PATH = "/models"

WHISPER_MODEL = "Systran/faster-whisper-large-v3"
QWEN_MODEL = "Qwen/Qwen2-VL-7B-Instruct-AWQ"

def download_models():
    from huggingface_hub import snapshot_download
    os.makedirs(f"{VOLUME_PATH}/faster-whisper-v3", exist_ok=True)
    os.makedirs(f"{VOLUME_PATH}/qwen2-vl-7b-awq", exist_ok=True)
    
    print("Downloading Whisper...")
    snapshot_download(repo_id=WHISPER_MODEL, local_dir=f"{VOLUME_PATH}/faster-whisper-v3")
    print("Downloading Qwen...")
    snapshot_download(repo_id=QWEN_MODEL, local_dir=f"{VOLUME_PATH}/qwen2-vl-7b-awq")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6")
    .pip_install(
        "huggingface-hub",
        "faster-whisper",
        "vllm", 
        "torch==2.4.0",
        "torchaudio==2.4.0",
        "opencv-python-headless",
        extra_index_url="https://download.pytorch.org/whl/cu121"
    )
    .run_function(download_models, volumes={VOLUME_PATH: models_volume})
)

@app.cls(image=image, gpu="A100", volumes={VOLUME_PATH: models_volume}, scaledown_window=300)
class STT_LLM_Worker:
    @modal.enter()
    def load_models(self):
        from faster_whisper import WhisperModel
        from vllm import LLM
        
        self.whisper_path = f"{VOLUME_PATH}/faster-whisper-v3"
        self.qwen_path = f"{VOLUME_PATH}/qwen2-vl-7b-awq"
        
        print("Inicijalizacija Faster-Whisper modela...")
        self.whisper_model = WhisperModel(self.whisper_path, device="cuda", compute_type="float16")
        
        print("Inicijalizacija vLLM Qwen modela...")
        self.llm = LLM(
            model=self.qwen_path,
            quantization="awq",
            gpu_memory_utilization=0.85,
            max_model_len=4096,
            tensor_parallel_size=1
        )

    def handle_transcribe(self, audio_b64: str):
        audio_data = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            tmp_audio.write(audio_data)
            tmp_audio_path = tmp_audio.name
        
        segments, info = self.whisper_model.transcribe(tmp_audio_path, language="sr", beam_size=5)
        result = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        
        os.remove(tmp_audio_path)
        return {"language": info.language, "segments": result}

    def handle_translate(self, prompt: str, frames_b64: list):
        from vllm import SamplingParams
        
        messages = [{"role": "user", "content": []}]
        for img_b64 in frames_b64:
            messages[0]["content"].append({
                "type": "image_url", 
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
            })
            
        messages[0]["content"].append({"type": "text", "text": prompt})
        
        sampling_params = SamplingParams(temperature=0.3, max_tokens=2048)
        outputs = self.llm.chat(messages, sampling_params=sampling_params)
        
        return {"translation": outputs[0].outputs[0].text}

    @modal.fastapi_endpoint(method="POST")
    def process_task(self, data: dict):
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
                return {"error": f"Nepoznat task_type: {task_type}"}
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
