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

# ─── GLOBALNI MONKEY-PATCH: json.JSONEncoder.default ───
# Ovo hvata SVE json.dumps() pozive u celom procesu (Celery, Redis, fajlovi, itd.)
# i automatski konvertuje numpy tipove (float64, int64, bool_, ndarray) u Python native.
# Bez ovoga, bilo koji ML modul (sentence-transformers, CrossEncoder, numpy) može da
# vrati numpy tip koji standardni json encoder ne prepoznaje.
import json as _json
_original_encoder_default = _json.JSONEncoder.default

def _numpy_safe_default(self, obj):
    try:
        import numpy as np
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    return _original_encoder_default(self, obj)

_json.JSONEncoder.default = _numpy_safe_default
print("[JSON PATCH] json.JSONEncoder.default monkey-patched za numpy tipove.", flush=True)
# ─── KRAJ MONKEY-PATCH-A ───

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

# Zadatak 3: Celery Beat konfiguracija
celery_app.conf.beat_schedule = {
    "cleanup-old-files-nightly": {
        "task": "backend.worker.tasks.cleanup_old_files",
        "schedule": crontab(hour=3, minute=0),
    },
    "promote-pending-tm-every-4-hours": {
        "task": "promote_pending_tm_task",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "nightly-pattern-analysis": {
        "task": "run_nightly_pattern_analysis_task",
        "schedule": crontab(hour=2, minute=0),
    },
    "deploy-lora-weekly": {
        "task": "deploy_lora_task",
        "schedule": crontab(day_of_week=0, hour=0, minute=0),
    },
}

