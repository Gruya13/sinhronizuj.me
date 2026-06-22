import uuid
import json
import boto3
import subprocess
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from botocore.config import Config

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.models import User, Project, Segment
from backend.core.auth import get_current_user
from backend.core.schemas import VideoRequest, CreateProjectRequest, SaveProjectRequest
from backend.core.limiter import limiter
from backend.services.redis import get_redis_client
from backend.services.s3 import get_presigned_download_url

router = APIRouter(tags=["Projects"])

@router.get("/api/v1/storage/upload_url")
def get_upload_url(
    filename: str, 
    project_id: str,
    content_type: str = 'video/mp4', 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu ili projekat ne postoji.")
        
    allowed_types = ["video/mp4", "video/webm", "video/ogg", "video/quicktime", "video/x-matroska"]
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Nedozvoljen tip sadržaja. Podržani su samo video fajlovi.")
        
    ext = filename.split('.')[-1] if '.' in filename else 'mp4'
    if ext.lower() not in ['mp4', 'webm', 'ogg', 'mov', 'mkv']:
        ext = 'mp4'
    
    safe_filename = f"users/{current_user.id}/projects/{project_id}/uploads/{uuid.uuid4()}.{ext}"
    
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        region_name=settings.S3_REGION
    )
    
    s3_public = boto3.client(
        's3',
        endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        region_name=settings.S3_REGION
    )
    
    try:
        try:
            s3_internal.head_bucket(Bucket=settings.MINIO_BUCKET)
        except Exception:
            s3_internal.create_bucket(Bucket=settings.MINIO_BUCKET)
            
        url = s3_public.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': settings.MINIO_BUCKET, 
                'Key': safe_filename,
                'ContentType': content_type
            },
            ExpiresIn=300
        )
        return {
            "upload_url": url, 
            "file_key": safe_filename,
            "s3_url": f"s3://{settings.MINIO_BUCKET}/{safe_filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/process-video")
@limiter.limit("5/hour")
def process_video(request: Request, data: VideoRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Pokreće asinhronu analizu videa (Faza 1). Zahteva proveru vlasništva, kvota i limita.
    """
    print(f"--- [API RECEIVE] Pokrećem FAZU 1 (Analiza): url={data.url}, project_id={data.project_id}", flush=True)
    
    if data.project_id:
        p = db.query(Project).filter(Project.id == data.project_id, Project.user_id == current_user.id).first()
        if not p:
            raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
            
    # --- KVOTE I LIMITI ---
    file_size_bytes = 0
    video_duration_sec = 0.0
    
    s3 = boto3.client(
        's3',
        endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        region_name=settings.S3_REGION
    )
    
    if data.url.startswith("s3://"):
        try:
            parts = data.url.replace("s3://", "").split("/")
            bucket = parts[0]
            key = "/".join(parts[1:])
            
            meta = s3.head_object(Bucket=bucket, Key=key)
            file_size_bytes = meta.get("ContentLength", 0)
            
            presigned = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=300
            )
            
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                presigned
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                video_duration_sec = float(res.stdout.strip())
        except Exception as e:
            print(f"[QUOTA WARNING] Greška pri dobijanju metapodataka za S3 video: {e}")
    else:
        try:
            import yt_dlp
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(data.url, download=False)
                file_size_bytes = info.get("filesize", info.get("filesize_approx", 0))
                video_duration_sec = float(info.get("duration", 0.0))
        except Exception as e:
            print(f"[QUOTA WARNING] Greška pri dobijanju metapodataka za eksterni video: {e}")
            try:
                cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    data.url
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    video_duration_sec = float(res.stdout.strip())
            except Exception:
                pass

    file_size_mb = file_size_bytes / (1024 * 1024) if file_size_bytes > 0 else 0.0
    print(f"[QUOTA CHECK] Korisnik: {current_user.id}, Fajl: {file_size_mb:.2f} MB, Trajanje: {video_duration_sec:.2f} s")

    if settings.MAX_SINGLE_FILE_SIZE_MB > 0 and file_size_mb > settings.MAX_SINGLE_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400, 
            detail=f"Veličina fajla ({file_size_mb:.2f} MB) prelazi limit od {settings.MAX_SINGLE_FILE_SIZE_MB} MB."
        )

    r = get_redis_client()
    
    now = datetime.utcnow()
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
    ttl_seconds = int((end_of_day - now).total_seconds())
    if ttl_seconds <= 0:
        ttl_seconds = 3600
        
    daily_bytes_key = f"user:{current_user.id}:daily_bytes"
    daily_duration_key = f"user:{current_user.id}:daily_duration"
    
    current_daily_bytes = float(r.get(daily_bytes_key) or 0.0)
    current_daily_duration = float(r.get(daily_duration_key) or 0.0)
    
    current_daily_mb = current_daily_bytes / (1024 * 1024)
    
    if settings.MAX_DAILY_UPLOAD_MB > 0 and (current_daily_mb + file_size_mb) > settings.MAX_DAILY_UPLOAD_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Prekoračen dnevni limit za upload. Preostalo: {settings.MAX_DAILY_UPLOAD_MB - current_daily_mb:.2f} MB. Zahtevano: {file_size_mb:.2f} MB."
        )
        
    if settings.MAX_DAILY_DURATION_SEC > 0 and (current_daily_duration + video_duration_sec) > settings.MAX_DAILY_DURATION_SEC:
        allowed_mins = settings.MAX_DAILY_DURATION_SEC / 60
        used_mins = current_daily_duration / 60
        raise HTTPException(
            status_code=400,
            detail=f"Prekoračen dnevni limit za trajanje videa ({allowed_mins:.1f} min). Danas ste već obradili {used_mins:.1f} min. Zahtevano: {video_duration_sec/60:.1f} min."
        )

    r.incrbyfloat(daily_bytes_key, file_size_bytes)
    r.incrbyfloat(daily_duration_key, video_duration_sec)
    r.expire(daily_bytes_key, ttl_seconds)
    r.expire(daily_duration_key, ttl_seconds)
    # ----------------------------------

    from backend.worker.tasks import analyze_video_task
    task = analyze_video_task.delay(data.url, data.debug, project_id=data.project_id)
    
    if data.project_id:
        r.set(f"task:{task.id}:project_id", data.project_id, ex=86400) # 24h
        p.status = "analyzing"
        db.commit()
                
    return {
        "status": "success",
        "message": "Započet asinhroni proces analize videa.",
        "task_id": task.id
    }

@router.post("/api/v1/project")
@limiter.limit("15/minute")
def create_project(request: Request, data: CreateProjectRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Kreira projekat u PostgreSQL bazi.
    """
    db_project = Project(
        name=data.name,
        user_id=current_user.id,
        status="empty"
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    proj_id_str = str(db_project.id)
    
    meta_data = {
        "id": proj_id_str,
        "name": db_project.name,
        "video_title": "",
        "status": "empty",
        "created_at": db_project.created_at.isoformat()
    }
    return meta_data

@router.get("/api/v1/projects")
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Izlistava projekte koji pripadaju isključivo ulogovanom korisniku iz baze podataka.
    """
    db_projects = db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.created_at.desc()).all()
    projects_list = []
    for p in db_projects:
        projects_list.append({
            "id": str(p.id),
            "name": p.name,
            "video_title": p.video_title or "",
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else ""
        })
    return projects_list

@router.delete("/api/v1/project/{project_id}")
def delete_project(project_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Briše projekat iz PostgreSQL-a i briše povezane fajlove sa S3 skladišta.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        region_name='us-east-1'
    )
    
    # Brišemo fajlove sa S3
    for key in [p.video_s3_key, p.vocals_s3_key, p.no_vocals_s3_key, p.visual_context_s3_key, p.dubbed_audio_s3_key, p.final_video_s3_key]:
        if key:
            try:
                s3.delete_object(Bucket=settings.MINIO_BUCKET, Key=key)
            except Exception as e:
                print(f"[S3 DELETE ERROR] Greška pri brisanju {key}: {e}", flush=True)
                
    # Brišemo tts fajlove pojedinačnih segmenata sa S3
    db_segs = db.query(Segment).filter(Segment.project_id == project_id).all()
    for s in db_segs:
        if s.tts_s3_key:
            try:
                s3.delete_object(Bucket=settings.MINIO_BUCKET, Key=s.tts_s3_key)
            except Exception:
                pass
                
    db.delete(p)
    db.commit()
    
    r = get_redis_client()
    r.delete(f"project:{project_id}:draft")
    
    return {"status": "success", "message": "Projekat je uspešno obrisan."}

@router.get("/api/v1/project/{project_id}")
def get_project_draft(project_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Učitava nacrt projekta i segmente iz baze podataka, sa generisanjem presigned URL-ova.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
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
            "active_speaker": s.active_speaker,
            "tts_path": get_presigned_download_url(settings.MINIO_BUCKET, s.tts_s3_key) if s.tts_s3_key else None,
            "tts_duration": s.tts_duration,
            "status": s.status,
            "confidence_score": s.confidence_score if s.confidence_score is not None else 5,
            "needs_retranslation": s.needs_retranslation if s.needs_retranslation is not None else False,
            "actual_speed_factor": s.actual_speed_factor if s.actual_speed_factor is not None else 1.0
        })
        
    project_data = {
        "project_id": str(p.id),
        "name": p.name,
        "video_url": get_presigned_download_url(settings.MINIO_BUCKET, p.video_s3_key) if p.video_s3_key else "",
        "video_path": p.video_s3_key, # Za kompatibilnost
        "vocals_path": p.vocals_s3_key,
        "no_vocals_path": p.no_vocals_s3_key,
        "no_vocals_url": get_presigned_download_url(settings.MINIO_BUCKET, p.no_vocals_s3_key) if p.no_vocals_s3_key else "",
        "dubbed_audio_path": p.dubbed_audio_s3_key,
        "dubbed_audio_url": get_presigned_download_url(settings.MINIO_BUCKET, p.dubbed_audio_s3_key) if p.dubbed_audio_s3_key else "",
        "visual_context_url": get_presigned_download_url("previews", p.visual_context_s3_key) if p.visual_context_s3_key else "",
        "title": p.video_title,
        "segments": segments_list,
        "costs": p.costs or {"phases": {}, "total_usd": 0.0},
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else ""
    }
    
    r = get_redis_client()
    r.set(f"project:{project_id}:draft", json.dumps(project_data), ex=604800)
    
    return project_data

@router.post("/api/v1/project/{project_id}/save")
def save_project_draft(project_id: str, request: SaveProjectRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Čuva najnovije izmene segmenata prevoda u PostgreSQL bazu.
    Optimizovano: Rešen N+1 upit i batch-ovano slanje glosara.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    # Učitavamo sve segmente projekta odjednom (izbegavanje N+1)
    db_segments = db.query(Segment).filter(Segment.project_id == project_id).all()
    db_segments_map = {s.segment_id: s for s in db_segments}
    
    corrections = []
    
    for req_seg in request.segments:
        db_seg = db_segments_map.get(req_seg.id)
        if db_seg:
            if db_seg.translated != req_seg.translated:
                # Skupljamo korekciju za batch slanje
                corrections.append({
                    "original": db_seg.original,
                    "old_translated": db_seg.translated,
                    "new_translated": req_seg.translated
                })
                db_seg.translated = req_seg.translated
            db_seg.voice_type = req_seg.voice_type or "clone"
            db_seg.volume = req_seg.volume if req_seg.volume is not None else 0.0
            db_seg.speed = req_seg.speed if req_seg.speed is not None else 1.0
            db_seg.pitch = req_seg.pitch if req_seg.pitch is not None else 0.0
            db_seg.bg_volume = req_seg.bg_volume if req_seg.bg_volume is not None else 0.0
            db_seg.active_speaker = req_seg.active_speaker if req_seg.active_speaker is not None else db_seg.active_speaker
            db_seg.status = "edited"
            
    db.commit()
    
    # Batch slanje svih ispravki glosara u jednom Celery tasku
    if corrections:
        from backend.worker.tasks import learn_user_glossary_batch_task
        learn_user_glossary_batch_task.delay(str(current_user.id), corrections)
    
    # Sinhronizujemo Redis
    get_project_draft(project_id, current_user, db)
    
    return {"status": "success", "message": "Promene na prevodu su sačuvane."}
