import modal
import os

# Konfiguracija volumena
VOLUME_PATH = "/models"
models_volume = modal.NetworkFileSystem.from_name("sinhronizuj-models", create_if_missing=True)

# Konstanta modela
WHISPER_MODEL = "Systran/faster-whisper-large-v3"

def download_whisper():
    from huggingface_hub import snapshot_download
    import os
    whisper_dir = f"{VOLUME_PATH}/faster-whisper-v3"
    if not os.path.exists(whisper_dir):
        print(f"Preuzimanje Whisper modela: {WHISPER_MODEL}")
        snapshot_download(WHISPER_MODEL, local_dir=whisper_dir)

# Koristimo CUDA image umesto debian_slim kako bismo imali libcublas.so.12 i ostale CUDA biblioteke
image_stt = (
    modal.Image.from_registry("nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04", add_python="3.11")
    .apt_install("git", "ffmpeg")
    .pip_install(
        "faster-whisper",
        "huggingface-hub",
        "torch",
        "torchaudio",
        "fastapi",
        "uvicorn"
    )
    .run_function(download_whisper, network_file_systems={VOLUME_PATH: models_volume})
)

app = modal.App("sm-stt-only")

@app.cls(
    gpu="T4", 
    network_file_systems={VOLUME_PATH: models_volume}, 
    image=image_stt, 
    timeout=600,
    scaledown_window=300
)
class STTWorker:
    @modal.enter()
    def load_model(self):
        from faster_whisper import WhisperModel
        print("Učitavanje Faster-Whisper modela na T4...")
        # Putanja do modela na perzistentnom volumenu
        model_path = f"{VOLUME_PATH}/faster-whisper-v3"
        self.whisper_model = WhisperModel(model_path, device="cuda", compute_type="float16")

    @modal.asgi_app()
    def task(self):
        from fastapi import FastAPI, Request
        web_app = FastAPI()
        
        @web_app.post("/")
        async def handle_request(request: Request):
            import base64
            import tempfile
            import os
            
            data = await request.json()
            audio_b64 = data.get("audio_base64")
            if not audio_b64:
                return {"error": "audio_base64 is required"}
                
            audio_data = base64.b64decode(audio_b64)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                tmp_audio.write(audio_data)
                tmp_audio_path = tmp_audio.name
            
            try:
                # Koristimo već učitan model unutar iste instance (self)
                print(f"Transkribujem fajl: {tmp_audio_path}")
                segments, info = self.whisper_model.transcribe(tmp_audio_path, language=None, beam_size=5)
                result = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
                return {"language": info.language, "segments": result}
            except Exception as e:
                print(f"Greška pri transkripciji: {e}")
                return {"error": str(e)}
            finally:
                if os.path.exists(tmp_audio_path):
                    os.remove(tmp_audio_path)
        
        return web_app
