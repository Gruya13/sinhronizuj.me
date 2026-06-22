import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.models import User, Project, Segment
from backend.core.auth import get_current_user
from backend.core.schemas import ShortenSegmentRequest, SegmentTTSRequest, GenerateAllTTSRequest, RenderRequest
from backend.core.limiter import limiter
from backend.services.redis import get_redis_client

router = APIRouter(tags=["Segments"])

@router.post("/api/v1/project/{project_id}/segment/{segment_id}/shorten")
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

@router.post("/api/v1/project/{project_id}/segment/{segment_id}/tts")
@limiter.limit("30/minute")
def generate_segment_tts(request: Request, project_id: str, segment_id: int, data: SegmentTTSRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Sinteza pojedinačnog segmenta govora u asinhronom režimu preko Celery-ja.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == segment_id).first()
    if not db_seg:
        raise HTTPException(status_code=404, detail="Segment nije pronađen.")
        
    from backend.worker.tasks import generate_segment_tts_task
    task = generate_segment_tts_task.delay(
        project_id,
        segment_id,
        data.text,
        data.voice_type,
        data.volume,
        data.speed,
        data.pitch,
        data.bg_volume
    )
    
    from backend.services.redis import get_redis_client
    r = get_redis_client()
    r.set(f"task:{task.id}:project_id", project_id, ex=86400) # 24h
    
    return {
        "status": "success",
        "task_id": task.id,
        "detail": "Asinhroni TTS zadatak je uspešno pokrenut."
    }

@router.post("/api/v1/project/{project_id}/generate-all-tts")
@limiter.limit("10/minute")
def generate_all_tts(request: Request, project_id: str, data: GenerateAllTTSRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Sinteza glasa za ceo video u asinhronom režimu preko Celery-ja.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    db_segments = db.query(Segment).filter(Segment.project_id == project_id).all()
    if not db_segments:
        raise HTTPException(status_code=400, detail="Projekat nema segmenata za sintezu.")
        
    from backend.worker.tasks import generate_all_tts_task
    task = generate_all_tts_task.delay(
        project_id,
        data.voice_type
    )
    
    from backend.services.redis import get_redis_client
    r = get_redis_client()
    r.set(f"task:{task.id}:project_id", project_id, ex=86400) # 24h
    
    return {
        "status": "success",
        "task_id": task.id,
        "detail": "Asinhroni zadatak sinteze celog videa je uspešno pokrenut."
    }

@router.post("/api/v1/project/{project_id}/render")
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
