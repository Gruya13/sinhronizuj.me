from backend.worker.celery_app import celery_app
from backend.worker.downloader import download_youtube_video

@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, video_url: str):
    """
    Korenski Celery zadatak koji vodi Fazu 1 (yt-dlp preuzimanje).
    """
    print(f"[FAZA 1] Pocinjem preuzimanje za URL: {video_url}")
    
    result = download_youtube_video(video_url)
    
    if result["status"] == "error":
        print(f"[GREŠKA] Preuzimanje nije uspelo: {result['message']}")
        return result
        
    print(f"[FAZA 1 ZAVRŠENA] Video preuzet: {result['video_path']}")
    print(f"[FAZA 1 ZAVRŠENA] Audio ekstrahovan: {result['audio_path']}")
    
    # --- FAZA 2: Separacija Zvuka (Demucs) ---
    print("[FAZA 2] Započinjem izolaciju vokala...")
    from backend.worker.audio_sep import separate_audio
    sep_result = separate_audio(result['audio_path'])
    
    if sep_result["status"] == "error":
        print(f"[GREŠKA] Separacija zvuka nije uspela: {sep_result['message']}")
        return sep_result
        
    print(f"[FAZA 2 ZAVRŠENA] Čist vokal sacuvan na: {sep_result['vocals_path']}")
    print(f"[FAZA 2 ZAVRŠENA] Pozadina sacuvana na: {sep_result['no_vocals_path']}")
    
    # Sutra ovde dodajemo Fazu 3 (Whisper)
    
    return {
        "status": "completed", 
        "url": video_url,
        "video_path": result["video_path"],
        "audio_path": result["audio_path"],
        "vocals_path": sep_result["vocals_path"],
        "background_path": sep_result["no_vocals_path"]
    }
