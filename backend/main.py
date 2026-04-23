from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from celery.result import AsyncResult
from backend.worker.celery_app import celery_app
from backend.worker.tasks import process_video_task
from backend.core.config import settings

app = FastAPI(title="Daca Dub API", description="API za inteligentnu sinhronizaciju videa", version="1.0.0")

# CORS podešavanja za komunikaciju sa React frontendom
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kreiranje foldera ukoliko ne postoji i serviranje finalnih videa korisnicima
os.makedirs(settings.TEMP_WORKSPACE, exist_ok=True)
app.mount("/videos", StaticFiles(directory=settings.TEMP_WORKSPACE), name="videos")

class VideoRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    return {"message": "Daca Dub API je aktivan!"}

@app.post("/api/v1/process-video")
def process_video(request: VideoRequest):
    # Okidamo Celery task u pozadini i vracamo task_id na frontend
    task = process_video_task.delay(request.url)
    return {
        "status": "success",
        "message": "Zadatak za sinhronizaciju je predat radniku.",
        "task_id": task.id
    }

@app.get("/api/v1/status/{task_id}")
def get_task_status(task_id: str):
    # Frontend ce na svakih par sekundi pitati ovaj endpoint da li je gotovo
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }
    
    # Dodajemo meta-podatke o progresu ako postoje
    if task_result.status == "PROGRESS":
        response["progress_data"] = task_result.info
    
    if task_result.status == "SUCCESS":
        result = task_result.result
        if result.get("status") == "error":
            response["status"] = "FAILURE"
            response["error"] = result.get("message")
        else:
            # Izvlačimo samo ime fajla kako bismo kreirali validan link za frontend reprodukciju
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

@app.post("/api/v1/runpod/stop")
def stop_runpod():
    import requests
    if not settings.RUNPOD_API_KEY or not settings.RUNPOD_POD_ID:
        raise HTTPException(status_code=400, detail="RunPod API ključ ili Pod ID nisu konfigurisani.")
    
    query = """
    mutation {
      podStop(input: {podId: "%s"}) {
        id
        desiredStatus
      }
    }
    """ % settings.RUNPOD_POD_ID
    
    url = f"https://api.runpod.io/graphql?api_key={settings.RUNPOD_API_KEY}"
    try:
        res = requests.post(url, json={'query': query})
        return res.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/orchestrator/find-best-pod")
def find_best_pod(gpu_type: str = "NVIDIA GeForce RTX 3090"):
    from backend.core.orchestrator import RunPodOrchestrator
    orchestrator = RunPodOrchestrator()
    best_pod_info = orchestrator.find_best_pod(gpu_type)
    return best_pod_info

@app.get("/api/v1/logs")
def get_worker_logs():
    import os
    log_path = "/app/worker.log"
    if not os.path.exists(log_path):
        return {"logs": "Log fajl još uvek nije generisan..."}
    try:
        # Čitamo poslednjih 100 linija
        with os.popen(f"tail -n 100 {log_path}") as f:
            logs = f.read()
        return {"logs": logs}
    except Exception as e:
        return {"error": str(e)}
