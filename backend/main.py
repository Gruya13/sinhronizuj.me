from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# Serviranje frontenda direktno iz dist foldera
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist"))
if os.path.exists(frontend_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {"message": "Daca Dub API je aktivan, ali frontend nije pronadjen!"}

class VideoRequest(BaseModel):
    url: str

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
