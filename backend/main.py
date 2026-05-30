import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
import redis
import re
from typing import List, Optional
from celery.result import AsyncResult
from backend.worker.celery_app import celery_app
from backend.core.config import settings
from botocore.config import Config

app = FastAPI(title="Sinhronizuj.me API", description="API za inteligentnu sinhronizaciju videa", version="2.0.0")

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

class VideoRequest(BaseModel):
    url: str
    debug: bool = False

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

class SaveProjectRequest(BaseModel):
    segments: List[SegmentItem]

class SegmentTTSRequest(BaseModel):
    text: str
    voice_type: str = "clone"
    volume: float = 0.0
    speed: float = 1.0
    pitch: float = 0.0

class GenerateAllTTSRequest(BaseModel):
    voice_type: str = "clone"

class RenderRequest(BaseModel):
    voice_type: str = "clone"
    background_volume: float = -5.0
    dubbed_volume: float = 0.0

class MixerSettingsRequest(BaseModel):
    background_volume: float
    dubbed_volume: float

@app.get("/")
def read_root():
    return {"message": "Sinhronizuj.me API je aktivan i ažuriran na v2.0 (Dvofazni)!"}

@app.get("/api/v1/storage/upload_url")
def get_upload_url(filename: str, content_type: str = 'video/mp4'):
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
        except:
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
        
        print(f"--- DEBUG: GENERISAN JAVNI URL: {url}", flush=True)
            
        return {
            "upload_url": url, 
            "file_key": filename,
            "s3_url": f"s3://{settings.MINIO_BUCKET}/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/process-video")
def process_video(request: VideoRequest):
    print(f"--- [API RECEIVE] Pokrećem FAZU 1 (Analiza): url={request.url}", flush=True)
    from backend.worker.tasks import analyze_video_task
    # Pokrećemo analizu (Faza 1)
    task = analyze_video_task.delay(request.url, request.debug)
    return {
        "status": "success",
        "message": "Započet asinhroni proces analize videa.",
        "task_id": task.id
    }

# --- NOVE RUTE ZA DVOFAZNI PIPELINE ---

@app.get("/api/v1/project/{project_id}")
def get_project_draft(project_id: str):
    """
    Učitava nacrt projekta iz Redis-a.
    """
    r = get_redis_client()
    draft_bytes = r.get(f"project:{project_id}:draft")
    if not draft_bytes:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen ili je istekao.")
    return json.loads(draft_bytes)

@app.post("/api/v1/project/{project_id}/save")
def save_project_draft(project_id: str, request: SaveProjectRequest):
    """
    Čuva najnovije izmene prevoda segmenata u Redis-u.
    """
    r = get_redis_client()
    draft_bytes = r.get(f"project:{project_id}:draft")
    if not draft_bytes:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen.")
        
    project_data = json.loads(draft_bytes)
    
    # Ažuriramo segmente
    updated_segments = []
    seg_map = {s.id: s for s in request.segments}
    
    for orig_seg in project_data["segments"]:
        orig_id = orig_seg["id"]
        if orig_id in seg_map:
            req_seg = seg_map[orig_id]
            # Ažuriramo prevedeni tekst, glas i audio podešavanja za segment
            orig_seg["translated"] = req_seg.translated
            orig_seg["voice_type"] = req_seg.voice_type or orig_seg.get("voice_type", "clone")
            orig_seg["volume"] = req_seg.volume if req_seg.volume is not None else orig_seg.get("volume", 0.0)
            orig_seg["speed"] = req_seg.speed if req_seg.speed is not None else orig_seg.get("speed", 1.0)
            orig_seg["pitch"] = req_seg.pitch if req_seg.pitch is not None else orig_seg.get("pitch", 0.0)
            orig_seg["status"] = "edited"
        updated_segments.append(orig_seg)
        
    project_data["segments"] = updated_segments
    r.set(f"project:{project_id}:draft", json.dumps(project_data), ex=604800)
    return {"status": "success", "message": "Promene na prevodu su sačuvane."}

@app.post("/api/v1/project/{project_id}/segment/{segment_id}/tts")
def generate_segment_tts(project_id: str, segment_id: int, request: SegmentTTSRequest):
    """
    Brza i izolovana sinteza glasa samo za jedan segment.
    Omogućava korisniku da presluša prevod u realnom vremenu na vremenskoj liniji.
    """
    r = get_redis_client()
    draft_bytes = r.get(f"project:{project_id}:draft")
    if not draft_bytes:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen.")
        
    project_data = json.loads(draft_bytes)
    segments = project_data["segments"]
    
    # Pronalazimo traženi segment
    target_segment = None
    for s in segments:
        if s["id"] == segment_id:
            target_segment = s
            break
            
    if target_segment is None:
        raise HTTPException(status_code=404, detail="Segment nije pronađen.")
        
    # Pokrećemo brzu sintezu samo za taj jedan segment
    from backend.worker.tts_engine import synthesize_audio
    
    # Formatiramo segment za funkciju sinteze
    single_tts_segment = [{
        "id": target_segment["id"],
        "start": target_segment["start"],
        "end": target_segment["end"],
        "text": request.text,
        "original_text": target_segment["original"]
    }]
    
    print(f"[API TTS] Pokrećem probni segment TTS za {project_id} seg-{segment_id} sa tekstom: {request.text}")
    
    tts_result = synthesize_audio(
        project_data["vocals_path"],
        single_tts_segment,
        voice_type=request.voice_type,
        disable_openvoice=settings.DISABLE_OPENVOICE,
        disable_enhance=settings.DISABLE_ENHANCE,
        all_segments=segments
    )
    
    if tts_result["status"] == "error":
        raise HTTPException(status_code=500, detail=f"TTS sinteza nije uspela: {tts_result.get('message')}")
        
    # Uzimamo generisani fajl
    res_segments = tts_result.get("tts_segments", [])
    if not res_segments:
        raise HTTPException(status_code=500, detail="TTS nije vratio metapodatke o segmentu.")
        
    # Primenjujemo audio modifikatore (volume, speed, pitch)
    from backend.worker.utils import apply_audio_modifiers
    probni_filename = f"tts_probni_{project_id}_{segment_id}.wav"
    stable_probni_path = os.path.join(os.path.dirname(settings.TEMP_WORKSPACE), settings.TEMP_WORKSPACE, probni_filename)
    
    apply_audio_modifiers(
        generated_seg["path"],
        stable_probni_path,
        volume=request.volume,
        speed=request.speed,
        pitch=request.pitch
    )
    
    # Učitavamo tačno novo trajanje nakon modifikacija
    from pydub import AudioSegment
    try:
        updated_audio = AudioSegment.from_wav(stable_probni_path)
        actual_duration = len(updated_audio) / 1000.0
    except Exception:
        actual_duration = generated_seg["duration"]
    
    # Ažuriramo metapodatke u nacrtu u Redis-u
    old_duration = target_segment.get("tts_duration")
    old_duration_ms = int(old_duration * 1000) if old_duration else int((target_segment["end"] - target_segment["start"]) * 1000)
    
    target_segment["translated"] = request.text
    target_segment["voice_type"] = request.voice_type
    target_segment["tts_path"] = stable_probni_path
    target_segment["tts_duration"] = actual_duration
    target_segment["volume"] = request.volume
    target_segment["speed"] = request.speed
    target_segment["pitch"] = request.pitch
    target_segment["status"] = "previewed"
    
    # Ako već postoji izgenerisan pun miks za ceo video, ažuriramo i njega dinamički!
    dubbed_path = project_data.get("dubbed_audio_path")
    if dubbed_path and os.path.exists(dubbed_path):
        try:
            from pydub import AudioSegment
            full_audio = AudioSegment.from_wav(dubbed_path)
            new_seg_audio = AudioSegment.from_wav(stable_probni_path)
            
            start_ms = int(target_segment["start"] * 1000)
            
            # Uklanjamo stari glas u tom prozoru (postavljamo tišinu pomoću audio splicing-a)
            part1 = full_audio[:start_ms]
            part2 = AudioSegment.silent(duration=old_duration_ms)
            part3 = full_audio[start_ms + old_duration_ms:]
            full_audio = part1 + part2 + part3
            
            # Preklapamo novi generisani audio
            full_audio = full_audio.overlay(new_seg_audio, position=start_ms)
            full_audio.export(dubbed_path, format="wav")
            print(f"[API TTS] Dinamički osvežen segment-{segment_id} unutar punog miksa: {dubbed_path}", flush=True)
        except Exception as e:
            print(f"[WARNING] Neuspešno dinamičko osvežavanje punog miksa: {e}", flush=True)
            
    project_data["segments"] = segments
    r.set(f"project:{project_id}:draft", json.dumps(project_data), ex=604800)
    
    # Čistimo privremene fajlove nastale tokom ove izolovane sinteze
    if os.path.exists(generated_seg["path"]):
        os.remove(generated_seg["path"])
    if os.path.exists(tts_result["dubbed_audio_path"]):
        os.remove(tts_result["dubbed_audio_path"])
        
    return {
        "status": "success",
        "audio_url": f"/videos/{probni_filename}",
        "duration": generated_seg["duration"]
    }

@app.post("/api/v1/project/{project_id}/generate-all-tts")
def generate_all_tts(project_id: str, request: GenerateAllTTSRequest):
    """
    Sintetizuje glas za sve segmente u projektu i pravi kompletan miks (dubbed audio) za preslušavanje na timeline-u.
    """
    r = get_redis_client()
    draft_bytes = r.get(f"project:{project_id}:draft")
    if not draft_bytes:
        raise HTTPException(status_code=404, detail="Projekat nije pronađen ili je istekao.")
        
    project_data = json.loads(draft_bytes)
    segments = project_data["segments"]
    
    if not segments:
        raise HTTPException(status_code=400, detail="Projekat nema segmenata za sintezu.")
        
    # Formatiramo sve segmente za funkciju sinteze
    tts_segments = []
    for s in segments:
        tts_segments.append({
            "id": s["id"],
            "start": s["start"],
            "end": s["end"],
            "text": s["translated"],
            "original_text": s["original"],
            "voice_type": s.get("voice_type", request.voice_type)
        })
        
    print(f"[API TTS ALL] Pokrećem sintezu svih {len(tts_segments)} segmenata za projekat {project_id}")
    
    from backend.worker.tts_engine import synthesize_audio
    tts_result = synthesize_audio(
        project_data["vocals_path"],
        tts_segments,
        voice_type=request.voice_type,
        disable_openvoice=settings.DISABLE_OPENVOICE,
        disable_enhance=settings.DISABLE_ENHANCE,
        all_segments=segments
    )
    
    if tts_result["status"] == "error":
        raise HTTPException(status_code=500, detail=f"Sinteza celog videa nije uspela: {tts_result.get('message')}")
        
    res_segments = tts_result.get("tts_segments", [])
    res_map = {s["id"]: s for s in res_segments}
    
    # Učitavamo originalni vokal da bismo znali ukupnu dužinu i napravili finalni miks sa svim podešavanjima
    from pydub import AudioSegment
    try:
        ref_audio = AudioSegment.from_wav(project_data["vocals_path"])
        video_duration_ms = len(ref_audio)
    except Exception:
        video_duration_ms = 30000  # fallback 30s
    
    final_mix = AudioSegment.silent(duration=video_duration_ms)
    
    # Ažuriramo segmente u Redis nacrtu i gradimo novi finalni miks sa svim podešavanjima
    from backend.worker.utils import apply_audio_modifiers
    import shutil
    
    for s in segments:
        if s["id"] in res_map:
            res_s = res_map[s["id"]]
            
            # Kopiramo i pojedinačni segment u temp_workspace sa primenom modifikatora
            seg_filename = f"tts_seg_{project_id}_{s['id']}.wav"
            stable_seg_path = os.path.join(os.path.dirname(settings.TEMP_WORKSPACE), settings.TEMP_WORKSPACE, seg_filename)
            
            apply_audio_modifiers(
                res_s["path"],
                stable_seg_path,
                volume=s.get("volume", 0.0),
                speed=s.get("speed", 1.0),
                pitch=s.get("pitch", 0.0)
            )
            
            try:
                seg_audio = AudioSegment.from_wav(stable_seg_path)
                duration = len(seg_audio) / 1000.0
            except Exception:
                try:
                    seg_audio = AudioSegment.from_wav(res_s["path"])
                except Exception:
                    seg_audio = AudioSegment.silent(duration=int((s["end"] - s["start"]) * 1000))
                duration = res_s.get("duration", s["end"] - s["start"])
                
            s["tts_path"] = stable_seg_path
            s["tts_duration"] = duration
            s["status"] = "previewed"
            
            if os.path.exists(res_s["path"]):
                os.remove(res_s["path"])
                
        # Dodajemo segment u finalni miks ako postoji na disku
        if s.get("tts_path") and os.path.exists(s["tts_path"]):
            try:
                seg_audio = AudioSegment.from_wav(s["tts_path"])
                start_ms = int(s["start"] * 1000)
                final_mix = final_mix.overlay(seg_audio, position=start_ms)
            except Exception as e:
                print(f"[WARNING] Greška pri dodavanju segmenta {s['id']} u miks: {e}", flush=True)
                
    dubbed_filename = f"tts_full_{project_id}.wav"
    stable_dubbed_path = os.path.join(os.path.dirname(settings.TEMP_WORKSPACE), settings.TEMP_WORKSPACE, dubbed_filename)
    final_mix.export(stable_dubbed_path, format="wav")
                
    project_data["segments"] = segments
    project_data["dubbed_audio_path"] = stable_dubbed_path
    
    r.set(f"project:{project_id}:draft", json.dumps(project_data), ex=604800)
    
    # Čistimo privremeni dubbed fajl
    if os.path.exists(tts_result["dubbed_audio_path"]):
        os.remove(tts_result["dubbed_audio_path"])
        
    return {
        "status": "success",
        "dubbed_audio_url": f"/videos/{dubbed_filename}",
        "segments": segments
    }

@app.post("/api/v1/project/{project_id}/render")
def render_project(project_id: str, request: RenderRequest):
    """
    Pokreće drugu fazu (Render) sinhronizacije na Celery-ju.
    """
    from backend.worker.tasks import render_video_task
    print(f"--- [API RECEIVE] Pokrećem FAZU 2 (Render) za projekat: {project_id}", flush=True)
    task = render_video_task.delay(
        project_id, 
        request.voice_type, 
        request.background_volume, 
        request.dubbed_volume
    )
    return {
        "status": "success",
        "message": "Pokrenuto renderovanje finalnog videa.",
        "task_id": task.id
    }

# --- KRAJ NOVIH RUTA ---

# Legacy rute zadržane radi kompatibilnosti
@app.post("/api/v1/continue/{task_id}")
def continue_task(task_id: str):
    r = get_redis_client()
    r.set(f"task:{task_id}:continue", "true", ex=3600)
    return {"status": "success", "message": "Signal za nastavak poslat."}

@app.post("/api/v1/regenerate-tts/{task_id}")
def regenerate_tts(task_id: str):
    r = get_redis_client()
    r.set(f"task:{task_id}:continue", "regenerate", ex=3600)
    return {"status": "success", "message": "Zahtev za ponovno generisanje TTS-a poslat."}

@app.post("/api/v1/edit-segments/{task_id}")
def edit_segments(task_id: str, request: SaveProjectRequest):
    r = get_redis_client()
    r.set(f"task:{task_id}:edited_segments", json.dumps([s.dict() for s in request.segments]), ex=3600)
    return {"status": "success", "message": "Segmenti uspešno sačuvani."}

@app.post("/api/v1/mixer-settings/{task_id}")
def save_mixer_settings(task_id: str, request: MixerSettingsRequest):
    r = get_redis_client()
    r.set(f"task:{task_id}:mixer_settings", json.dumps({
        "background_volume": request.background_volume,
        "dubbed_volume": request.dubbed_volume
    }), ex=3600)
    return {"status": "success", "message": "Podešavanja miksera sačuvana."}

@app.get("/api/v1/status/{task_id}")
def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
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
async def warmup_workers():
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
                print(f"[WARMUP] Pingujem: {url}", flush=True)
                await client.get(url)
        except httpx.TimeoutException:
            print(f"[WARMUP] Ping timeout za {url} (ovo je očekivano i u redu).", flush=True)
        except Exception as e:
            print(f"[WARMUP] Ping izuzetak za {url}: {e} (cold start je verovatno okinut).", flush=True)

    for url in urls:
        asyncio.create_task(ping(url))
        
    return {"status": "success", "message": "Zahtevi za zagrevanje Modal radnika su poslati u pozadini."}

@app.get("/api/v1/modal-status")
def get_modal_global_status():
    return {
        "status": "Spreman",
        "active_workers": "Auto-Scale",
        "platform": "Modal.com",
        "timestamp": os.getpid()
    }

@app.get("/api/v1/hw-stats")
async def hw_stats():
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
        print(f"HW Stats Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/v1/logs")
def get_worker_logs():
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
