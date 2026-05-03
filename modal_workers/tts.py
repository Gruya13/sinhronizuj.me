# v1.1 - Migration to Modal with Fish Speech 1.5 Fixes
import modal
import os
import base64
import tempfile
import subprocess
import glob

app = modal.App("sm-tts-v110")

models_nfs = modal.NetworkFileSystem.from_name("sinhronizuj-models-nfs", create_if_missing=True)
VOLUME_PATH = "/models_nfs"
FISH_MODEL = "fishaudio/fish-speech-1.5"

# Globalne putanje za privremene fajlove unutar containera
TMP_REF_AUDIO = "/tmp/ref_audio.wav"
TMP_OUT_BASE = "/tmp/output_audio"
TMP_OUT_AUDIO = "/tmp/output_audio.wav"

def download_models():
    from huggingface_hub import snapshot_download
    import os
    import shutil
    
    print(f"Započinjem download u {VOLUME_PATH}/fish-speech-1.5")
    os.makedirs(f"{VOLUME_PATH}/fish-speech-1.5", exist_ok=True)
    snapshot_download(repo_id=FISH_MODEL, local_dir=f"{VOLUME_PATH}/fish-speech-1.5")
    print("Download završen.")
    
    config_path = None
    ckpt_path = None
    
    print("Tražim fajlove pomoću os.walk...")
    for root, dirs, files in os.walk(f"{VOLUME_PATH}/fish-speech-1.5"):
        for file in files:
            if file == "config.json":
                config_path = os.path.join(root, file)
            elif file.endswith(".ckpt"):
                ckpt_path = os.path.join(root, file)
                
    print(f"Nađeno: config={config_path}, ckpt={ckpt_path}")
    
    if config_path and ckpt_path:
        unified_dir = f"{VOLUME_PATH}/fish-speech-1.5/unified"
        os.makedirs(unified_dir, exist_ok=True)
        shutil.copy2(config_path, os.path.join(unified_dir, "config.json"))
        shutil.copy2(ckpt_path, os.path.join(unified_dir, "model.ckpt"))
        print(f"Modeli unifikovani u {unified_dir}")
    else:
        print("Greška: Nisu nađeni potrebni fajlovi!")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "portaudio19-dev")
    .run_commands(
        "git clone --branch v1.4.0 https://github.com/fishaudio/fish-speech.git /opt/fish-speech",
        "cd /opt/fish-speech && pip install -e .",
    )
    .pip_install("torch", "torchaudio", "huggingface-hub", "orjson", "matplotlib", "librosa", "soundfile", "vector-quantize-pytorch", "torchcodec==0.11.1")
)

@app.cls(image=image, gpu="L4", network_file_systems={VOLUME_PATH: models_nfs}, scaledown_window=300, timeout=1200)
class WorkerV110:
    @modal.enter()
    def setup(self):
        self.fish_path = f"{VOLUME_PATH}/fish-speech-1.5"
        self.cwd = "/opt/fish-speech"
        
        if not os.path.exists(f"{self.fish_path}/unified/model.ckpt"):
            download_models()

    @modal.fastapi_endpoint(method="POST")
    def task(self, data: dict):
        import traceback
        import base64
        import os
        import subprocess
        import glob
        
        try:
            # Ensure fish_path is set (fallback for weird lifecycle issues)
            if not hasattr(self, 'fish_path'):
                self.fish_path = f"{VOLUME_PATH}/fish-speech-1.5"
            
            text = data.get('text')
            ref_audio_b64 = data.get('reference_audio_base64')
            ref_text = data.get('reference_text')
            
            if not all([text, ref_audio_b64, ref_text]):
                return {"error": "Nedostaju parametri: text, reference_audio_base64, reference_text"}
                
            # Čistimo stare fajlove ako postoje
            for f in [TMP_REF_AUDIO, TMP_OUT_AUDIO]:
                if os.path.exists(f): os.remove(f)
            
            # Save reference audio
            with open(TMP_REF_AUDIO, "wb") as f:
                f.write(base64.b64decode(ref_audio_b64))
            import glob
            # Fish Speech 1.5 koristi model.pth
            # Tražimo ih rekurzivno jer snapshot_download može da ih stavi u podfoldere
            llama_ckpt = next(glob.iglob(f"{self.fish_path}/**/model.pth", recursive=True), None)
            vqgan_ckpt = next(glob.iglob(f"{self.fish_path}/**/firefly-gan-vq-fsq-8x1024-21hz-generator.pth", recursive=True), None)
            
            if not llama_ckpt or not vqgan_ckpt:
                 # Pokušaj sa model.ckpt ako model.pth ne postoji (za starije verzije unutar 1.5)
                 llama_ckpt = llama_ckpt or next(glob.iglob(f"{self.fish_path}/**/model.ckpt", recursive=True), None)
            
            if not llama_ckpt or not vqgan_ckpt:
                return {"error": f"Checkpointi nisu nađeni u {self.fish_path}. Nađeno: Llama={llama_ckpt}, VQGAN={vqgan_ckpt}"}
            
            print(f"[TTS] Koristim Llama: {llama_ckpt}")
            print(f"[TTS] Koristim VQGAN: {vqgan_ckpt}")

            # Dinamičko pronalaženje skripti unutar /opt/fish-speech
            vqgan_script = next(glob.iglob(f"/opt/fish-speech/**/vqgan/inference.py", recursive=True), None)
            llama_script = next(glob.iglob(f"/opt/fish-speech/**/llama/generate.py", recursive=True), None)
            
            if not vqgan_script or not llama_script:
                return {"error": f"Skripte nisu nađene. VQGAN={vqgan_script}, Llama={llama_script}"}

            print(f"[TTS] Koristim VQGAN skriptu: {vqgan_script}")
            print(f"[TTS] Koristim Llama skriptu: {llama_script}")

            # Step 1: Encode (Audio -> Tokens)
            encode_cmd = ["python3", vqgan_script, "-i", TMP_REF_AUDIO, "-o", "fake.npy", "--checkpoint-path", vqgan_ckpt]
            
            env = os.environ.copy()
            env["PYTHONPATH"] = f"/opt/fish-speech:{env.get('PYTHONPATH', '')}"
            
            p1 = subprocess.run(encode_cmd, capture_output=True, text=True, env=env, cwd="/opt/fish-speech")
            if p1.returncode != 0:
                return {"error": f"Step 1 (Encode) failed: {p1.stderr}\nSTDOUT: {p1.stdout}"}
                
            # Step 2: Generate (Tokens -> Semantic Tokens)
            gen_cmd = ["python3", llama_script, "--text", text, "--prompt-text", ref_text, "--prompt-tokens", "fake.npy", "--checkpoint-path", llama_ckpt, "--num-samples", "1"]
            p2 = subprocess.run(gen_cmd, capture_output=True, text=True, env=env, cwd="/opt/fish-speech")
            if p2.returncode != 0:
                return {"error": f"Step 2 (Generate) failed: {p2.stderr}\nSTDOUT: {p2.stdout}"}
                
            # Step 3: Decode (Semantic Tokens -> Audio)
            decode_cmd = ["python3", vqgan_script, "-i", "codes_0.npy", "-o", TMP_OUT_AUDIO, "--checkpoint-path", vqgan_ckpt]
            p3 = subprocess.run(decode_cmd, capture_output=True, text=True, env=env, cwd="/opt/fish-speech")
            if p3.returncode != 0:
                return {"error": f"Step 3 (Decode) failed: {p3.stderr}\nSTDOUT: {p3.stdout}"}
            
            if not os.path.exists(TMP_OUT_AUDIO):
                return {"error": "Finalni audio nije nađen."}
                
            generated_b64 = subprocess.check_output(["base64", "-w", "0", TMP_OUT_AUDIO]).decode().strip()
            return {"audio_base64": generated_b64}
            
        except Exception as e:
            import traceback
            return {"error": f"PIPELINE_ERROR: {str(e)}\n{traceback.format_exc()}"}
        # Cleanup removed to prevent race conditions
@app.local_entrypoint()
def main():
    w = WorkerV110()
    print("Ovaj worker se pokreće preko FastAPI endpointa.")
