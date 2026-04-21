import os
import yt_dlp
import uuid
from backend.core.config import settings

def download_youtube_video(url: str) -> dict:
    """
    Preuzima YouTube video u HD rezoluciji (do 1080p) i ekstrahuje .wav audio fajl.
    Vraća putanje do preuzetog videa i audio fajla.
    """
    if not os.path.exists(settings.TEMP_WORKSPACE):
        os.makedirs(settings.TEMP_WORKSPACE)

    # Generisemo jedinstveni ID za ovaj video proces kako se fajlovi ne bi prepisivali
    task_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(settings.TEMP_WORKSPACE, f"{task_id}_%(title)s.%(ext)s")
    
    ydl_opts = {
        # Skidamo najbolji MP4 video do 1080p + najbolji audio, ili najbolji mp4 u celini
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'keepvideo': True, # Cuvamo originalni .mp4 fajl (ne zelimo da ga obrise nakon ekstrakcije zvuka)
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Prepare_filename vraca originalno ime sa video ekstenzijom
            base_filename = ydl.prepare_filename(info)
            
            # Postprocesor pravi .wav fajl sa istim imenom osnove
            audio_path = os.path.splitext(base_filename)[0] + ".wav"
            video_path = base_filename
            
            # Zastita u slucaju da yt-dlp promeni ekstenziju zbog spajanja
            if not os.path.exists(video_path):
                video_path = os.path.splitext(base_filename)[0] + ".mkv"
                
            return {
                "status": "success",
                "video_path": video_path,
                "audio_path": audio_path,
                "title": info.get('title', 'Nepoznat Naslov')
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
