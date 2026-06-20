import os
import json
import shutil
import boto3
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from botocore.config import Config
from pydub import AudioSegment

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.models import User, Project, Segment
from backend.core.auth import get_current_user
from backend.core.schemas import ShortenSegmentRequest, SegmentTTSRequest, GenerateAllTTSRequest, RenderRequest
from backend.core.limiter import limiter
from backend.services.redis import get_redis_client
from backend.services.s3 import get_presigned_download_url
from backend.routes.projects import get_project_draft

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
    Sinteza pojedinačnog segmenta govora uz proveru vlasništva i skladištenje na S3.
    """
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=403, detail="Nemate pravo pristupa ovom projektu.")
        
    db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == segment_id).first()
    if not db_seg:
        raise HTTPException(status_code=404, detail="Segment nije pronađen.")
        
    old_tts_duration = db_seg.tts_duration or (db_seg.end - db_seg.start)
        
    probni_filename = f"tts_probni_{project_id}_{segment_id}.wav"
    stable_probni_path = os.path.join(settings.TEMP_WORKSPACE, probni_filename)
    
    raw_filename = f"tts_raw_{project_id}_{segment_id}.wav"
    stable_raw_path = os.path.join(settings.TEMP_WORKSPACE, raw_filename)
    
    from backend.worker.utils import apply_audio_modifiers
    
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
        local_vocals_path = os.path.join(settings.TEMP_WORKSPACE, f"vocals_temp_{project_id}.wav")
        if not os.path.exists(local_vocals_path) and p.vocals_s3_key:
            try:
                s3.download_file(settings.MINIO_BUCKET, p.vocals_s3_key, local_vocals_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Greška pri preuzimanju vokala sa S3: {e}")
                
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
            
    probni_s3_key = f"projects/{project_id}/tts_seg_{segment_id}.wav"
    raw_s3_key = f"projects/{project_id}/tts_raw_{segment_id}.wav"
    
    try:
        s3.upload_file(stable_probni_path, settings.MINIO_BUCKET, probni_s3_key)
        s3.upload_file(stable_raw_path, settings.MINIO_BUCKET, raw_s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload TTS neuspešan: {e}")
        
    if os.path.exists(stable_probni_path): os.remove(stable_probni_path)
    if os.path.exists(stable_raw_path): os.remove(stable_raw_path)
    
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
    
    if p.dubbed_audio_s3_key:
        local_dubbed_path = os.path.join(settings.TEMP_WORKSPACE, f"dubbed_temp_{project_id}.wav")
        try:
            s3.download_file(settings.MINIO_BUCKET, p.dubbed_audio_s3_key, local_dubbed_path)
            full_audio = AudioSegment.from_wav(local_dubbed_path)
            
            temp_seg_local = os.path.join(settings.TEMP_WORKSPACE, f"temp_seg_{segment_id}.wav")
            s3.download_file(settings.MINIO_BUCKET, probni_s3_key, temp_seg_local)
            new_seg_audio = AudioSegment.from_wav(temp_seg_local)
            
            start_ms = int(db_seg.start * 1000)
            old_duration_ms = int(old_tts_duration * 1000)
            
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
            
    get_project_draft(project_id, current_user, db)
    
    presigned_url = get_presigned_download_url(settings.MINIO_BUCKET, probni_s3_key)
    
    return {
        "status": "success",
        "audio_url": presigned_url,
        "duration": actual_duration
    }

@router.post("/api/v1/project/{project_id}/generate-all-tts")
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
            
            try:
                start_ms = int(s.start * 1000)
                final_mix = final_mix.overlay(seg_audio, position=start_ms)
            except Exception:
                pass
                
            if os.path.exists(stable_seg_path): os.remove(stable_seg_path)
            if os.path.exists(res_s["path"]): os.remove(res_s["path"])
            
        elif s.tts_s3_key:
            temp_seg_local = os.path.join(settings.TEMP_WORKSPACE, f"temp_seg_{s.segment_id}.wav")
            try:
                s3.download_file(settings.MINIO_BUCKET, s.tts_s3_key, temp_seg_local)
                seg_audio = AudioSegment.from_wav(temp_seg_local)
                start_ms = int(s.start * 1000)
                final_mix = final_mix.overlay(seg_audio, position=start_ms)
                if os.path.exists(temp_seg_local): os.remove(temp_seg_local)
            except Exception:
                pass
                
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
    
    get_project_draft(project_id, current_user, db)
    
    presigned_dubbed_url = get_presigned_download_url(settings.MINIO_BUCKET, dubbed_audio_s3_key)
    
    return {
        "status": "success",
        "audio_url": presigned_dubbed_url,
        "segments": [{"id": s.segment_id, "tts_path": get_presigned_download_url(settings.MINIO_BUCKET, s.tts_s3_key)} for s in db_segments if s.tts_s3_key]
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
