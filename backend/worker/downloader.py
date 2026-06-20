import os
import yt_dlp
import uuid
import boto3
import subprocess
import socket
from urllib.parse import urlparse
from backend.core.config import settings

import ipaddress

def resolve_and_check_ip(hostname: str) -> bool:
    """
    Razrešava hostname i proverava da li su sve IP adrese (IPv4 i IPv6) bezbedne.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in infos:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private or 
                ip.is_loopback or 
                ip.is_link_local or 
                ip.is_multicast or 
                ip.is_reserved or
                ip.is_unspecified
            ):
                return False
        return True
    except Exception:
        return False

def is_safe_url(url: str) -> bool:
    """
    Proverava da li je URL bezbedan i sprečava SSRF napade ka lokalnoj mreži,
    prateći redirekcije i proveravajući svaki hop.
    """
    try:
        parsed_url = urlparse(url)
        # S3 interna šema je dozvoljena u našem sistemu
        if parsed_url.scheme == "s3":
            return True
            
        if parsed_url.scheme not in ["http", "https"]:
            return False
            
        current_url = url
        import httpx
        from urllib.parse import urljoin
        
        # Pratimo redirekcije ručno da proverimo svaki hop (maksimalno 5 redirekcija)
        for _ in range(5):
            parsed = urlparse(current_url)
            hostname = parsed.hostname
            if not hostname:
                return False
                
            if not resolve_and_check_ip(hostname):
                print(f"[SSRF BLOCKED] Odbijen pristup nebezbednom mrežnom opsegu za URL: {current_url}")
                return False
                
            # HEAD zahtev bez automatskog praćenja redirekcija kako bismo sami kontrolisali sledeći hop
            with httpx.Client(verify=False) as client:
                response = client.head(current_url, follow_redirects=False, timeout=2.0)
                if response.is_redirect:
                    next_url = response.headers.get("Location")
                    if not next_url:
                        break
                    if not next_url.startswith("http"):
                        next_url = urljoin(current_url, next_url)
                    current_url = next_url
                else:
                    break
        return True
    except Exception as e:
        print(f"[SSRF ERROR] Greška pri validaciji URL-a: {e}")
        return False

def download_video(url: str, workspace_path: str = None) -> dict:
    """
    Glavna funkcija za dobavljanje videa. Podržava YouTube i S3.
    """
    if not is_safe_url(url):
        return {"status": "error", "message": "Zabranjen ili neispravan URL (SSRF zaštita)."}

    workspace = workspace_path or settings.TEMP_WORKSPACE
    if not os.path.exists(workspace):
        os.makedirs(workspace)

    if url.startswith("s3://"):
        return _download_from_s3(url, workspace)
    else:
        return _download_from_youtube(url, workspace)

def _download_from_s3(s3_url: str, workspace: str) -> dict:
    """
    Preuzima fajl direktno sa našeg MinIO storage-a.
    Format: s3://bucket_name/filename
    """
    try:
        parts = s3_url.replace("s3://", "").split("/")
        bucket = parts[0]
        key = "/".join(parts[1:])
        
        local_video_path = os.path.join(workspace, key)
        local_audio_path = local_video_path.rsplit(".", 1)[0] + ".wav"
        
        s3 = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name=settings.S3_REGION
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

def _download_from_youtube(url: str, workspace: str) -> dict:
    """
    Standardni YouTube download koristeći yt-dlp.
    """
    video_id = uuid.uuid4().hex[:8]
    output_template = os.path.join(workspace, f"{video_id}.%(ext)s")
    
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
