import os
import yt_dlp
import uuid
import boto3
import subprocess
import socket
from urllib.parse import urlparse
from backend.core.config import settings

def is_safe_url(url: str) -> bool:
    """
    Proverava da li je URL bezbedan i sprečava SSRF napade ka lokalnoj mreži.
    """
    try:
        parsed_url = urlparse(url)
        # S3 interna šema je dozvoljena u našem sistemu
        if parsed_url.scheme == "s3":
            return True
            
        if parsed_url.scheme not in ["http", "https"]:
            return False
            
        hostname = parsed_url.hostname
        if not hostname:
            return False
            
        # Rezolucija IP adrese
        ip = socket.gethostbyname(hostname)
        
        # Provera privatnih i loopback opsega (RFC 1918 i localhost)
        ip_parts = list(map(int, ip.split('.')))
        if (
            ip_parts[0] == 127 or                  # Loopback
            ip_parts[0] == 10 or                   # Klasa A
            (ip_parts[0] == 172 and 16 <= ip_parts[1] <= 31) or # Klasa B
            (ip_parts[0] == 192 and ip_parts[1] == 168) or      # Klasa C
            ip == "0.0.0.0"
        ):
            print(f"[SSRF BLOCKED] Odbijen pristup privatnom mrežnom opsegu: {ip} za URL: {url}")
            return False
            
        return True
    except Exception as e:
        print(f"[SSRF ERROR] Greška pri validaciji URL-a: {e}")
        return False

def download_video(url: str) -> dict:
    """
    Glavna funkcija za dobavljanje videa. Podržava YouTube i S3.
    """
    if not is_safe_url(url):
        return {"status": "error", "message": "Zabranjen ili neispravan URL (SSRF zaštita)."}

    if not os.path.exists(settings.TEMP_WORKSPACE):
        os.makedirs(settings.TEMP_WORKSPACE)


    if url.startswith("s3://"):
        return _download_from_s3(url)
    else:
        return _download_from_youtube(url)

def _download_from_s3(s3_url: str) -> dict:
    """
    Preuzima fajl direktno sa našeg MinIO storage-a.
    Format: s3://bucket_name/filename
    """
    try:
        parts = s3_url.replace("s3://", "").split("/")
        bucket = parts[0]
        key = "/".join(parts[1:])
        
        local_video_path = os.path.join(settings.TEMP_WORKSPACE, key)
        local_audio_path = local_video_path.rsplit(".", 1)[0] + ".wav"
        
        s3 = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY
        )
        
        print(f"[FAZA 1] Preuzimam sa S3: {s3_url} -> {local_video_path}")
        s3.download_file(bucket, key, local_video_path)
        
        # Ekstrakcija audija
        subprocess.run([
            "ffmpeg", "-y", "-i", local_video_path, 
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", 
            local_audio_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return {
            "status": "success",
            "video_path": local_video_path,
            "audio_path": local_audio_path,
            "title": key
        }
    except Exception as e:
        return {"status": "error", "message": f"S3 Download Error: {str(e)}"}

def _download_from_youtube(url: str) -> dict:
    """
    Standardni YouTube download koristeći yt-dlp.
    """
    video_id = uuid.uuid4().hex[:8]
    output_template = os.path.join(settings.TEMP_WORKSPACE, f"{video_id}.%(ext)s")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'keepvideo': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            audio_path = video_path.rsplit(".", 1)[0] + ".wav"
            
            return {
                "status": "success",
                "video_path": video_path,
                "audio_path": audio_path,
                "title": info.get('title', 'YouTube Video'),
                "description": info.get('description', ''),
                "tags": info.get('tags', [])
            }
    except Exception as e:
        return {"status": "error", "message": f"YouTube Download Error: {str(e)}"}
