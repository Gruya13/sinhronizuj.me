import os
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from backend.core.database import get_db
from backend.core.models import User, Project
from backend.core.auth import get_current_user, get_current_admin_user
from backend.services.redis import get_redis_client
from backend.core.config import settings
from backend.worker.celery_app import celery_app

router = APIRouter(tags=["System"])

@router.get("/api/v1/status/{task_id}")
def get_task_status(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Vraća status Celery taska uz proveru vlasništva nad projektom.
    """
    r = get_redis_client()
    project_id = r.get(f"task:{task_id}:project_id")
    project_id_str = None
    if project_id:
        project_id_str = project_id.decode('utf-8')
        p = db.query(Project).filter(Project.id == project_id_str, Project.user_id == current_user.id).first()
        if not p:
            raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom statusu.")
            
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "project_id": project_id_str,
        "status": task_result.status,
    }
    if task_result.status == "PROGRESS":
        response["progress_data"] = task_result.info
        if isinstance(task_result.info, dict) and "costs" in task_result.info:
            response["costs"] = task_result.info["costs"]
    if task_result.status == "SUCCESS":
        result = task_result.result
        if result and isinstance(result, dict) and result.get("status") == "error":
            response["status"] = "FAILURE"
            response["error"] = result.get("message")
        elif result and isinstance(result, dict) and "final_video_path" in result:
            video_filename = os.path.basename(result["final_video_path"])
            response["video_url"] = f"/videos/{video_filename}"
            if "costs" in result:
                response["costs"] = result["costs"]
        elif result and isinstance(result, dict) and "video_url" in result:
            response["video_url"] = result["video_url"]
            if "costs" in result:
                response["costs"] = result["costs"]
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.info)
    return response

@router.post("/api/v1/warmup")
async def warmup_workers(current_user: User = Depends(get_current_admin_user)):
    import asyncio
    import httpx
    
    urls = [
        settings.MODAL_STT_URL,
        settings.MODAL_TRANSLATOR_URL,
        settings.MODAL_LEKTOR_URL,
        settings.MODAL_TTS_URL
    ]
    
    urls = [url for url in urls if url]
    if not urls:
        return {"status": "success", "message": "Nema konfigurisanih Modal URL-ova za zagrevanje."}
        
    print(f"[WARMUP] Započinjem zagrevanje za {len(urls)} Modal radnika: {urls}", flush=True)
    
    async def ping(url: str):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.get(url)
        except Exception:
            pass

    for url in urls:
        asyncio.create_task(ping(url))
        
    return {"status": "success", "message": "Zahtevi za zagrevanje su poslati."}

@router.get("/api/v1/modal-status")
def get_modal_global_status(current_user: User = Depends(get_current_admin_user)):
    return {
        "status": "Spreman",
        "active_workers": "Auto-Scale",
        "platform": "Modal.com",
        "timestamp": os.getpid()
    }

@router.get("/api/v1/hw-stats")
async def hw_stats(current_user: User = Depends(get_current_admin_user)):
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
        return {"status": "error", "message": str(e)}

@router.get("/api/v1/logs")
def get_worker_logs(current_user: User = Depends(get_current_admin_user)):
    log_path = os.path.join(os.path.dirname(__file__), "../../worker.log")
    if not os.path.exists(log_path):
        return {"logs": "Log fajl još uvek nije generisan..."}
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
            logs = "".join(lines[-100:])
        return {"logs": logs}
    except Exception as e:
        return {"error": str(e)}

@router.post("/api/v1/flush-redis")
def flush_redis(current_user: User = Depends(get_current_admin_user)):
    """
    Čisti Redis keš (samo neaktivne projekte stare preko 7 dana).
    """
    r = get_redis_client()
    all_projects = r.hgetall("projects:metadata")
    
    deleted_count = 0
    now = datetime.now()
    
    for pid_bytes, data_bytes in all_projects.items():
        try:
            pid = pid_bytes.decode('utf-8')
            meta = json.loads(data_bytes.decode('utf-8'))
            created_at_str = meta.get("created_at")
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str)
                if meta.get("status") == "empty" and (now - created_at) > timedelta(days=7):
                    r.delete(f"project:{pid}:draft")
                    r.hdel("projects:metadata", pid)
                    deleted_count += 1
        except Exception:
            pass
            
    return {"status": "success", "message": f"Čišćenje završeno. Obrisano {deleted_count} neaktivnih projekata."}
