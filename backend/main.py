import boto3
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
import redis
import re
from typing import List, Optional
from celery.result import AsyncResult

# Uvozi za bazu podataka, auth i rate-limiting
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.worker.celery_app import celery_app
from backend.core.config import settings
from backend.core.database import engine, get_db, Base
from backend.core.models import User, Project, Segment, Glossary, Waitlist
from backend.core.auth import get_password_hash, verify_password, create_access_token, get_current_user
from botocore.config import Config

# Automatsko kreiranje tabela u bazi podataka pri startu servera
Base.metadata.create_all(bind=engine)

# Inicijalizacija Rate Limiter-a sa Redis storage-om za deljenje stanja i perzistenciju
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
app = FastAPI(title="Sinhronizuj.me API", description="API za inteligentnu sinhronizaciju videa", version="2.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.TEMP_WORKSPACE, exist_ok=True)
app.mount("/videos", StaticFiles(directory=settings.TEMP_WORKSPACE), name="videos")

# Pomoćna funkcija za Redis konekciju
def get_redis_client():
    match = re.search(r'@([^:/]+)', settings.REDIS_URL)
    redis_host = match.group(1) if match else "redis"
    return redis.Redis(host=redis_host, password=settings.REDIS_PASSWORD, port=6379, db=0)

def get_presigned_download_url(bucket_name: str, object_key: str, expires_in: int = 86400) -> str:
    if not object_key:
        return ""
    if object_key.startswith("http://") or object_key.startswith("https://"):
        return object_key
        
    s3_public = boto3.client(
        's3',
        endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    try:
        url = s3_public.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        print(f"[ERROR] Greška pri generisanju pre-signed URL-a za preuzimanje: {e}", flush=True)
        return ""

# PYDANTIC MODELI ZA AUTH I ZAHTEVE
class UserRegisterRequest(BaseModel):
    email: str
    password: str

class UserLoginRequest(BaseModel):
    email: str
    password: str

class WaitlistRequest(BaseModel):
    email: str


class VideoRequest(BaseModel):
    url: str
    debug: bool = False
    project_id: Optional[str] = None

class CreateProjectRequest(BaseModel):
    name: str

class SegmentItem(BaseModel):
    id: int
    start: float
    end: float
    original: str
    translated: str
    tts_path: Optional[str] = None
    tts_duration: Optional[float] = None
    status: Optional[str] = "draft"
    voice_type: Optional[str] = "clone"
    volume: Optional[float] = 0.0
    speed: Optional[float] = 1.0
    pitch: Optional[float] = 0.0
    bg_volume: Optional[float] = 0.0

class SaveProjectRequest(BaseModel):
    segments: List[SegmentItem]

class SegmentTTSRequest(BaseModel):
    text: str
    voice_type: str = "clone"
    volume: float = 0.0
    speed: float = 1.0
    pitch: float = 0.0
    bg_volume: float = 0.0

class ShortenSegmentRequest(BaseModel):
    text: str

class GenerateAllTTSRequest(BaseModel):
    voice_type: str = "clone"

class RenderRequest(BaseModel):
    voice_type: str = "clone"
    background_volume: float = -5.0
    dubbed_volume: float = 0.0

class MixerSettingsRequest(BaseModel):
    background_volume: float
    dubbed_volume: float

# --- HOME I AUTENTIFIKACIJA RUTE ---

@app.get("/")
def read_root():
    return {"message": "Sinhronizuj.me API je aktivan i ažuriran na v2.0 (Dvofazni, PostgreSQL, JWT)!"}

@app.post("/api/v1/waitlist")
@limiter.limit("5/minute")
def add_to_waitlist(request: Request, data: WaitlistRequest, db: Session = Depends(get_db)):
    """
    Dodavanje korisnika na listu čekanja (Waitlist) za zatvorenu betu.
    """
    # Normalizacija email adrese
    email_clean = data.email.strip().lower()
    
    # Validacija email formata
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email_clean):
        raise HTTPException(status_code=400, detail="Neispravan format email adrese.")
        
    # Provera da li je već na listi čekanja
    existing_waitlist = db.query(Waitlist).filter(Waitlist.email == email_clean).first()
    if existing_waitlist:
        raise HTTPException(status_code=400, detail="Ovaj email je već prijavljen na listu čekanja.")
        
    # Provera da li već postoji ulogovani nalog sa tim emailom
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Korisnik sa ovim email-om već ima otvoren nalog. Prijavite se.")
        
    # Dodavanje u bazu
    new_entry = Waitlist(email=email_clean)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    
    return {"status": "success", "message": "Uspešno ste se prijavili na listu čekanja."}


@app.post("/api/v1/auth/register")
@limiter.limit("10/minute")
def register_user(request: Request, data: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Registracija novog korisničkog naloga.
    """
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Korisnik sa ovim email-om već postoji.")
    
    hashed_pwd = get_password_hash(data.password)
    new_user = User(email=data.email, password_hash=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "success", "message": "Nalog je uspešno kreiran. Prijavite se."}

@app.post("/api/v1/auth/login")
@limiter.limit("15/minute")
def login_user(request: Request, data: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Prijava korisnika i generisanje JWT tokena.
    """
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Pogrešan email ili lozinka.")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email
        }
    }

@app.get("/api/v1/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """
    Profil ulogovanog korisnika na osnovu JWT tokena.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email
    }

# --- RUTE ZA UPLOAD I OBRADU VIDEA ---

@app.get("/api/v1/storage/upload_url")
def get_upload_url(filename: str, content_type: str = 'video/mp4', current_user: User = Depends(get_current_user)):
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
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
        except Exception:
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
        return {
            "upload_url": url, 
            "file_key": filename,
            "s3_url": f"s3://{settings.MINIO_BUCKET}/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/process-video")
@limiter.limit("5/hour")
def process_video(request: Request, data: VideoRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Pokreće asinhronu analizu videa (Faza 1). Zahteva proveru vlasništva.
    """
    print(f"--- [API RECEIVE] Pokrećem FAZU 1 (Analiza): url={data.url}, project_id={data.project_id}", flush=True)
    
    if data.project_id:
        p = db.query(Project).filter(Project.id == data.project_id, Project.user_id == current_user.id).first()
        if not p:
            raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
            
    from backend.worker.tasks import analyze_video_task
    task = analyze_video_task.delay(data.url, data.debug, project_id=data.project_id)
    
    r = get_redis_client()
    if data.project_id:
        r.set(f"task:{task.id}:project_id", data.project_id, ex=86400) # 24h
        
        # Ažuriramo status projekta u bazi
        p.status = "analyzing"
        db.commit()
                
    return {
        "status": "success",
        "message": "Započet asinhroni proces analize videa.",
        "task_id": task.id
    }

# --- NOVE DVOFAZNE RUTE SA POSTGRES VLASNIŠTVOM ---

@app.post("/api/v1/project")
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

@app.get("/api/v1/projects")
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

@app.delete("/api/v1/project/{project_id}")
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
        config=Config(signature_version='s3v4'),
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

@app.get("/api/v1/project/{project_id}")
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
            "tts_path": get_presigned_download_url(settings.MINIO_BUCKET, s.tts_s3_key) if s.tts_s3_key else None,
            "tts_duration": s.tts_duration,
            "status": s.status
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
    
    # Dodatni keš u Redisu za asinkrone radnike ukoliko je potrebno pročitati brzo draft_path
    r = get_redis_client()
    r.set(f"project:{project_id}:draft", json.dumps(project_data), ex=604800)
    
    return project_data

@app.post("/api/v1/project/{project_id}/save")
def save_project_draft(project_id: str, request: SaveProjectRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Čuva najnovije izmene segmenata prevoda u PostgreSQL bazu.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    for req_seg in request.segments:
        db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == req_seg.id).first()
        if db_seg:
            db_seg.translated = req_seg.translated
            db_seg.voice_type = req_seg.voice_type or "clone"
            db_seg.volume = req_seg.volume if req_seg.volume is not None else 0.0
            db_seg.speed = req_seg.speed if req_seg.speed is not None else 1.0
            db_seg.pitch = req_seg.pitch if req_seg.pitch is not None else 0.0
            db_seg.bg_volume = req_seg.bg_volume if req_seg.bg_volume is not None else 0.0
            db_seg.status = "edited"
            
    db.commit()
    
    # Sinhronizujemo Redis za kompatibilnost
    get_project_draft(project_id, current_user, db)
    
    return {"status": "success", "message": "Promene na prevodu su sačuvane."}

@app.post("/api/v1/project/{project_id}/segment/{segment_id}/shorten")
@limiter.limit("30/minute")
def shorten_segment_translation(request: Request, project_id: str, segment_id: int, data: ShortenSegmentRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    AI Lektura za skraćivanje teksta uz proveru vlasništva.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    r = get_redis_client()
    draft_bytes = r.get(f"project:{project_id}:draft")
    if not draft_bytes:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen.")
    
    project_data = json.loads(draft_bytes)
    segments = project_data["segments"]
    
    target_segment = None
    for s in segments:
        if s["id"] == segment_id:
            target_segment = s
            break
            
    if not target_segment:
        raise HTTPException(status_code=404, detail="Segment nije pronađen.")
        
    original_text = target_segment.get("original", "")
    duration = target_segment.get("end", 0.0) - target_segment.get("start", 0.0)
    
    if duration < 2.5:
        limit = max(int(duration * 15), 10)
    else:
        limit = max(int(duration * 20), 10)
        
    if not settings.MODAL_LEKTOR_URL:
        raise HTTPException(status_code=500, detail="Modal Lektor nije konfigurisan na serveru.")
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    
    lektor_prompt = (
        "Ti si stručni lektor i prevodilac za srpski jezik (ekavica, latinica). Dobio si zadatak da skratiš i lekturišeš prevod na srpskom jeziku kako bi stao u predviđeni vremenski okvir sinhronizacije (govora).\n\n"
        f"Originalni engleski tekst: {original_text}\n"
        f"Maksimalno dozvoljeno trajanje: {duration:.2f}s\n"
        f"Strogi limit karaktera sa razmacima: {limit} (Tvoj novi prevod MORA imati manje karaktera od ovog limita!)\n"
        f"Trenutni prevod koji treba da skratiš: {data.text}\n\n"
        "OBAVEZNA PRAVILA ZA SKRAĆIVANJE:\n"
        "1. Prevod mora biti kraći i jezgrovitiji, STRIKTNO ispod limita karaktera. Bolje je izgubiti detalje nego prekoračiti vreme govora!\n"
        "2. Sačuvaj osnovnu poruku originalne engleske rečenice.\n"
        "3. Piši isključivo na srpskoj latinici (ekavica) i koristi prirodne fraze.\n"
        "4. Poštuj glosar i pravila za reči (npr. 'thin square tubes' -> tanke kvadratne cevi, 'welding rods' -> elektrode za zavarivanje, 'welder' -> zavarivač, 'nut' -> matica, 'jammer' -> ometač, 'feels' -> oseća, 'seashell' -> školjka).\n"
        "5. NIKADA ne koristi ijekavske reči (npr. smeje, dela, delovi, deo, video, rešenje, tačke, tačka) niti strane neprevedene termine.\n"
        "6. Obraćaj se sa 'ti' (npr. 'ako želiš', 'uradi').\n"
        "7. Vrati SAMO i isključivo novi skraćeni tekst, bez ikakvih uvoda, komentara, navodnika, objašnjenja ili CoT analize. Tvoj odgovor treba da bude čista rečenica."
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": lektor_prompt}],
        "temperature": 0.2,
        "max_tokens": 150
    }
    
    try:
        from backend.worker.utils import call_modal_endpoint
        from backend.worker.translator import clean_translation_text, to_latin
        
        response_data = call_modal_endpoint(url=url, payload=payload)
        choices = response_data.get("choices", [])
        if not choices:
            raise Exception("Lektor nije vratio validan odgovor.")
            
        shortened_text = choices[0]["message"]["content"].strip()
        if shortened_text.startswith('"') and shortened_text.endswith('"'):
            shortened_text = shortened_text[1:-1].strip()
        if shortened_text.startswith("'") and shortened_text.endswith("'"):
            shortened_text = shortened_text[1:-1].strip()
            
        shortened_text = clean_translation_text(to_latin(shortened_text))
            
        return {
            "status": "success",
            "original_text": data.text,
            "shortened_text": shortened_text,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/project/{project_id}/segment/{segment_id}/tts")
@limiter.limit("30/minute")
def generate_segment_tts(request: Request, project_id: str, segment_id: int, data: SegmentTTSRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Sinteza pojedinačnog segmenta govora uz proveru vlasništva i skladištenje na S3.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == segment_id).first()
    if not db_seg:
        raise HTTPException(status_code=404, detail="Segment nije pronađen.")
        
    probni_filename = f"tts_probni_{project_id}_{segment_id}.wav"
    stable_probni_path = os.path.join(settings.TEMP_WORKSPACE, probni_filename)
    
    raw_filename = f"tts_raw_{project_id}_{segment_id}.wav"
    stable_raw_path = os.path.join(settings.TEMP_WORKSPACE, raw_filename)
    
    from backend.worker.utils import apply_audio_modifiers
    from pydub import AudioSegment
    
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    is_fast_adjust = (
        db_seg.translated == data.text and 
        db_seg.voice_type == data.voice_type
    )
    
    if is_fast_adjust:
        # Preuzmi tts_raw sa S3 ako ga nema lokalno
        raw_s3_key = f"projects/{project_id}/tts_raw_{segment_id}.wav"
        if not os.path.exists(stable_raw_path):
            try:
                s3.download_file(settings.MINIO_BUCKET, raw_s3_key, stable_raw_path)
            except Exception:
                is_fast_adjust = False
                
    if is_fast_adjust and os.path.exists(stable_raw_path):
        apply_audio_modifiers(
            stable_raw_path,
            stable_probni_path,
            volume=data.volume,
            speed=data.speed,
            pitch=data.pitch
        )
        try:
            updated_audio = AudioSegment.from_wav(stable_probni_path)
            actual_duration = len(updated_audio) / 1000.0
        except Exception:
            actual_duration = db_seg.tts_duration or (db_seg.end - db_seg.start)
    else:
        # Preuzmi vocals sa S3
        local_vocals_path = os.path.join(settings.TEMP_WORKSPACE, f"vocals_temp_{project_id}.wav")
        if not os.path.exists(local_vocals_path) and p.vocals_s3_key:
            try:
                s3.download_file(settings.MINIO_BUCKET, p.vocals_s3_key, local_vocals_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Greška pri preuzimanju vokala sa S3: {e}")
                
        # Svi segmenti za TTS engine
        db_segs = db.query(Segment).filter(Segment.project_id == project_id).order_by(Segment.segment_id).all()
        segments_list_dicts = [{"id": s.segment_id, "start": s.start, "end": s.end, "original": s.original, "translated": s.translated} for s in db_segs]
        
        from backend.worker.tts_engine import synthesize_audio
        
        single_tts_segment = [{
            "id": db_seg.segment_id,
            "start": db_seg.start,
            "end": db_seg.end,
            "text": data.text,
            "original_text": db_seg.original
        }]
        
        tts_result = synthesize_audio(
            local_vocals_path,
            single_tts_segment,
            voice_type=data.voice_type,
            disable_openvoice=settings.DISABLE_OPENVOICE,
            disable_enhance=settings.DISABLE_ENHANCE,
            all_segments=segments_list_dicts
        )
        
        if tts_result["status"] == "error":
            raise HTTPException(status_code=500, detail=f"TTS sinteza nije uspela: {tts_result.get('message')}")
            
        res_segments = tts_result.get("tts_segments", [])
        if not res_segments:
            raise HTTPException(status_code=500, detail="TTS nije vratio metapodatke o segmentu.")
            
        generated_seg = res_segments[0]
        
        import shutil
        shutil.copy2(generated_seg["path"], stable_raw_path)
        
        apply_audio_modifiers(
            generated_seg["path"],
            stable_probni_path,
            volume=data.volume,
            speed=data.speed,
            pitch=data.pitch
        )
        
        try:
            updated_audio = AudioSegment.from_wav(stable_probni_path)
            actual_duration = len(updated_audio) / 1000.0
        except Exception:
            actual_duration = generated_seg["duration"]
            
        if os.path.exists(generated_seg["path"]):
            os.remove(generated_seg["path"])
        if os.path.exists(tts_result["dubbed_audio_path"]):
            os.remove(tts_result["dubbed_audio_path"])
            
    # Upload novog probnog i raw fajla na S3
    probni_s3_key = f"projects/{project_id}/tts_seg_{segment_id}.wav"
    raw_s3_key = f"projects/{project_id}/tts_raw_{segment_id}.wav"
    
    try:
        s3.upload_file(stable_probni_path, settings.MINIO_BUCKET, probni_s3_key)
        s3.upload_file(stable_raw_path, settings.MINIO_BUCKET, raw_s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload TTS neuspešan: {e}")
        
    # Čišćenje lokalnih fajlova
    if os.path.exists(stable_probni_path): os.remove(stable_probni_path)
    if os.path.exists(stable_raw_path): os.remove(stable_raw_path)
    
    # Ažuriranje u bazi podataka
    db_seg.translated = data.text
    db_seg.voice_type = data.voice_type
    db_seg.volume = data.volume
    db_seg.speed = data.speed
    db_seg.pitch = data.pitch
    db_seg.bg_volume = data.bg_volume
    db_seg.tts_s3_key = probni_s3_key
    db_seg.tts_duration = actual_duration
    db_seg.status = "previewed"
    db.commit()
    
    # Regenerišemo ceo sinhronizovani audio ako postoji
    if p.dubbed_audio_s3_key:
        local_dubbed_path = os.path.join(settings.TEMP_WORKSPACE, f"dubbed_temp_{project_id}.wav")
        try:
            s3.download_file(settings.MINIO_BUCKET, p.dubbed_audio_s3_key, local_dubbed_path)
            full_audio = AudioSegment.from_wav(local_dubbed_path)
            
            # Preuzmi ovaj segment ponovo na kratko da uradiš overlay
            temp_seg_local = os.path.join(settings.TEMP_WORKSPACE, f"temp_seg_{segment_id}.wav")
            s3.download_file(settings.MINIO_BUCKET, probni_s3_key, temp_seg_local)
            new_seg_audio = AudioSegment.from_wav(temp_seg_local)
            
            start_ms = int(db_seg.start * 1000)
            old_duration_ms = int((db_seg.tts_duration or (db_seg.end - db_seg.start)) * 1000)
            
            part1 = full_audio[:start_ms]
            part2 = AudioSegment.silent(duration=old_duration_ms)
            part3 = full_audio[start_ms + old_duration_ms:]
            
            temp_audio = part1 + part2 + part3
            full_audio = temp_audio.overlay(new_seg_audio, position=start_ms)
            full_audio.export(local_dubbed_path, format="wav")
            
            s3.upload_file(local_dubbed_path, settings.MINIO_BUCKET, p.dubbed_audio_s3_key)
            
            if os.path.exists(local_dubbed_path): os.remove(local_dubbed_path)
            if os.path.exists(temp_seg_local): os.remove(temp_seg_local)
        except Exception as e:
            print(f"[ERROR] Greška pri osvežavanju celog dubbed audia na S3: {e}", flush=True)
            
    # Sinhronizujemo Redis za kompatibilnost
    get_project_draft(project_id, current_user, db)
    
    # Generišemo presigned URL za probni fajl
    presigned_url = get_presigned_download_url(settings.MINIO_BUCKET, probni_s3_key)
    
    return {
        "status": "success",
        "audio_url": presigned_url,
        "duration": actual_duration
    }

@app.post("/api/v1/project/{project_id}/generate-all-tts")
@limiter.limit("10/minute")
def generate_all_tts(request: Request, project_id: str, data: GenerateAllTTSRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Sinteza glasa za ceo video uz proveru vlasništva i prenos na S3.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    db_segments = db.query(Segment).filter(Segment.project_id == project_id).order_by(Segment.segment_id).all()
    if not db_segments:
        raise HTTPException(status_code=400, detail="Projekat nema segmenata za sintezu.")
        
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # Preuzmi vocals sa S3
    local_vocals_path = os.path.join(settings.TEMP_WORKSPACE, f"vocals_temp_{project_id}.wav")
    if not os.path.exists(local_vocals_path) and p.vocals_s3_key:
        try:
            s3.download_file(settings.MINIO_BUCKET, p.vocals_s3_key, local_vocals_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Greška pri preuzimanju vokala sa S3: {e}")
            
    tts_segments = []
    segments_list_dicts = []
    for s in db_segments:
        item = {
            "id": s.segment_id,
            "start": s.start,
            "end": s.end,
            "text": s.translated,
            "original_text": s.original,
            "voice_type": s.voice_type or data.voice_type
        }
        tts_segments.append(item)
        segments_list_dicts.append(item)
        
    from backend.worker.tts_engine import synthesize_audio
    tts_result = synthesize_audio(
        local_vocals_path,
        tts_segments,
        voice_type=data.voice_type,
        disable_openvoice=settings.DISABLE_OPENVOICE,
        disable_enhance=settings.DISABLE_ENHANCE,
        all_segments=segments_list_dicts
    )
    
    if tts_result["status"] == "error":
        raise HTTPException(status_code=500, detail=f"Sinteza celog videa nije uspela: {tts_result.get('message')}")
        
    res_segments = tts_result.get("tts_segments", [])
    res_map = {s["id"]: s for s in res_segments}
    
    from pydub import AudioSegment
    try:
        ref_audio = AudioSegment.from_wav(local_vocals_path)
        video_duration_ms = len(ref_audio)
    except Exception:
        video_duration_ms = 30000
        
    final_mix = AudioSegment.silent(duration=video_duration_ms)
    
    from backend.worker.utils import apply_audio_modifiers
    
    for s in db_segments:
        if s.segment_id in res_map:
            res_s = res_map[s.segment_id]
            seg_filename = f"tts_seg_{project_id}_{s.segment_id}.wav"
            stable_seg_path = os.path.join(settings.TEMP_WORKSPACE, seg_filename)
            
            apply_audio_modifiers(
                res_s["path"],
                stable_seg_path,
                volume=s.volume,
                speed=s.speed,
                pitch=s.pitch
            )
            
            try:
                seg_audio = AudioSegment.from_wav(stable_seg_path)
                duration = len(seg_audio) / 1000.0
            except Exception:
                try:
                    seg_audio = AudioSegment.from_wav(res_s["path"])
                except Exception:
                    seg_audio = AudioSegment.silent(duration=int((s.end - s.start) * 1000))
                duration = res_s.get("duration", s.end - s.start)
                
            # Upload pojedinačnog tts wav na S3
            probni_s3_key = f"projects/{project_id}/tts_seg_{s.segment_id}.wav"
            raw_s3_key = f"projects/{project_id}/tts_raw_{s.segment_id}.wav"
            
            try:
                s3.upload_file(stable_seg_path, settings.MINIO_BUCKET, probni_s3_key)
                s3.upload_file(res_s["path"], settings.MINIO_BUCKET, raw_s3_key)
            except Exception as e:
                print(f"[S3 UPLOAD ERROR] Greška pri uploadu TTS seg {s.segment_id}: {e}", flush=True)
                
            s.tts_s3_key = probni_s3_key
            s.tts_duration = duration
            s.status = "previewed"
            
            # Dodajemo u miks
            try:
                start_ms = int(s.start * 1000)
                final_mix = final_mix.overlay(seg_audio, position=start_ms)
            except Exception:
                pass
                
            # Čišćenje lokalno
            if os.path.exists(stable_seg_path): os.remove(stable_seg_path)
            if os.path.exists(res_s["path"]): os.remove(res_s["path"])
            
        elif s.tts_s3_key:
            # Ako već ima generisan tts_path na S3, preuzmi ga i ubaci u miks
            temp_seg_local = os.path.join(settings.TEMP_WORKSPACE, f"temp_seg_{s.segment_id}.wav")
            try:
                s3.download_file(settings.MINIO_BUCKET, s.tts_s3_key, temp_seg_local)
                seg_audio = AudioSegment.from_wav(temp_seg_local)
                start_ms = int(s.start * 1000)
                final_mix = final_mix.overlay(seg_audio, position=start_ms)
                if os.path.exists(temp_seg_local): os.remove(temp_seg_local)
            except Exception:
                pass
                
    # Izvozimo i uploadujemo ceo dubbed audio na S3
    dubbed_filename = f"tts_full_{project_id}.wav"
    stable_dubbed_path = os.path.join(settings.TEMP_WORKSPACE, dubbed_filename)
    final_mix.export(stable_dubbed_path, format="wav")
    
    dubbed_audio_s3_key = f"projects/{project_id}/dubbed_audio.wav"
    try:
        s3.upload_file(stable_dubbed_path, settings.MINIO_BUCKET, dubbed_audio_s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload celog tona neuspešan: {e}")
        
    if os.path.exists(stable_dubbed_path): os.remove(stable_dubbed_path)
    if os.path.exists(local_vocals_path): os.remove(local_vocals_path)
    if os.path.exists(tts_result["dubbed_audio_path"]): os.remove(tts_result["dubbed_audio_path"])
    
    p.dubbed_audio_s3_key = dubbed_audio_s3_key
    db.commit()
    
    # Sinhronizujemo Redis za kompatibilnost
    get_project_draft(project_id, current_user, db)
    
    presigned_dubbed_url = get_presigned_download_url(settings.MINIO_BUCKET, dubbed_audio_s3_key)
    
    return {
        "status": "success",
        "audio_url": presigned_dubbed_url,
        "segments": [{"id": s.segment_id, "tts_path": get_presigned_download_url(settings.MINIO_BUCKET, s.tts_s3_key)} for s in db_segments if s.tts_s3_key]
    }

@app.post("/api/v1/project/{project_id}/render")
@limiter.limit("2/hour")
def render_project(request: Request, project_id: str, data: RenderRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Pokretanje finalnog renderovanja (Faza 2) uz proveru vlasništva.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    from backend.worker.tasks import render_video_task
    print(f"--- [API RECEIVE] Pokrećem FAZU 2 (Render) za projekat: {project_id}", flush=True)
    task = render_video_task.delay(
        project_id, 
        data.voice_type, 
        data.background_volume, 
        data.dubbed_volume
    )
    return {
        "status": "success",
        "message": "Pokrenuto renderovanje finalnog videa.",
        "task_id": task.id
    }

# --- KONTROLA ZADATAKA I SISTEMSKE RUTE ---

@app.get("/api/v1/status/{task_id}")
def get_task_status(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Vraća status Celery taska uz proveru vlasništva nad projektom.
    """
    r = get_redis_client()
    project_id = r.get(f"task:{task_id}:project_id")
    if project_id:
        project_id_str = project_id.decode('utf-8')
        p = db.query(Project).filter(Project.id == project_id_str, Project.user_id == current_user.id).first()
        if not p:
            raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom statusu.")
            
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "project_id": project_id_str if project_id else None,
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

@app.post("/api/v1/warmup")
async def warmup_workers(current_user: User = Depends(get_current_user)):
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

@app.get("/api/v1/modal-status")
def get_modal_global_status(current_user: User = Depends(get_current_user)):
    return {
        "status": "Spreman",
        "active_workers": "Auto-Scale",
        "platform": "Modal.com",
        "timestamp": os.getpid()
    }

@app.get("/api/v1/hw-stats")
async def hw_stats(current_user: User = Depends(get_current_user)):
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

@app.get("/api/v1/logs")
def get_worker_logs(current_user: User = Depends(get_current_user)):
    log_path = os.path.join(os.path.dirname(__file__), "../worker.log")
    if not os.path.exists(log_path):
        return {"logs": "Log fajl još uvek nije generisan..."}
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
            logs = "".join(lines[-100:])
        return {"logs": logs}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/v1/flush-redis")
def flush_redis(current_user: User = Depends(get_current_user)):
    """
    Čisti Redis keš (samo neaktivne projekte stare preko 7 dana).
    """
    r = get_redis_client()
    # Dobavljamo sve metapodatke
    all_projects = r.hgetall("projects:metadata")
    from datetime import datetime, timedelta
    
    deleted_count = 0
    now = datetime.now()
    
    for pid_bytes, data_bytes in all_projects.items():
        try:
            pid = pid_bytes.decode('utf-8')
            meta = json.loads(data_bytes.decode('utf-8'))
            created_at_str = meta.get("created_at")
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str)
                # Ako je projekat prazan (empty) i stariji od 7 dana, obriši ga
                if meta.get("status") == "empty" and (now - created_at) > timedelta(days=7):
                    r.delete(f"project:{pid}:draft")
                    r.hdel("projects:metadata", pid)
                    deleted_count += 1
        except Exception:
            pass
            
    return {"status": "success", "message": f"Čišćenje završeno. Obrisano {deleted_count} neaktivnih projekata."}
