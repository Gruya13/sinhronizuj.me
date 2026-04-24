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

@app.get("/")
def read_root():
    return {"message": "Sinhronizuj.me API je aktivan!"}

@app.get("/api/v1/storage/upload_url")
def get_upload_url(filename: str, content_type: str = 'video/mp4'):
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    try:
        try:
            s3.head_bucket(Bucket=settings.MINIO_BUCKET)
        except:
            s3.create_bucket(Bucket=settings.MINIO_BUCKET)
            
        url = s3.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': settings.MINIO_BUCKET, 
                'Key': filename,
                'ContentType': content_type
            },
            ExpiresIn=3600
        )
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

@app.get("/api/v1/hw-stats")
def get_hw_stats():
    from backend.worker.hw_monitor import get_gpu_stats, get_system_stats
    return {
        "gpu": get_gpu_stats(),
        "system": get_system_stats()
    }

@app.get("/api/v1/logs")
def get_worker_logs():
    log_path = "/app/worker.log"
    if not os.path.exists(log_path):
        return {"logs": "Log fajl još uvek nije generisan..."}
    try:
        with os.popen(f"tail -n 100 {log_path}") as f:
            logs = f.read()
        return {"logs": logs}
    except Exception as e:
        return {"error": str(e)}
