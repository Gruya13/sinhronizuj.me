import subprocess
import os
import uuid
from backend.core.config import settings

def extract_visual_context(video_path: str, interval: int = 4, workspace_path: str = None) -> str:
    """
    Ekstrahuje frejmove iz videa i pravi lagani preview klip (bez zvuka).
    Pomaže LLM-u da vidi kontekst bez gušenja mreže.
    """
    output_filename = f"preview_{uuid.uuid4().hex}.mp4"
    workspace = workspace_path or settings.TEMP_WORKSPACE
    output_path = os.path.join(workspace, output_filename)
    
    # FFMPEG komanda: 
    # - 1 frejm na svakih 'interval' sekundi
    # - Skaliranje na 320px širine (očuvanje AR)
    # - Izbacivanje zvuka
    # - H264 kompresija sa visokim CRF (lošiji kvalitet, manji fajl)
    
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"fps=1/{interval},scale=320:-2",
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

import boto3
from botocore.config import Config

def upload_to_minio(file_path: str, bucket_name: str = "previews") -> str:
    """
    Uploaduje fajl na MinIO i vraća presigned URL koji je validan 24h.
    Ovo omogućava RunPod-u da pristupi fajlu bez javnog bucket-a.
    """
    if not os.path.exists(file_path):
        print(f"[ERROR] Fajl za upload ne postoji: {file_path}")
        return ""

    filename = os.path.basename(file_path)
    
    # 1. Interni klijent za brzi upload unutar Docker mreze
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        region_name=settings.S3_REGION
    )
    
    # 2. Javni klijent za generisanje URL-a koji RunPod moze da vidi
    s3_public = boto3.client(
        's3',
        endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        region_name=settings.S3_REGION
    )
    
    try:
        # Kofa previews već postoji na S3 serveru, prelazimo direktno na upload.

        # Upload preko internog klijenta (brze je)
        print(f"[MINIO] Uploadujem {filename} u {bucket_name}...")
        s3_internal.upload_file(file_path, bucket_name, filename)
        
        # Generisi presigned URL preko JAVNOG klijenta (validan 24h)
        url = s3_public.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket_name, 'Key': filename},
            ExpiresIn=86400
        )
        
        print(f"[MINIO] Generisan JAVNI URL za RunPod: {url}")
        return url
    except Exception as e:
        print(f"[ERROR] MinIO Upload Error: {str(e)}")
        return ""
