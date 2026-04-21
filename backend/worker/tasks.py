from backend.worker.celery_app import celery_app
import time

@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, video_url: str):
    """
    Korenski Celery zadatak koji oponasa Fazu 1 (yt-dlp preuzimanje).
    """
    print(f"Pocinjem preuzimanje za URL: {video_url}")
    # Simulacija rada
    time.sleep(5)
    print("Preuzimanje zavrseno!")
    return {"status": "completed", "url": video_url}
