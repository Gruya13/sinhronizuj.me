import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from backend.core.config import settings

# Zadatak 1: Eksplicitno učitavanje .env fajla za worker procese
load_dotenv()

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
)

# Zadatak 3: Celery Beat konfiguracija za čišćenje SSD-a (svake noći u 03:00)
celery_app.conf.beat_schedule = {
    "cleanup-old-files-nightly": {
        "task": "backend.worker.tasks.cleanup_old_files",
        "schedule": crontab(hour=3, minute=0),
    },
}

