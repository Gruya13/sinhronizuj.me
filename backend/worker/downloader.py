import os
import yt_dlp
import uuid
from backend.core.config import settings

import subprocess

def download_youtube_video(url: str) -> dict:
    """
    HAKOVANA VERZIJA ZA LOKALNI TEST:
    Preskace YouTube i koristi 'videoplayback.mp4' iz rut direktorijuma.
    """
    if not os.path.exists(settings.TEMP_WORKSPACE):
        os.makedirs(settings.TEMP_WORKSPACE)

    try:
        video_path = "/root/daca_dub/videoplayback.mp4"
        audio_path = os.path.join(settings.TEMP_WORKSPACE, "test_audio.wav")
        
        # Ekstrahujemo audio pomocu ffmpeg-a (ovo bi inace radio yt-dlp)
        print("[FAZA 1] Hakovan downloader: Koristim lokalni fajl i vadim audio...")
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path, 
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", 
            audio_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return {
            "status": "success",
            "video_path": video_path,
            "audio_path": audio_path,
            "title": "Manuelni Lokalni Test"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Greška pri manuelnom ucitavanju: {str(e)}"
        }
