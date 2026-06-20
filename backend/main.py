import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from backend.core.config import settings
from backend.core.limiter import limiter
# Eksponiranje za kompatibilnost sa testovima
from backend.services.redis import get_redis_client
from backend.services.s3 import get_presigned_download_url

import sentry_sdk

# Inicijalizacija Sentry monitoringa
if getattr(settings, "SENTRY_DSN", None):
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    print("[SENTRY INIT] Sentry monitoring je uspešno inicijalizovan za FastAPI.", flush=True)

app = FastAPI(title="Sinhronizuj.me API", description="API za inteligentnu sinhronizaciju videa", version="2.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.TEMP_WORKSPACE, exist_ok=True)
app.mount("/videos", StaticFiles(directory=settings.TEMP_WORKSPACE), name="videos")

# Uvozimo ruter pod-module
from backend.routes.auth import router as auth_router
from backend.routes.projects import router as projects_router
from backend.routes.segments import router as segments_router
from backend.routes.admin import router as admin_router
from backend.routes.system import router as system_router

# Registrujemo rute
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(segments_router)
app.include_router(admin_router)
app.include_router(system_router)

@app.get("/")
def read_root():
    return {"message": "Sinhronizuj.me API je aktivan i ažuriran na v2.0 (Dvofazni, PostgreSQL, JWT)!"}
