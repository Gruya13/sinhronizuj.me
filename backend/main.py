import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from celery.result import AsyncResult
from backend.worker.celery_app import celery_app
from backend.core.config import settings
from botocore.config import Config

app = FastAPI(title="Sinhronizuj.me API", description="API za inteligentnu sinhronizaciju videa", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.TEMP_WORKSPACE, exist_ok=True)
app.mount("/videos", StaticFiles(directory=settings.TEMP_WORKSPACE), name="videos")

class VideoRequest(BaseModel):
    url: str
    debug: bool = False

@app.get("/")
def read_root():
    return {"message": "Sinhronizuj.me API je aktivan!"}

@app.get("/api/v1/storage/upload_url")
def get_upload_url(filename: str, content_type: str = 'video/mp4'):
    # 1. Interni klijent za proveru bucket-a (brze unutar Docker mreze)
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # 2. Javni klijent ISKLJUCIVO za generisanje Presigned URL-a (ispravan potpis za klijenta)
    s3_public = boto3.client(
        's3',
        endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    try:
        try:
            s3_internal.head_bucket(Bucket=settings.MINIO_BUCKET)
        except:
            s3_internal.create_bucket(Bucket=settings.MINIO_BUCKET)
            
        url = s3_public.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': settings.MINIO_BUCKET, 
                'Key': filename,
                'ContentType': content_type
            },
            ExpiresIn=3600
        )
        
        print(f"--- DEBUG: GENERISAN JAVNI URL: {url}", flush=True)
            
        return {
            "upload_url": url, 
            "file_key": filename,
            "s3_url": f"s3://{settings.MINIO_BUCKET}/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/process-video")
def process_video(request: VideoRequest):
    print(f"--- [API RECEIVE] Primljen zahtev: url={request.url}, debug={request.debug}", flush=True)
    from backend.worker.tasks import process_video_task
    # Koristimo striktno pozicione argumente
    task = process_video_task.delay(request.url, request.debug)
    return {
        "status": "success",
        "message": "Zadatak za sinhronizaciju je predat radniku.",
        "task_id": task.id
    }

class EditedSegmentsRequest(BaseModel):
    segments: list

class MixerSettingsRequest(BaseModel):
    background_volume: float
    dubbed_volume: float

@app.post("/api/v1/continue/{task_id}")
def continue_task(task_id: str):
    """
    Signalizira Celery zadatku da nastavi sa sledećim korakom u debugging modu.
    """
    import redis
    import re
    match = re.search(r'@([^:/]+)', settings.REDIS_URL)
    redis_host = match.group(1) if match else "redis"
    
    r = redis.Redis(host=redis_host, password=settings.REDIS_PASSWORD, port=6379, db=0)
    r.set(f"task:{task_id}:continue", "true", ex=3600)
    return {"status": "success", "message": "Signal za nastavak poslat."}

@app.post("/api/v1/edit-segments/{task_id}")
def edit_segments(task_id: str, request: EditedSegmentsRequest):
    import redis
    import json
    import re
    match = re.search(r'@([^:/]+)', settings.REDIS_URL)
    redis_host = match.group(1) if match else "redis"
    
    r = redis.Redis(host=redis_host, password=settings.REDIS_PASSWORD, port=6379, db=0)
    r.set(f"task:{task_id}:edited_segments", json.dumps(request.segments), ex=3600)
    return {"status": "success", "message": "Segmenti uspešno sačuvani."}

@app.post("/api/v1/mixer-settings/{task_id}")
def save_mixer_settings(task_id: str, request: MixerSettingsRequest):
    import redis
    import json
    import re
    match = re.search(r'@([^:/]+)', settings.REDIS_URL)
    redis_host = match.group(1) if match else "redis"
    
    r = redis.Redis(host=redis_host, password=settings.REDIS_PASSWORD, port=6379, db=0)
    r.set(f"task:{task_id}:mixer_settings", json.dumps({
        "background_volume": request.background_volume,
        "dubbed_volume": request.dubbed_volume
    }), ex=3600)
    return {"status": "success", "message": "Podešavanja miksera sačuvana."}

@app.get("/api/v1/status/{task_id}")
def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }
    if task_result.status == "PROGRESS":
        response["progress_data"] = task_result.info
    if task_result.status == "SUCCESS":
        result = task_result.result
        if result and isinstance(result, dict) and result.get("status") == "error":
            response["status"] = "FAILURE"
            response["error"] = result.get("message")
        elif result and isinstance(result, dict) and "final_video_path" in result:
            video_filename = os.path.basename(result["final_video_path"])
            response["video_url"] = f"/videos/{video_filename}"
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.info)
    return response

@app.get("/api/v1/modal-status")
def get_modal_global_status():
    """
    Vraća status Modal serverless radnika.
    Budući da je Modal serverless, uvek je 'Spreman'.
    """
    return {
        "status": "Spreman",
        "active_workers": "Auto-Scale",
        "platform": "Modal.com",
        "timestamp": os.getpid()
    }

@app.get("/api/v1/hw-stats")
async def hw_stats():
    try:
        from backend.worker.hw_monitor import get_gpu_stats, get_system_stats
        sys_stats = get_system_stats()
        gpu_stats = get_gpu_stats()
        return {
            "status": "online",
            "cpu_usage": sys_stats.get("cpu_usage", 0),
            "memory": sys_stats.get("memory", {"percent": 0}),
            "gpus": gpu_stats
        }
    except Exception as e:
        print(f"HW Stats Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/v1/logs")
def get_worker_logs():
    # Dinamicka putanja: gleda u root projekta bez obzira na okruzenje
    log_path = os.path.join(os.path.dirname(__file__), "../worker.log")
    if not os.path.exists(log_path):
        return {"logs": "Log fajl još uvek nije generisan..."}
    try:
        # Uzimamo poslednjih 100 linija
        with open(log_path, "r") as f:
            lines = f.readlines()
            logs = "".join(lines[-100:])
        return {"logs": logs}
    except Exception as e:
        return {"error": str(e)}
