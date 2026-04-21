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
    
    # Sutra ovde dodajemo poziv za Fazu 2 (Demucs separacija) prosledjivanjem audio_path
    
    return {
        "status": "completed", 
        "url": video_url,
        "video_path": result["video_path"],
        "audio_path": result["audio_path"]
    }
