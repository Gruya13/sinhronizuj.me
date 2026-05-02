import modal
import os
import base64
import tempfile
import subprocess

app = modal.App("sinhronizuj-me-tts")

models_volume = modal.Volume.from_name("sinhronizuj-models", create_if_missing=True)
VOLUME_PATH = "/models"
FISH_MODEL = "fishaudio/fish-speech-1.5"

def download_models():
    from huggingface_hub import snapshot_download
    os.makedirs(f"{VOLUME_PATH}/fish-speech-1.5", exist_ok=True)
    print("Downloading Fish Speech...")
    snapshot_download(repo_id=FISH_MODEL, local_dir=f"{VOLUME_PATH}/fish-speech-1.5")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")
    .run_commands("git clone https://github.com/fishaudio/fish-speech.git /opt/fish-speech")
    .run_commands("cd /opt/fish-speech && pip install -e .")
    .pip_install("huggingface-hub")
    .run_function(download_models, volumes={VOLUME_PATH: models_volume})
)

@app.cls(image=image, gpu="L4", volumes={VOLUME_PATH: models_volume}, container_idle_timeout=300)
class TTS_Worker:
    @modal.enter()
    def setup(self):
        self.fish_path = f"{VOLUME_PATH}/fish-speech-1.5"
        self.cwd = "/opt/fish-speech"

    @modal.web_endpoint(method="POST")
    def process_task(self, data: dict):
        text = data.get('text')
        ref_audio_b64 = data.get('reference_audio_base64')
        ref_text = data.get('reference_text')
        
        if not all([text, ref_audio_b64, ref_text]):
            return {"error": "Nedostaju parametri: text, reference_audio_base64, reference_text"}
            
        ref_audio_data = base64.b64decode(ref_audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_ref:
            tmp_ref.write(ref_audio_data)
            tmp_ref_path = tmp_ref.name
            
        output_path = tempfile.mktemp(suffix=".wav")
        
        try:
            cmd = [
                "python", "-m", "tools.generate", 
                "--text", text, 
                "--prompt-audio", tmp_ref_path, 
                "--prompt-text", ref_text,
                "--output", output_path,
                "--checkpoint-path", self.fish_path
            ]
            
            subprocess.run(cmd, cwd=self.cwd, check=True)
            
            with open(output_path, "rb") as audio_file:
                generated_b64 = base64.b64encode(audio_file.read()).decode('utf-8')
                
            return {"audio_base64": generated_b64}
            
        except subprocess.CalledProcessError as e:
            return {"error": f"Fish Speech generisanje propalo: {str(e)}"}
        finally:
            if os.path.exists(tmp_ref_path): os.remove(tmp_ref_path)
            if os.path.exists(output_path): os.remove(output_path)
