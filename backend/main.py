from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

app = FastAPI(title="Daca Dub API", description="API za inteligentnu sinhronizaciju videa", version="1.0.0")

class VideoRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    return {"message": "Daca Dub API je aktivan!"}

@app.post("/api/v1/process-video")
def process_video(request: VideoRequest):
    # Ovde cemo sutra proslediti url Celery radniku za Fazu 1 (yt-dlp)
    # npr: task = process_video_task.delay(request.url)
    return {
        "status": "success",
        "message": f"Zadatak za preuzimanje videa je primljen. URL: {request.url}",
        "task_id": "dummy_task_id_za_sada"
    }
