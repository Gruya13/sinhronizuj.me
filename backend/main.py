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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://178.104.214.78:8000",
        "http://178.104.214.78",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.TEMP_WORKSPACE, exist_ok=True)
app.mount("/videos", StaticFiles(directory=settings.TEMP_WORKSPACE), name="videos")

class VideoRequest(BaseModel):
    url: str

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
    from backend.worker.tasks import process_video_task
    task = process_video_task.delay(request.url)
    return {
        "status": "success",
        "message": "Zadatak za sinhronizaciju je predat radniku.",
        "task_id": task.id
    }

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
        if result.get("status") == "error":
            response["status"] = "FAILURE"
            response["error"] = result.get("message")
        else:
            video_filename = os.path.basename(result["final_video_path"])
            response["video_url"] = f"/videos/{video_filename}"
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.info)
    return response

@app.get("/api/v1/runpod-status")
def get_runpod_global_status():
    """
    Proverava broj aktivnih radnika na RunPod-u.
    Ne budi instancu, samo čita metriku.
    """
    endpoints = {
        "Whisper": settings.RUNPOD_WHISPER_ID,
        "Translator": settings.RUNPOD_TRANSLATOR_ID,
        "TTS": settings.RUNPOD_TTS_ID
    }
    
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    overall_status = "Asleep"
    active_count = 0
    
    try:
        # Proveravamo samo Translator kao reprezentativni endpoint (ili sve ako želimo preciznost)
        # Za sada ćemo proveriti sve i ako bilo koji ima > 0 radnika, sistem je "Budan"
        for name, eid in endpoints.items():
            if not eid: continue
            
            # RunPod health endpoint
            health_url = f"https://api.runpod.ai/v2/{eid}/health"
            res = requests.get(health_url, headers=headers, timeout=5)
            if res.ok:
                data = res.json()
                workers = data.get("workerCount", 0)
                if workers > 0:
                    active_count += workers
                    overall_status = "Active"
        
        return {
            "status": overall_status,
            "active_workers": active_count,
            "timestamp": os.getpid() # placeholder za cache busting
        }
    except Exception as e:
        return {"status": "Unknown", "error": str(e)}

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
