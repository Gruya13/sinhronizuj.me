import os
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.models import User, Project, Segment, Waitlist
from backend.core.auth import get_current_admin_user
from backend.services.redis import get_redis_client
from backend.services.s3 import get_presigned_download_url
from backend.core.config import settings

router = APIRouter(tags=["Admin"])

@router.get("/api/v1/admin/stats")
def get_admin_stats(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """
    Vraća globalne statistike sistema za Dashboard administratora.
    """
    total_users = db.query(User).count()
    total_waitlist = db.query(Waitlist).count()
    waitlist_pending = db.query(Waitlist).filter(Waitlist.status == "pending").count()
    
    all_projects = db.query(Project).all()
    total_projects = len(all_projects)
    
    status_counts = {"empty": 0, "analyzing": 0, "ready": 0, "completed": 0, "failed": 0}
    for p in all_projects:
        status_counts[p.status] = status_counts.get(p.status, 0) + 1
        
    total_cost_usd = 0.0
    phase_costs = {
        "separation": 0.0,
        "transcription": 0.0,
        "translation": 0.0,
        "lektor": 0.0,
        "tts": 0.0,
        "lipsync": 0.0
    }
    
    for p in all_projects:
        costs_json = p.costs or {}
        total_cost_usd += costs_json.get("total_usd", 0.0)
        
        phases = costs_json.get("phases", {})
        for phase_id, phase_data in phases.items():
            if phase_id in phase_costs:
                phase_costs[phase_id] += phase_data.get("cost_usd", 0.0)
                
    total_cost_usd = round(total_cost_usd, 4)
    for k in phase_costs:
        phase_costs[k] = round(phase_costs[k], 4)
        
    return {
        "users": {
            "total": total_users,
            "waitlist_total": total_waitlist,
            "waitlist_pending": waitlist_pending
        },
        "projects": {
            "total": total_projects,
            "by_status": status_counts
        },
        "costs": {
            "total_usd": total_cost_usd,
            "by_phase": phase_costs
        }
    }

@router.get("/api/v1/admin/waitlist")
def get_admin_waitlist(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """
    Vraća listu svih prijava za zatvorenu betu.
    """
    entries = db.query(Waitlist).order_by(Waitlist.created_at.desc()).all()
    return [{
        "id": str(e.id),
        "email": e.email,
        "status": e.status,
        "created_at": e.created_at.isoformat()
    } for e in entries]

@router.post("/api/v1/admin/waitlist/{waitlist_id}/approve")
def approve_waitlist_entry(waitlist_id: str, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """
    Odobrava prijavu na listu čekanja.
    """
    entry = db.query(Waitlist).filter(Waitlist.id == waitlist_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Prijava nije pronađena.")
    
    entry.status = "approved"
    db.commit()
    return {"status": "success", "message": f"Prijava za {entry.email} je uspešno odobrena."}

@router.post("/api/v1/admin/waitlist/{waitlist_id}/reject")
def reject_waitlist_entry(waitlist_id: str, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """
    Odbija prijavu na listu čekanja.
    """
    entry = db.query(Waitlist).filter(Waitlist.id == waitlist_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Prijava nije pronađena.")
    
    entry.status = "rejected"
    db.commit()
    return {"status": "success", "message": f"Prijava za {entry.email} je odbijena."}

@router.get("/api/v1/admin/users")
def get_admin_users(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """
    Vraća listu svih registrovanih korisnika sa statistikom o projektima i troškovima.
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    response = []
    
    for u in users:
        projects = db.query(Project).filter(Project.user_id == u.id).all()
        proj_count = len(projects)
        user_costs = sum((p.costs or {}).get("total_usd", 0.0) for p in projects)
        
        response.append({
            "id": str(u.id),
            "email": u.email,
            "is_admin": getattr(u, "is_admin", False),
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "projects_count": proj_count,
            "total_costs_usd": round(user_costs, 4)
        })
    return response

@router.post("/api/v1/admin/users/{user_id}/toggle-admin")
def toggle_user_admin(user_id: str, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """
    Dodeljuje ili oduzima administratorske privilegije korisniku.
    """
    if str(current_user.id) == user_id:
        raise HTTPException(status_code=400, detail="Ne možete sami sebi ukinuti administratorski status.")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Korisnik nije pronađen.")
        
    user.is_admin = not getattr(user, "is_admin", False)
    db.commit()
    db.refresh(user)
    
    role_str = "administrator" if user.is_admin else "korisnik"
    return {"status": "success", "message": f"Korisniku {user.email} je uspešno dodeljena uloga: {role_str}."}

@router.get("/api/v1/admin/projects")
def get_admin_projects(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """
    Vraća listu svih projekata u sistemu.
    """
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    response = []
    
    for p in projects:
        owner = db.query(User).filter(User.id == p.user_id).first()
        response.append({
            "id": str(p.id),
            "name": p.name,
            "status": p.status,
            "video_title": p.video_title or "",
            "owner_email": owner.email if owner else "Nepoznat",
            "created_at": p.created_at.isoformat() if p.created_at else "",
            "total_cost_usd": round((p.costs or {}).get("total_usd", 0.0), 4)
        })
    return response

@router.get("/api/v1/admin/project/{project_id}")
def get_admin_project_detail(project_id: str, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """
    Vraća detaljan uvid u projekat (segmenti, S3 putanje, detaljni troškovi i logovi).
    """
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen.")
        
    owner = db.query(User).filter(User.id == p.user_id).first()
    db_segments = db.query(Segment).filter(Segment.project_id == project_id).order_by(Segment.segment_id).all()
    
    segments_list = []
    for s in db_segments:
        segments_list.append({
            "id": s.segment_id,
            "start": s.start,
            "end": s.end,
            "original": s.original,
            "translated": s.translated,
            "voice_type": s.voice_type,
            "volume": s.volume,
            "speed": s.speed,
            "pitch": s.pitch,
            "bg_volume": s.bg_volume,
            "tts_s3_key": s.tts_s3_key,
            "tts_duration": s.tts_duration,
            "status": s.status
        })
        
    project_logs = []
    log_path = os.path.join(os.path.dirname(__file__), "../../worker.log")
    
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
                recent_lines = lines[-2000:]
                for line in recent_lines:
                    if project_id in line or (p.status == "failed" and "ERROR" in line):
                        project_logs.append(line.strip())
        except Exception as e:
            project_logs.append(f"[ADMIN LOG PARSER ERROR] Greška pri čitanju worker.log: {e}")
            
    try:
        r = get_redis_client()
        draft_bytes = r.get(f"project:{project_id}:draft")
        if draft_bytes:
            draft_data = json.loads(draft_bytes)
            if "logs" in draft_data:
                project_logs.extend(draft_data["logs"])
    except:
        pass
        
    return {
        "id": str(p.id),
        "name": p.name,
        "owner_email": owner.email if owner else "Nepoznat",
        "status": p.status,
        "video_title": p.video_title or "",
        "video_url": get_presigned_download_url(settings.MINIO_BUCKET, p.video_s3_key) if p.video_s3_key else "",
        "vocals_url": get_presigned_download_url(settings.MINIO_BUCKET, p.vocals_s3_key) if p.vocals_s3_key else "",
        "no_vocals_url": get_presigned_download_url(settings.MINIO_BUCKET, p.no_vocals_s3_key) if p.no_vocals_s3_key else "",
        "final_video_url": get_presigned_download_url(settings.MINIO_BUCKET, p.final_video_s3_key) if p.final_video_s3_key else "",
        "costs": p.costs or {"phases": {}, "total_usd": 0.0},
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "segments": segments_list,
        "logs": project_logs[-100:]
    }
