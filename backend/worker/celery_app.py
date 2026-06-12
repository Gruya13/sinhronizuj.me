import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from backend.core.config import settings

# Zadatak 1: Eksplicitno učitavanje .env fajla za worker procese
load_dotenv()

import sentry_sdk

# Inicijalizacija Sentry monitoringa za Celery (Sentry 2.x automatski integriše Celery)
if getattr(settings, "SENTRY_DSN", None):
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
    )
    print("[SENTRY INIT] Sentry monitoring je uspešno inicijalizovan za Celery.", flush=True)

celery_app = Celery(
    "sinhronizuj_me_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["backend.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Belgrade",
    enable_utc=True,
    task_routes={
        "analyze_video_task": {"queue": "analyze_queue"},
        "render_video_task": {"queue": "render_queue"},
        "process_video_task": {"queue": "render_queue"},
        "backend.worker.tasks.cleanup_old_files": {"queue": "default_queue"},
    },
)

# Zadatak 3: Celery Beat konfiguracija za čišćenje SSD-a (svake noći u 03:00)
celery_app.conf.beat_schedule = {
    "cleanup-old-files-nightly": {
        "task": "backend.worker.tasks.cleanup_old_files",
        "schedule": crontab(hour=3, minute=0),
    },
}

