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
    scaledown_window=300,
    secrets=[modal.Secret.from_dotenv()]
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
        from fastapi.responses import JSONResponse
        web_app = FastAPI()
        
        @web_app.post("/")
        async def handle_request(request: Request):
            # Provera API ključa
            expected_key = os.environ.get("MODAL_API_KEY")
            if expected_key:
                api_key = request.headers.get("X-API-Key")
                if api_key != expected_key:
                    return JSONResponse(status_code=403, content={"error": "Neovlašćen pristup. API ključ je neispravan."})

            import base64
            import tempfile
            import os
            
            data = await request.json()
            audio_b64 = data.get("audio_base64")
            initial_prompt = data.get("initial_prompt", "This is a clear speech. Please use punctuation: dots, commas, and capital letters.")
            vad_filter = data.get("vad_filter", True)
            condition_on_previous_text = data.get("condition_on_previous_text", False)
            word_timestamps = data.get("word_timestamps", True)
            
            # Dodatni pragovi za borbu protiv preskakanja
            no_speech_threshold = data.get("no_speech_threshold", 0.6)
            log_prob_threshold = data.get("log_prob_threshold", -1.0)
            compression_ratio_threshold = data.get("compression_ratio_threshold", 2.4)
            
            if not audio_b64:
                return {"error": "audio_base64 is required"}
                
            audio_data = base64.b64decode(audio_b64)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                tmp_audio.write(audio_data)
                tmp_audio_path = tmp_audio.name
            
            try:
                # Forsiramo interpunkciju kroz initial_prompt
                print(f"Transkribujem: {tmp_audio_path}, vad_filter: {vad_filter}, word_timestamps: {word_timestamps}, condition_on_prev: {condition_on_previous_text}")
                segments, info = self.whisper_model.transcribe(
                    tmp_audio_path, 
                    language=None, 
                    beam_size=5,
                    word_timestamps=word_timestamps, # Dobijamo vreme svake reči
                    condition_on_previous_text=condition_on_previous_text,
                    vad_filter=vad_filter,
                    vad_parameters=dict(
                        min_speech_duration_ms=250,
                        speech_pad_ms=400  # Izbegavanje sečenja reči
                    ) if vad_filter else None,
                    initial_prompt=initial_prompt,
                    no_speech_threshold=no_speech_threshold,
                    log_prob_threshold=log_prob_threshold,
                    compression_ratio_threshold=compression_ratio_threshold
                )
                
                result = []
                for s in segments:
                    # Izvlačimo reči sa njihovim timestamp-ovima
                    words = []
                    if s.words:
                        for w in s.words:
                            words.append({"start": w.start, "end": w.end, "word": w.word})
                    
                    result.append({
                        "start": s.start, 
                        "end": s.end, 
                        "text": s.text,
                        "words": words
                    })
                return {"language": info.language, "segments": result}
            except Exception as e:
                print(f"Greška pri transkripciji: {e}")
                return {"error": str(e)}
            finally:
                if os.path.exists(tmp_audio_path):
                    os.remove(tmp_audio_path)
        
        return web_app
