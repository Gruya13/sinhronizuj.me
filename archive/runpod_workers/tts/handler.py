import os
import runpod
import base64
import tempfile
import subprocess
from huggingface_hub import snapshot_download

VOLUME_PATH = "/runpod-volume/models"
FISH_MODEL = "fishaudio/fish-speech-1.5"

def ensure_model_exists(repo_id, local_dir):
    full_path = os.path.join(VOLUME_PATH, local_dir)
    if not os.path.exists(full_path):
        print(f"[{repo_id}] Model nije pronadjen na volume-u. Zapocinjem preuzimanje...")
        snapshot_download(repo_id=repo_id, local_dir=full_path, max_workers=8)
        print(f"[{repo_id}] Preuzimanje zavrseno.")
    return full_path

# Provera pri startu kontejnera
fish_path = ensure_model_exists(FISH_MODEL, "fish-speech-1.5")

def handle_tts(text, reference_audio_b64, reference_text):
    # Spašavanje referentnog audia
    ref_audio_data = base64.b64decode(reference_audio_b64)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_ref:
        tmp_ref.write(ref_audio_data)
        tmp_ref_path = tmp_ref.name
        
    output_path = tempfile.mktemp(suffix=".wav")
    
    try:
        # Poziv Fish Speech inferencije (Pretpostavljamo da je instalirana via CLI ili subprocess)
        # Prilagodi ovu komandu specifičnom načinu na koji pokrećeš Fish Speech
        cmd = [
            "python", "-m", "tools.generate", 
            "--text", text, 
            "--prompt-audio", tmp_ref_path, 
            "--prompt-text", reference_text,
            "--output", output_path,
            "--checkpoint-path", fish_path
        ]
        
        subprocess.run(cmd, check=True)
        
        # Citanje generisanog audia i konverzija u Base64
        with open(output_path, "rb") as audio_file:
            generated_b64 = base64.b64encode(audio_file.read()).decode('utf-8')
            
        return {"audio_base64": generated_b64}
        
    except subprocess.CalledProcessError as e:
        return {"error": f"Fish Speech generisanje propalo: {str(e)}"}
    finally:
        if os.path.exists(tmp_ref_path): os.remove(tmp_ref_path)
        if os.path.exists(output_path): os.remove(output_path)


def handler(job):
    job_input = job.get('input', {})
    
    text = job_input.get('text')
    ref_audio = job_input.get('reference_audio_base64')
    ref_text = job_input.get('reference_text')
    
    if not all([text, ref_audio, ref_text]):
        return {"error": "Nedostaju parametri: text, reference_audio_base64, reference_text"}
        
    return handle_tts(text, ref_audio, ref_text)

runpod.serverless.start({"handler": handler})
