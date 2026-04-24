import subprocess
import os
import uuid
from backend.core.config import settings

def extract_visual_context(video_path: str, interval: int = 4) -> str:
    """
    Ekstrahuje frejmove iz videa i pravi lagani preview klip (bez zvuka).
    Pomaže LLM-u da vidi kontekst bez gušenja mreže.
    """
    output_filename = f"preview_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(settings.TEMP_WORKSPACE, output_filename)
    
    # FFMPEG komanda: 
    # - 1 frejm na svakih 'interval' sekundi
    # - Skaliranje na 320px širine (očuvanje AR)
    # - Izbacivanje zvuka
    # - H264 kompresija sa visokim CRF (lošiji kvalitet, manji fajl)
    
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"fps=1/{interval},scale=320:-1",
        "-an", # bez audija
        "-c:v", "libx264", "-crf", "30", "-preset", "veryfast",
        output_path
    ]
    
    try:
        print(f"[PREPROCESSOR] Generišem vizuelni kontekst: {output_path}")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFMPEG greška pri generisanju preview-a: {e.stderr.decode()}")
        return None

def upload_to_minio(file_path: str, bucket_name: str = "previews") -> str:
    """
    Uploaduje fajl na MinIO i vraća URL (trenutno vraćamo lokalni put ili placeholder 
    dok ne konfigurišemo MinIO klijent).
    """
    # Za sada simuliramo MinIO URL
    # TODO: Implementirati boto3 upload i presigned URL
    filename = os.path.basename(file_path)
    return f"http://{settings.MINIO_ENDPOINT}/{bucket_name}/{filename}"
