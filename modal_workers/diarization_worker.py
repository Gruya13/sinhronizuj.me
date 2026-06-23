import modal
import os
import base64
import tempfile

app = modal.App("sm-diarization")

models_nfs = modal.NetworkFileSystem.from_name("sinhronizuj-models-nfs", create_if_missing=True)
VOLUME_PATH = "/models_nfs"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "pyannote.audio",
        "fastapi",
        "uvicorn",
        "torch",
        "torchaudio"
    )
)

@app.cls(
    gpu="T4",
    image=image,
    network_file_systems={VOLUME_PATH: models_nfs},
    scaledown_window=300,
    timeout=600,
    secrets=[modal.Secret.from_dotenv()]
)
class DiarizationWorker:
    @modal.enter()
    def setup(self):
        # Postavljanje cache foldera na NFS
        os.environ["HF_HOME"] = f"{VOLUME_PATH}/hf_cache"
        os.environ["TORCH_HOME"] = f"{VOLUME_PATH}/torch_cache"
        
        token = os.environ.get("HF_TOKEN")
        
        # Inicijalizujemo PyAnnote pipeline
        from pyannote.audio import Pipeline
        print("Inicijalizujem PyAnnote.audio pipeline...")
        try:
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=token
            )
            print("Uspešno učitan pyannote/speaker-diarization-3.1")
        except Exception as e:
            print(f"Greška pri učitavanju modela 3.1: {e}. Pokušavam sa modelom 3.0...")
            try:
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.0",
                    use_auth_token=token
                )
                print("Uspešno učitan pyannote/speaker-diarization-3.0")
            except Exception as e2:
                print(f"Greška pri učitavanju modela 3.0: {e2}. Pokušavam bez tokena...")
                try:
                    self.pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1"
                    )
                    print("Uspešno učitan pyannote/speaker-diarization-3.1 bez tokena")
                except Exception as e3:
                    print(f"Greška pri učitavanju modela bez tokena: {e3}")
                    self.pipeline = None

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
                    return JSONResponse(status_code=403, content={"error": "Neovlašćen pristup"})
            
            if self.pipeline is None:
                return JSONResponse(
                    status_code=500, 
                    content={"error": "PyAnnote pipeline nije uspešno učitan. Proverite HF_TOKEN u tajnama."}
                )
                
            data = await request.json()
            audio_b64 = data.get("audio_base64")
            
            if not audio_b64:
                return {"error": "audio_base64 je obavezan parametar"}
                
            try:
                audio_data = base64.b64decode(audio_b64)
            except Exception as e:
                return {"error": f"Greška pri dekodiranju base64 zvuka: {str(e)}"}
                
            # Upisivanje u privremeni fajl
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                tmp_audio.write(audio_data)
                tmp_audio_path = tmp_audio.name
                
            try:
                import torch
                # Pokrećemo diarizaciju na GPU (ako je dostupan)
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                self.pipeline.to(device)
                
                print(f"Pokrećem PyAnnote diarizaciju na uređaju: {device}")
                diarization = self.pipeline(tmp_audio_path)
                
                # Formatiramo rezultate
                results = []
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    results.append({
                        "start": float(turn.start),
                        "end": float(turn.end),
                        "speaker": str(speaker)
                    })
                    
                print(f"Diarizacija završena. Prepoznato {len(results)} segmenata.")
                return {"status": "success", "diarization": results}
                
            except Exception as e:
                print(f"Greška tokom diarizacije: {e}")
                return {"error": str(e)}
            finally:
                if os.path.exists(tmp_audio_path):
                    try:
                        os.remove(tmp_audio_path)
                    except Exception:
                        pass
                    
        return web_app
