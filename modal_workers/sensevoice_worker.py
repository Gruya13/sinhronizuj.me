import modal
import os

def download_sensevoice():
    from funasr import AutoModel
    print("Preuzimanje SenseVoice modela sa HuggingFace u lokalni cache slike...")
    # Preuzimamo model sa HuggingFace na CPU tokom izgradnje slike
    AutoModel(
        model="FunAudioLLM/SenseVoiceSmall",
        device="cpu",
        hub="hf",
        disable_update=True
    )

# Slikamo sve i ugrađujemo model u sam Docker image
image_sensevoice = (
    modal.Image.from_registry("nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04", add_python="3.11")
    .apt_install("git", "ffmpeg")
    .pip_install(
        "funasr",
        "huggingface-hub",
        "transformers",
        "torch",
        "torchaudio",
        "fastapi",
        "uvicorn"
    )
    .run_function(download_sensevoice)
)

app = modal.App("sm-sensevoice-only")

@app.cls(
    gpu="T4", 
    image=image_sensevoice, 
    timeout=600,
    scaledown_window=300,
    secrets=[modal.Secret.from_dotenv()]
)
class SenseVoiceWorker:
    @modal.enter()
    def load_model(self):
        from funasr import AutoModel
        print("Učitavanje SenseVoice-Small modela na T4...")
        # Model se učitava direktno iz ugrađene slike u GPU memoriju
        self.model = AutoModel(
            model="FunAudioLLM/SenseVoiceSmall", 
            device="cuda",
            hub="hf",
            disable_update=True
        )

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
            
            data = await request.json()
            audio_b64 = data.get("audio_base64")
            if not audio_b64:
                return {"error": "audio_base64 is required"}
                
            audio_data = base64.b64decode(audio_b64)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                tmp_audio.write(audio_data)
                tmp_audio_path = tmp_audio.name
            
            try:
                print(f"SenseVoice: Transkribujem fajl: {tmp_audio_path}")
                res = self.model.generate(
                    input=tmp_audio_path,
                    cache={},
                    language="auto",
                    use_itn=True
                )
                
                text = ""
                if res and len(res) > 0:
                    text = res[0].get("text", "")
                    if not text:
                        text = res[0].get("preds", "")
                
                print(f"SenseVoice: Uspešno transkribovano: {text[:100]}...")
                return {"text": text}
            except Exception as e:
                print(f"SenseVoice greška pri transkripciji: {e}")
                return {"error": str(e)}
            finally:
                if os.path.exists(tmp_audio_path):
                    os.remove(tmp_audio_path)
        
        return web_app
