from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import os
import uuid
import subprocess

app = FastAPI(title="Wav2Lip Serverless API")

TEMP_DIR = "/app/temp_sync"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/sync")
async def sync_video(video: UploadFile = File(...), audio: UploadFile = File(...)):
    """
    Endpoint koji prima video i audio fajlove i vraća sinhronizovan video.
    """
    job_id = str(uuid.uuid4())
    video_path = os.path.join(TEMP_DIR, f"{job_id}_input_video.mp4")
    audio_path = os.path.join(TEMP_DIR, f"{job_id}_input_audio.wav")
    output_path = os.path.join(TEMP_DIR, f"{job_id}_output.mp4")

    # Čuvanje uploadovanih fajlova
    with open(video_path, "wb") as f:
        f.write(await video.read())
    with open(audio_path, "wb") as f:
        f.write(await audio.read())

    # Putanja do Wav2Lip koda unutar kontejnera
    wav2lip_dir = "/app/Wav2Lip"
    
    cmd = [
        "python", os.path.join(wav2lip_dir, "inference.py"),
        "--checkpoint_path", os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth"),
        "--face", video_path,
        "--audio", audio_path,
        "--outfile", output_path,
        "--nosmooth" # Opciono, zavisi od preferencija
    ]

    try:
        # Pokretanje inference procesa
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Vraćanje rezultujućeg videa
        return FileResponse(output_path, media_type="video/mp4", filename="synced_video.mp4")
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Wav2Lip greška: {e.stderr.decode()}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        # Cleanup ulaznih fajlova (opciono, može i periodično)
        # os.remove(video_path)
        # os.remove(audio_path)
        pass
