import modal
import os
import urllib.request

app = modal.App("sm-wav2lip")

models_nfs = modal.NetworkFileSystem.from_name("sinhronizuj-models-nfs", create_if_missing=True)
VOLUME_PATH = "/models_nfs"

def download_wav2lip_checkpoints():
    import os
    import urllib.request
    wav2lip_dir = f"{VOLUME_PATH}/wav2lip"
    os.makedirs(wav2lip_dir, exist_ok=True)
    
    # Preuzimanje wav2lip_gan.pth
    gan_path = f"{wav2lip_dir}/wav2lip_gan.pth"
    if not os.path.exists(gan_path):
        print("Preuzimam Wav2Lip GAN checkpoint sa HuggingFace-a...")
        url = "https://huggingface.co/briaai/Wav2Lip/resolve/main/wav2lip_gan.pth"
        urllib.request.urlretrieve(url, gan_path)
        print("Wav2Lip GAN checkpoint uspešno sačuvan.")
        
    # Preuzimanje s3fd face detector modela
    s3fd_dir = f"{VOLUME_PATH}/wav2lip/face_detection/detection/sfd"
    os.makedirs(s3fd_dir, exist_ok=True)
    s3fd_path = f"{s3fd_dir}/s3fd-619a316812.pth"
    if not os.path.exists(s3fd_path):
        print("Preuzimam s3fd face detection model...")
        url = "https://huggingface.co/adrianbulat/large-models/resolve/main/s3fd-619a316812.pth"
        urllib.request.urlretrieve(url, s3fd_path)
        print("s3fd model uspešno sačuvan.")

def download_gfpgan_checkpoint():
    import os
    import urllib.request
    gfpgan_dir = f"{VOLUME_PATH}/gfpgan"
    os.makedirs(gfpgan_dir, exist_ok=True)
    gfpgan_path = f"{gfpgan_dir}/GFPGANv1.4.pth"
    if not os.path.exists(gfpgan_path):
        print("Preuzimam GFPGAN v1.4 checkpoint sa GitHub-a...")
        url = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
        urllib.request.urlretrieve(url, gfpgan_path)
        print("GFPGAN checkpoint uspešno sačuvan.")

def enhance_video_faces(input_video_path, output_video_path, model_path):
    import sys
    import types
    # Patch za basicsr transform import problem u novijim verzijama torchvision
    try:
        import torchvision.transforms.functional_tensor
    except ImportError:
        m = types.ModuleType('torchvision.transforms.functional_tensor')
        sys.modules['torchvision.transforms.functional_tensor'] = m
        
    import cv2
    import torch
    import os
    import shutil
    import subprocess
    from gfpgan import GFPGANer
    
    print(f"[GFPGAN] Pokrećem restauraciju lica na videu: {input_video_path}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Inicijalizacija restorer-a
    restorer = GFPGANer(
        model_path=model_path,
        upscale=1,
        arch='clean',
        channel_multiplier=2,
        bg_upsampler=None,
        device=device
    )
    
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        print(f"[GFPGAN ERROR] Nije moguće otvoriti video: {input_video_path}")
        shutil.copy2(input_video_path, output_video_path)
        return
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    temp_no_audio = input_video_path + ".noaudio.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_no_audio, fourcc, fps, (width, height))
    
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_idx += 1
        if frame_idx % 50 == 0 or frame_idx == 1:
            print(f"[GFPGAN] Procesirano {frame_idx}/{total_frames} frejmova...")
            
        try:
            _, _, restored_frame = restorer.enhance(
                frame,
                has_aligned=False,
                only_center_face=False,
                paste_back=True
            )
            out.write(restored_frame)
        except Exception as e:
            print(f"[GFPGAN WARNING] Greška pri obradi frejma {frame_idx}: {e}")
            out.write(frame)
            
    cap.release()
    out.release()
    
    # Kopiranje audio trake sa originalnog videa na poboljšani video
    print("[GFPGAN] Spajam poboljšani video i audio...")
    cmd = [
        "ffmpeg", "-y",
        "-i", temp_no_audio,
        "-i", input_video_path,
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_video_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    if os.path.exists(temp_no_audio):
        os.remove(temp_no_audio)
        
    if res.returncode != 0:
        print(f"[GFPGAN ERROR] FFmpeg spajanje nije uspelo: {res.stderr}")
        shutil.copy2(temp_no_audio, output_video_path)
    else:
        print("[GFPGAN] Uspešno završena restauracija lica i spajanje audia.")

# Definišemo sliku sa CUDA, Python 3.10 i zavisnostima za Wav2Lip i GFPGAN
image = (
    modal.Image.from_registry("nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04", add_python="3.10")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6", "libgl1-mesa-glx", "libglib2.0-0")
    .run_commands(
        "git clone https://github.com/Rudrabha/Wav2Lip.git /opt/Wav2Lip"
    )
    .pip_install(
        "torch", "torchvision", "opencv-python-headless", "librosa==0.9.2", "numba==0.56.4",
        "tqdm", "fastapi", "uvicorn", "python-multipart", "requests", "gdown",
        "gfpgan", "facexlib"
    )
)

@app.cls(image=image, gpu="T4", network_file_systems={VOLUME_PATH: models_nfs}, scaledown_window=300, timeout=1200, secrets=[modal.Secret.from_dotenv()])
class Wav2LipWorker:
    @modal.enter()
    def setup(self):
        import os
        import shutil
        
        # Postavljanje keša za torch hub u mrežni fajl sistem
        os.environ["TORCH_HOME"] = f"{VOLUME_PATH}/torch_cache"
        os.makedirs(f"{VOLUME_PATH}/torch_cache", exist_ok=True)
        
        self.wav2lip_dir = "/opt/Wav2Lip"
        self.gan_checkpoint = f"{VOLUME_PATH}/wav2lip/wav2lip_gan.pth"
        self.s3fd_checkpoint = f"{VOLUME_PATH}/wav2lip/face_detection/detection/sfd/s3fd-619a316812.pth"
        self.gfpgan_checkpoint = f"{VOLUME_PATH}/gfpgan/GFPGANv1.4.pth"
        
        # Provera i preuzimanje ako nedostaju
        if not os.path.exists(self.gan_checkpoint) or not os.path.exists(self.s3fd_checkpoint):
            download_wav2lip_checkpoints()
            
        if not os.path.exists(self.gfpgan_checkpoint):
            download_gfpgan_checkpoint()
            
        # Kopiranje s3fd modela u odgovarajući folder unutar kloniranog Wav2Lip-a kako bi ga kod pronašao lokalno
        dest_s3fd_dir = f"{self.wav2lip_dir}/face_detection/detection/sfd"
        os.makedirs(dest_s3fd_dir, exist_ok=True)
        if not os.path.exists(f"{dest_s3fd_dir}/s3fd-619a316812.pth"):
            shutil.copy2(self.s3fd_checkpoint, f"{dest_s3fd_dir}/s3fd-619a316812.pth")
            
        # Takođe možemo kopirati i u ~/.cache/torch/hub/checkpoints/ za svaki slučaj
        torch_hub_dir = f"{VOLUME_PATH}/torch_cache/hub/checkpoints"
        os.makedirs(torch_hub_dir, exist_ok=True)
        if not os.path.exists(f"{torch_hub_dir}/s3fd-619a316812.pth"):
            shutil.copy2(self.s3fd_checkpoint, f"{torch_hub_dir}/s3fd-619a316812.pth")

    @modal.asgi_app()
    def task(self):
        from fastapi import FastAPI, Request, BackgroundTasks
        from fastapi.responses import JSONResponse
        import uuid
        import json
        import shutil
        import base64
        import requests
        import subprocess
        
        web_app = FastAPI()
        
        jobs_dir = f"{VOLUME_PATH}/jobs"
        os.makedirs(jobs_dir, exist_ok=True)
        
        def save_job(job_id, data):
            with open(os.path.join(jobs_dir, f"{job_id}.json"), "w") as f:
                json.dump(data, f)
                
        def get_job(job_id):
            path = os.path.join(jobs_dir, f"{job_id}.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    return json.load(f)
            return None

        def run_inference_bg(job_id: str, data: dict):
            # Stvarna inferencija
            temp_dir = f"/tmp/{job_id}"
            os.makedirs(temp_dir, exist_ok=True)
            
            video_url = data.get("video_url")
            audio_url = data.get("audio_url")
            video_base64 = data.get("video_base64")
            audio_base64 = data.get("audio_base64")
            
            video_path = f"{temp_dir}/input_video.mp4"
            audio_path = f"{temp_dir}/input_audio.wav"
            output_path = f"{temp_dir}/output.mp4"
            
            try:
                # Preuzimanje videa
                if video_url:
                    resp = requests.get(video_url, timeout=300)
                    resp.raise_for_status()
                    with open(video_path, "wb") as f:
                        f.write(resp.content)
                else:
                    with open(video_path, "wb") as f:
                        f.write(base64.b64decode(video_base64))
                        
                # Preuzimanje audia
                if audio_url:
                    resp = requests.get(audio_url, timeout=300)
                    resp.raise_for_status()
                    with open(audio_path, "wb") as f:
                        f.write(resp.content)
                else:
                    with open(audio_path, "wb") as f:
                        f.write(base64.b64decode(audio_base64))
                        
                cmd = [
                    "python", f"{self.wav2lip_dir}/inference.py",
                    "--checkpoint_path", self.gan_checkpoint,
                    "--face", video_path,
                    "--audio", audio_path,
                    "--outfile", output_path,
                    "--nosmooth"
                ]
                
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    save_job(job_id, {"status": "failed", "error": f"Wav2Lip greška: {res.stderr}"})
                    return
                    
                if not os.path.exists(output_path):
                    save_job(job_id, {"status": "failed", "error": "Izlazni video nije generisan."})
                    return
                    
                # GFPGAN restauracija lica ako je omogućeno
                enhance_face = data.get("enhance_face", True)
                if enhance_face:
                    enhanced_output = f"{temp_dir}/enhanced_output.mp4"
                    try:
                        enhance_video_faces(output_path, enhanced_output, self.gfpgan_checkpoint)
                        if os.path.exists(enhanced_output) and os.path.getsize(enhanced_output) > 0:
                            output_path = enhanced_output
                    except Exception as gfp_err:
                        print(f"[GFPGAN BG ERROR] Neuspešna restauracija lica: {gfp_err}")
                    
                result_upload_url = data.get("result_upload_url")
                if result_upload_url:
                    with open(output_path, "rb") as f:
                        resp = requests.put(result_upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=300)
                        resp.raise_for_status()
                    save_job(job_id, {
                        "status": "completed",
                        "result": {
                            "status": "success",
                            "uploaded": True
                        }
                    })
                else:
                    with open(output_path, "rb") as f:
                        output_b64 = base64.b64encode(f.read()).decode('utf-8')
                        
                    save_job(job_id, {
                        "status": "completed",
                        "result": {
                            "status": "success",
                            "video_base64": output_b64
                        }
                    })
            except Exception as e:
                save_job(job_id, {"status": "failed", "error": str(e)})
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        @web_app.post("/submit")
        async def submit(request: Request, background_tasks: BackgroundTasks):
            expected_key = os.environ.get("MODAL_API_KEY")
            if expected_key:
                api_key = request.headers.get("X-API-Key")
                if api_key != expected_key:
                    return JSONResponse(status_code=403, content={"error": "Neovlašćen pristup"})
            
            data = await request.json()
            job_id = str(uuid.uuid4())
            save_job(job_id, {"status": "running"})
            background_tasks.add_task(run_inference_bg, job_id, data)
            return {"job_id": job_id}

        @web_app.get("/status/{job_id}")
        async def status(job_id: str):
            job = get_job(job_id)
            if not job:
                return JSONResponse(status_code=404, content={"error": "Job not found"})
            return job

        # Sinhroni fallback endpoint na korenskoj ruti (/)
        @web_app.post("/")
        async def sync_endpoint(request: Request):
            expected_key = os.environ.get("MODAL_API_KEY")
            if expected_key:
                api_key = request.headers.get("X-API-Key")
                if api_key != expected_key:
                    return JSONResponse(status_code=403, content={"error": "Neovlašćen pristup"})
            
            data = await request.json()
            job_id = str(uuid.uuid4())
            
            temp_dir = f"/tmp/{job_id}"
            os.makedirs(temp_dir, exist_ok=True)
            
            video_url = data.get("video_url")
            audio_url = data.get("audio_url")
            video_base64 = data.get("video_base64")
            audio_base64 = data.get("audio_base64")
            
            video_path = f"{temp_dir}/input_video.mp4"
            audio_path = f"{temp_dir}/input_audio.wav"
            output_path = f"{temp_dir}/output.mp4"
            
            try:
                if video_url:
                    resp = requests.get(video_url, timeout=300)
                    resp.raise_for_status()
                    with open(video_path, "wb") as f:
                        f.write(resp.content)
                else:
                    with open(video_path, "wb") as f:
                        f.write(base64.b64decode(video_base64))
                        
                if audio_url:
                    resp = requests.get(audio_url, timeout=300)
                    resp.raise_for_status()
                    with open(audio_path, "wb") as f:
                        f.write(resp.content)
                else:
                    with open(audio_path, "wb") as f:
                        f.write(base64.b64decode(audio_base64))
                        
                cmd = [
                    "python", f"{self.wav2lip_dir}/inference.py",
                    "--checkpoint_path", self.gan_checkpoint,
                    "--face", video_path,
                    "--audio", audio_path,
                    "--outfile", output_path,
                    "--nosmooth"
                ]
                
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    return {"error": f"Wav2Lip greška: {res.stderr}"}
                    
                if not os.path.exists(output_path):
                    return {"error": "Izlazni video nije generisan."}
                    
                # GFPGAN restauracija lica ako je omogućeno
                enhance_face = data.get("enhance_face", True)
                if enhance_face:
                    enhanced_output = f"{temp_dir}/enhanced_output.mp4"
                    try:
                        enhance_video_faces(output_path, enhanced_output, self.gfpgan_checkpoint)
                        if os.path.exists(enhanced_output) and os.path.getsize(enhanced_output) > 0:
                            output_path = enhanced_output
                    except Exception as gfp_err:
                        print(f"[GFPGAN SYNC ERROR] Neuspešna restauracija lica: {gfp_err}")
                    
                result_upload_url = data.get("result_upload_url")
                if result_upload_url:
                    with open(output_path, "rb") as f:
                        resp = requests.put(result_upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=300)
                        resp.raise_for_status()
                    return {
                        "status": "success",
                        "uploaded": True
                    }
                else:
                    with open(output_path, "rb") as f:
                        output_b64 = base64.b64encode(f.read()).decode('utf-8')
                        
                    return {
                        "status": "success",
                        "video_base64": output_b64
                    }
            except Exception as e:
                return {"error": str(e)}
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        return web_app
