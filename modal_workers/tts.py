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
        "git clone --branch v1.5.1 https://github.com/fishaudio/fish-speech.git /opt/fish-speech",
        "cd /opt/fish-speech && pip install -e .",
    )
    .pip_install("torch", "torchaudio", "huggingface-hub", "orjson", "matplotlib", "librosa", "soundfile", "vector-quantize-pytorch", "torchcodec==0.11.1")
)

@app.cls(image=image, gpu="L4", network_file_systems={VOLUME_PATH: models_nfs}, scaledown_window=300, timeout=1200, secrets=[modal.Secret.from_dotenv()])
class WorkerV110:
    @modal.enter()
    def setup(self):
        self.fish_path = f"{VOLUME_PATH}/fish-speech-1.5"
        self.cwd = "/opt/fish-speech"
        
        if not os.path.exists(f"{self.fish_path}/unified/model.ckpt"):
            download_models()

    @modal.method()
    def generate_segment(self, segment: dict, ref_indices_path: str, ref_text: str, uuid_str: str) -> dict:
        import os
        import subprocess
        import base64
        import glob
        
        seg_id = segment["id"]
        text = segment["text"]
        
        # Lokalne putanje za ovaj segment u kontejneru
        out_audio = f"/tmp/out_{uuid_str}_{seg_id}.wav"
        default_codes = f"/tmp/codes_0_{uuid_str}_{seg_id}.npy"
        
        # Pronalazenje modela
        llama_ckpt = next(glob.iglob(f"{VOLUME_PATH}/fish-speech-1.5/**/model.pth", recursive=True), None)
        if not llama_ckpt:
            llama_ckpt = next(glob.iglob(f"{VOLUME_PATH}/fish-speech-1.5/**/model.ckpt", recursive=True), None)
        vqgan_ckpt = next(glob.iglob(f"{VOLUME_PATH}/fish-speech-1.5/**/firefly-gan-vq-fsq-8x1024-21hz-generator.pth", recursive=True), None)
        
        vqgan_script = next(glob.iglob(f"/opt/fish-speech/**/vqgan/inference.py", recursive=True), None)
        llama_script = next(glob.iglob(f"/opt/fish-speech/**/text2semantic/inference.py", recursive=True), None)
        
        if not all([llama_ckpt, vqgan_ckpt, vqgan_script, llama_script]):
            return {"id": seg_id, "error": f"Modeli ili skripte nisu pronadjeni. Llama={llama_ckpt}, VQGAN={vqgan_ckpt}"}
            
        env = os.environ.copy()
        env["PYTHONPATH"] = f"/opt/fish-speech:{env.get('PYTHONPATH', '')}"
        
        # Pokrecemo Llama Generate
        # Moramo postaviti cwd=/tmp ili proslediti parametre
        # Koristimo specifican naziv fajla za codes da se ne bi sudarali ako vise procesa radi na istoj masini
        gen_cmd = [
            "python3", llama_script,
            "--text", text,
            "--prompt-text", ref_text,
            "--prompt-tokens", ref_indices_path,
            "--checkpoint-path", os.path.dirname(llama_ckpt),
            "--num-samples", "1",
            "--output-dir", "."
        ]
        
        print(f"[TTS-BATCH] Pokrecem Generate za segment {seg_id}: {text[:30]}...")
        # Llama script podrazumevano pise u codes_0.npy u CWD. Zato pokrecemo u jedinstvenom temp direktorijumu po segmentu!
        seg_tmp_dir = f"/tmp/seg_{uuid_str}_{seg_id}"
        os.makedirs(seg_tmp_dir, exist_ok=True)
        
        p2 = subprocess.run(gen_cmd, capture_output=True, text=True, env=env, cwd=seg_tmp_dir)
        if p2.returncode != 0:
            return {"id": seg_id, "error": f"Generate failed: {p2.stderr or p2.stdout}"}
            
        generated_codes = f"{seg_tmp_dir}/codes_0.npy"
        if not os.path.exists(generated_codes):
            return {"id": seg_id, "error": "codes_0.npy nije generisan."}
            
        # Decode
        decode_cmd = ["python3", vqgan_script, "-i", generated_codes, "-o", out_audio, "--checkpoint-path", vqgan_ckpt]
        p3 = subprocess.run(decode_cmd, capture_output=True, text=True, env=env, cwd=seg_tmp_dir)
        if p3.returncode != 0:
            return {"id": seg_id, "error": f"Decode failed: {p3.stderr or p3.stdout}"}
            
        if not os.path.exists(out_audio):
            return {"id": seg_id, "error": f"Finalni audio za segment {seg_id} nije nadjen."}
            
        # Citanje i Base64 konverzija
        with open(out_audio, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode('utf-8')
            
        # Ciscenje
        import shutil
        try:
            shutil.rmtree(seg_tmp_dir, ignore_errors=True)
            if os.path.exists(out_audio): os.remove(out_audio)
        except Exception:
            pass
            
        return {"id": seg_id, "audio_base64": audio_b64}

    @modal.fastapi_endpoint(method="POST")
    def task(self, data: dict, request = None):
        import traceback
        import base64
        import os
        import subprocess
        import glob
        import uuid
        import shutil
        from fastapi.responses import JSONResponse
        
        # Provera API ključa
        if request is not None:
            expected_key = os.environ.get("MODAL_API_KEY")
            if expected_key:
                api_key = request.headers.get("X-API-Key")
                if api_key != expected_key:
                    return JSONResponse(status_code=403, content={"error": "Neovlašćen pristup. API ključ je neispravan."})
        
        try:
            # Podesavanje putanje
            if not hasattr(self, 'fish_path'):
                self.fish_path = f"{VOLUME_PATH}/fish-speech-1.5"
            
            ref_audio_b64 = data.get('reference_audio_base64')
            ref_text = data.get('reference_text')
            
            if not all([ref_audio_b64, ref_text]):
                return {"error": "Nedostaju parametri: reference_audio_base64, reference_text"}

            # Pretraga modela za korak 1 (Encode)
            vqgan_ckpt = next(glob.iglob(f"{self.fish_path}/**/firefly-gan-vq-fsq-8x1024-21hz-generator.pth", recursive=True), None)
            vqgan_script = next(glob.iglob(f"/opt/fish-speech/**/vqgan/inference.py", recursive=True), None)
            
            if not vqgan_ckpt or not vqgan_script:
                return {"error": f"VQGAN checkpoint ili skripta nisu pronadjeni. CKPT={vqgan_ckpt}, Script={vqgan_script}"}

            # Kreiramo jedinstveni UUID za ovaj zahtev
            req_uuid = str(uuid.uuid4())
            tmp_ref_path = f"/tmp/ref_{req_uuid}.wav"
            
            with open(tmp_ref_path, "wb") as f:
                f.write(base64.b64decode(ref_audio_b64))

            # Korak 1: Encode (Audio -> Tokens)
            # Radimo lokalno na master kontejneru
            tmp_out_wav = f"/tmp/reconstructed_{req_uuid}.wav"
            encode_cmd = ["python3", vqgan_script, "-i", tmp_ref_path, "-o", tmp_out_wav, "--checkpoint-path", vqgan_ckpt]
            
            env = os.environ.copy()
            env["PYTHONPATH"] = f"/opt/fish-speech:{env.get('PYTHONPATH', '')}"
            
            print(f"[TTS] Pokrecem Encode za referentni audio: {' '.join(encode_cmd)}")
            result = subprocess.run(encode_cmd, capture_output=True, text=True, env=env, cwd="/tmp")
            if result.returncode != 0:
                 return {"error": f"Encode referentnog audia neuspesan: {result.stderr or result.stdout}"}
            
            local_npy = tmp_out_wav.rsplit('.', 1)[0] + ".npy"
            if not os.path.exists(local_npy):
                if os.path.exists(tmp_out_wav + ".npy"):
                    local_npy = tmp_out_wav + ".npy"
                else:
                    return {"error": "Encode nije generisao npy fajl."}

            # Kopiramo npy na NFS da bi svi .map() radnici mogli da ga procitaju
            nfs_temp_dir = f"{VOLUME_PATH}/temp"
            os.makedirs(nfs_temp_dir, exist_ok=True)
            nfs_npy_path = f"{nfs_temp_dir}/ref_{req_uuid}.npy"
            shutil.copy(local_npy, nfs_npy_path)
            
            # Cistimo lokalne privremene fajlove
            for f in [tmp_ref_path, tmp_out_wav, local_npy]:
                if os.path.exists(f): os.remove(f)

            # Provera da li se radi o pojedinacnom tekstu ili listi segmenata
            segments = data.get('segments')
            if segments:
                print(f"[TTS] Pokrecem paralelnu obradu za {len(segments)} segmenata preko Modal.map()")
                # Paralelna obrada pomocu Modal .map()
                results = list(self.generate_segment.map(
                    segments,
                    kwargs={"ref_indices_path": nfs_npy_path, "ref_text": ref_text, "uuid_str": req_uuid}
                ))
                
                # Cistimo NFS npy
                if os.path.exists(nfs_npy_path): os.remove(nfs_npy_path)
                return {"status": "success", "results": results}
            else:
                # Backward compatibility za stari pojedinacni format
                text = data.get('text')
                if not text:
                    if os.path.exists(nfs_npy_path): os.remove(nfs_npy_path)
                    return {"error": "Morate poslati 'text' ili 'segments'"}
                
                print(f"[TTS] Pokrecem pojedinacnu obradu (backward compatibility)")
                single_segment = {"id": "0", "text": text}
                res = self.generate_segment.local(single_segment, nfs_npy_path, ref_text, req_uuid)
                if os.path.exists(nfs_npy_path): os.remove(nfs_npy_path)
                return res

        except Exception as e:
            return {"error": f"PIPELINE_ERROR: {str(e)}\n{traceback.format_exc()}"}
        # Cleanup removed to prevent race conditions
@app.local_entrypoint()
def main():
    w = WorkerV110()
    print("Ovaj worker se pokreće preko FastAPI endpointa.")
