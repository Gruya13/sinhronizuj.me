from backend.worker.celery_app import celery_app
from backend.worker.downloader import download_video
from backend.core.config import settings
import os
import shutil
import json
import redis
import re
import time
import threading
from datetime import datetime, timedelta, timezone
import boto3
from botocore.config import Config
from backend.core.database import SessionLocal
from backend.core.models import Project, Segment

def upload_file_to_s3(file_path: str, bucket_name: str, object_key: str):
    if not os.path.exists(file_path):
        print(f"[S3 UPLOAD ERROR] Lokalni fajl ne postoji: {file_path}", flush=True)
        return False
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    try:
        s3_internal.upload_file(file_path, bucket_name, object_key)
        print(f"[S3 UPLOAD SUCCESS] Otpremljen {file_path} -> s3://{bucket_name}/{object_key}", flush=True)
        return True
    except Exception as e:
        print(f"[S3 UPLOAD ERROR] Greška pri otpremanju na S3: {e}", flush=True)
        return False

def download_file_from_s3(bucket_name: str, object_key: str, local_path: str):
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        s3_internal.download_file(bucket_name, object_key, local_path)
        print(f"[S3 DOWNLOAD SUCCESS] Preuzet s3://{bucket_name}/{object_key} -> {local_path}", flush=True)
        return True
    except Exception as e:
        print(f"[S3 DOWNLOAD ERROR] Greška pri preuzimanju sa S3: {e}", flush=True)
        return False

def get_redis_client():
    match = re.search(r'@([^:/]+)', settings.REDIS_URL)
    redis_host = match.group(1) if match else "redis"
    return redis.Redis(host=redis_host, password=settings.REDIS_PASSWORD, port=6379, db=0)

@celery_app.task(bind=True, name="analyze_video_task")
def analyze_video_task(self, video_url: str, debug: bool = False, project_id: str = None):
    print(f"--- [CELERY TASK] Započeta FAZA 1 (Analiza). Debug: {debug}, project_id: {project_id} ---", flush=True)
    r_client = get_redis_client()
    task_id = self.request.id
    effective_project_id = project_id if project_id else task_id

    # Uspostavljanje izolovanog radnog prostora za ovaj task
    original_temp_workspace = settings.TEMP_WORKSPACE
    task_workspace = os.path.join(original_temp_workspace, task_id)
    os.makedirs(task_workspace, exist_ok=True)
    settings.TEMP_WORKSPACE = task_workspace
    print(f"[CELERY TASK] Izolovani TEMP_WORKSPACE postavljen na: {settings.TEMP_WORKSPACE}", flush=True)

    progress_metadata = {
        'id': task_id,
        'current_step': "Inicijalizacija...",
        'percent': 0,
        'completed_steps': [],
        'segments': [],
        'detail': "Priprema radnog prostora...",
        'logs': [],
        'costs': {
            'phases': {},
            'total_usd': 0.0
        }
    }

    def add_phase_cost(phase_id, name, gpu, duration, rate):
        cost = duration * rate
        progress_metadata['costs']['phases'][phase_id] = {
            "name": name,
            "gpu": gpu,
            "duration_sec": round(duration, 2),
            "cost_usd": round(cost, 5)
        }
        total = sum(p["cost_usd"] for p in progress_metadata['costs']['phases'].values())
        progress_metadata['costs']['total_usd'] = round(total, 5)

    def update_progress(step_name=None, percentage=None, completed_step=None, segments=None, visual_context_url=None, detail=None):
        if step_name: progress_metadata['current_step'] = step_name
        if percentage is not None: progress_metadata['percent'] = percentage
        if completed_step: progress_metadata['completed_steps'].append(completed_step)
        if segments: progress_metadata['segments'] = segments
        if visual_context_url: progress_metadata['visual_context_url'] = visual_context_url
        if detail:
            progress_metadata['detail'] = detail
            ts = datetime.now().strftime("%H:%M:%S")
            progress_metadata['logs'].append(f"[{ts}] {detail}")
            if len(progress_metadata['logs']) > 20:
                progress_metadata['logs'] = progress_metadata['logs'][-20:]
        
        self.update_state(task_id=task_id, state='PROGRESS', meta=progress_metadata)

    vc_result = {}
    def run_vc_extraction(video_path):
        try:
            print("[BACKGROUND VC] Započinjem ekstrakciju frejmova u pozadini...", flush=True)
            from backend.worker.preprocessor import extract_visual_context, upload_to_minio
            t_start = time.time()
            preview_path = extract_visual_context(video_path)
            duration = time.time() - t_start
            url = None
            if preview_path:
                url = upload_to_minio(preview_path)
            vc_result["url"] = url
            vc_result["duration"] = duration
            print(f"[BACKGROUND VC] Ekstrakcija završena. URL: {url}, Trajanje: {duration:.2f}s", flush=True)
        except Exception as e:
            print(f"[BACKGROUND VC] Greška u pozadinskoj ekstrakciji: {e}", flush=True)
            vc_result["error"] = str(e)
            vc_result["url"] = None
            vc_result["duration"] = 0.0

    try:
        # --- KORAK 1: Preuzimanje ---
        update_progress("Preuzimanje videa...", 10, detail="Povezivanje sa izvorom i preuzimanje video zapisa...")
        result = download_video(video_url)
        if result["status"] == "error": 
            return result
        update_progress(completed_step="Preuzimanje završeno")
        
        # Pokrećemo ekstrakciju vizuelnog konteksta u pozadini
        vc_thread = threading.Thread(target=run_vc_extraction, args=(result["video_path"],))
        vc_thread.daemon = True
        vc_thread.start()
        
        # --- KORAK 2: Separacija Zvuka ---
        update_progress("Izolacija vokala...", 25, detail="Pokretanje Demucs modela na Modalu...")
        from backend.worker.audio_sep import separate_audio
        t_start_sep = time.time()
        sep_result = separate_audio(
            result['audio_path'],
            progress_callback=lambda detail: update_progress(detail=detail)
        )
        duration_sep = time.time() - t_start_sep
        if sep_result["status"] == "error": 
            return sep_result
        add_phase_cost("separation", "Izolacija vokala (Demucs)", "T4", duration_sep, 0.00018)
        update_progress(completed_step="Vokal izolovan")
        
        # Kopiramo vokal i no-vocal fajlove u privremeni direktorijum koji ostaje dostupan i nakon gašenja taska
        vocals_filename = f"vocals_{effective_project_id}.wav"
        no_vocals_filename = f"no_vocals_{effective_project_id}.wav"
        stable_vocals_path = os.path.join(original_temp_workspace, vocals_filename)
        stable_no_vocals_path = os.path.join(original_temp_workspace, no_vocals_filename)
        
        shutil.copy2(sep_result["vocals_path"], stable_vocals_path)
        shutil.copy2(sep_result["no_vocals_path"], stable_no_vocals_path)
        
        # --- KORAK 3: Transkripcija ---
        update_progress("Prepoznavanje govora (Whisper)...", 50, detail="Slanje vokalne trake na Modal Whisper...")
        
        video_title = result.get("title", "")
        video_tags = result.get("tags", [])
        prompt_keywords = []
        if video_title: prompt_keywords.append(video_title)
        if video_tags: prompt_keywords.extend(video_tags[:5])
        keywords_str = ", ".join([str(kw) for kw in prompt_keywords[:8]])
        
        initial_prompt = "This is a clear speech. Please use punctuation: dots, commas, and capital letters."
        if keywords_str:
            initial_prompt = f"This is a video about {keywords_str}. Please use correct punctuation: dots, commas, and capital letters. Spell names and technical terms correctly."
            
        from backend.worker.transcriber import transcribe_audio
        t_start_trans = time.time()
        transcription_result = transcribe_audio(
            stable_vocals_path,
            initial_prompt=initial_prompt,
            progress_callback=lambda detail: update_progress(detail=detail)
        )
        duration_trans = time.time() - t_start_trans
        if transcription_result["status"] == "error": 
            return transcription_result
        add_phase_cost("transcription", "Prepoznavanje govora (Whisper)", "T4", duration_trans, 0.00018)
        update_progress(completed_step="Govor prepoznat")
        
        # --- KORAK 4: Prevođenje & Lektura ---
        update_progress("Prevođenje (Modal + Multimodal)...", 75, detail="Čekam pozadinsku ekstrakciju slika...")
        
        if vc_thread.is_alive():
            vc_thread.join()
            
        visual_context_url = vc_result.get("url")
        duration_vc = vc_result.get("duration", 0.0)
        if visual_context_url:
            update_progress(visual_context_url=visual_context_url)
        add_phase_cost("visual_context", "Generisanje vizuelnog konteksta (Lokalno)", "Lokalni VPS", duration_vc, 0.0)
        
        update_progress("Prevođenje (Modal + Multimodal)...", 85, detail="Prevođenje i lektura teksta preko Qwen modela...")
        from backend.worker.translator import translate_segments
        
        # Kopiramo originalni video u stabilnu lokaciju
        video_filename = f"video_{effective_project_id}.mp4"
        stable_video_path = os.path.join(original_temp_workspace, video_filename)
        shutil.copy2(result["video_path"], stable_video_path)
        
        translation_result = translate_segments(
            transcription_result["segments"],
            video_path=stable_video_path,
            progress_callback=lambda detail: update_progress(detail=detail)
        )
        if translation_result["status"] == "error": 
            return translation_result
        
        metrics = translation_result.get("metrics", {})
        duration_translate = metrics.get("translator_duration", 0.0)
        duration_lektor = metrics.get("lektor_duration", 0.0)
        
        if duration_translate > 0:
            add_phase_cost("translation", "Prevođenje (Qwen-VL)", "A10G", duration_translate, 0.00033)
        if duration_lektor > 0:
            add_phase_cost("lektor", "Lektura teksta (Qwen 32B AWQ)", "A10G", duration_lektor, 0.00033)
            
        update_progress(completed_step="Prevedeno i lekturisano", percentage=85)
        
        # --- KORAK 5: Lokalna detekcija roda i govornika (diarizacija i ASD) ---
        update_progress("Diarizacija i vizuelna analiza...", 90, detail="Analiziram govornike i pokrete usana na ekranu...")
        
        from backend.worker.audio_gender import detect_gender_from_audio
        from backend.worker.active_speaker import is_speaker_active_on_screen
        
        processed_segments = []
        for i, s in enumerate(translation_result["translated_segments"]):
            update_progress(detail=f"Analiziram segment {i+1}/{len(translation_result['translated_segments'])}...")
            
            # Detektujemo rod iz audio trake
            gender = detect_gender_from_audio(stable_vocals_path, s["start"], s["end"])
            voice_type = "male" if gender == "male" else "clone"
            
            # Detektujemo da li se usne pomeraju na ekranu (aktivan govornik)
            is_active = is_speaker_active_on_screen(stable_video_path, s["start"], s["end"])
            
            processed_segments.append({
                "id": i,
                "start": s["start"],
                "end": s["end"],
                "original": s.get("original_text", ""),
                "translated": s["text"],
                "voice_type": voice_type,
                "active_speaker": is_active,
                "tts_path": None,
                "tts_duration": None,
                "status": "draft"
            })
            
        update_progress(completed_step="Diarizacija i vizuelna analiza završene", percentage=100)
            
        # Inicijalni naziv i kreiranje datuma za metapodatke
        created_at_val = datetime.now().isoformat()
        project_name = "Projekt " + effective_project_id[:8]
        
        if project_id:
            meta_bytes = r_client.hget("projects:metadata", project_id)
            if meta_bytes:
                meta = json.loads(meta_bytes)
                project_name = meta.get("name", project_name)
                created_at_val = meta.get("created_at", created_at_val)

        # --- SAČUVAJ PODATKE U POSTGRES I S3 ---
        video_key = f"projects/{effective_project_id}/video.mp4"
        vocals_key = f"projects/{effective_project_id}/vocals.wav"
        no_vocals_key = f"projects/{effective_project_id}/no_vocals.wav"
        visual_context_key = vc_result.get("key")
        
        update_progress(detail="Otpremanje originalnog videa na S3...")
        upload_file_to_s3(stable_video_path, settings.MINIO_BUCKET, video_key)
        
        update_progress(detail="Otpremanje izolovanog vokala na S3...")
        upload_file_to_s3(stable_vocals_path, settings.MINIO_BUCKET, vocals_key)
        
        update_progress(detail="Otpremanje pozadinske muzike na S3...")
        upload_file_to_s3(stable_no_vocals_path, settings.MINIO_BUCKET, no_vocals_key)
        
        # Čišćenje lokalnih fajlova sa diska radnika
        if os.path.exists(stable_video_path): os.remove(stable_video_path)
        if os.path.exists(stable_vocals_path): os.remove(stable_vocals_path)
        if os.path.exists(stable_no_vocals_path): os.remove(stable_no_vocals_path)
        
        db = SessionLocal()
        try:
            p_db = db.query(Project).filter(Project.id == effective_project_id).first()
            if p_db:
                p_db.video_s3_key = video_key
                p_db.vocals_s3_key = vocals_key
                p_db.no_vocals_s3_key = no_vocals_key
                p_db.visual_context_s3_key = visual_context_key
                p_db.video_title = video_title
                p_db.costs = progress_metadata["costs"]
                p_db.status = "ready"
                
                # Brišemo stare segmente pre kreiranja novih
                db.query(Segment).filter(Segment.project_id == effective_project_id).delete()
                
                for s in processed_segments:
                    db_seg = Segment(
                        project_id=effective_project_id,
                        segment_id=s["id"],
                        start=s["start"],
                        end=s["end"],
                        original=s["original"],
                        translated=s["translated"],
                        voice_type=s["voice_type"],
                        volume=0.0,
                        speed=1.0,
                        pitch=0.0,
                        bg_volume=0.0,
                        active_speaker=s["active_speaker"],
                        tts_s3_key=None,
                        tts_duration=None,
                        status="draft"
                    )
                    db.add(db_seg)
                db.commit()
                print(f"[CELERY TASK] Podaci uspešno upisani u PostgreSQL za projekat {effective_project_id}", flush=True)
            else:
                print(f"[CELERY TASK WARNING] Projekat {effective_project_id} nije pronađen u Postgres bazi podataka.", flush=True)
        except Exception as db_err:
            db.rollback()
            print(f"[CELERY TASK ERROR] Greška pri upisu u Postgres: {db_err}", flush=True)
            raise db_err
        finally:
            db.close()
            
        # Generišemo presigned URL-ove za Redis draft kompatibilnost
        from backend.main import get_presigned_download_url
        
        redis_segments = []
        for s in processed_segments:
            redis_segments.append({
                "id": s["id"],
                "start": s["start"],
                "end": s["end"],
                "original": s["original"],
                "translated": s["translated"],
                "voice_type": s["voice_type"],
                "active_speaker": s["active_speaker"],
                "tts_path": None,
                "tts_duration": None,
                "status": "draft"
            })
            
        draft_data = {
            "project_id": effective_project_id,
            "name": project_name,
            "video_url": get_presigned_download_url(settings.MINIO_BUCKET, video_key),
            "video_path": video_key,
            "vocals_path": vocals_key,
            "no_vocals_path": no_vocals_key,
            "no_vocals_url": get_presigned_download_url(settings.MINIO_BUCKET, no_vocals_key),
            "visual_context_url": visual_context_url,
            "title": video_title,
            "segments": redis_segments,
            "costs": progress_metadata["costs"],
            "status": "ready",
            "created_at": created_at_val
        }
        
        # Keširamo u Redisu
        r_client.set(f"project:{effective_project_id}:draft", json.dumps(draft_data), ex=604800)
        print(f"[CELERY TASK] Keširan draft u Redis: project:{effective_project_id}:draft", flush=True)
        
        # Ažuriramo metapodatke u projects:metadata HASH-u
        if project_id:
            meta_data = {
                "id": project_id,
                "name": project_name,
                "video_title": video_title or "Video",
                "status": "ready",
                "created_at": created_at_val
            }
            r_client.hset("projects:metadata", project_id, json.dumps(meta_data))
            
        return {
            "status": "success",
            "project_id": effective_project_id,
            "visual_context_url": visual_context_url,
            "segments": redis_segments,
            "costs": progress_metadata["costs"]
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
@celery_app.task(bind=True, name="render_video_task")
def render_video_task(self, project_id: str, voice_type: str = "clone", background_vol: float = -5.0, dubbed_vol: float = 0.0):
    print(f"--- [CELERY TASK] Započeta FAZA 2 (Render). Projekat: {project_id} ---", flush=True)
    r_client = get_redis_client()
    task_id = self.request.id
    
    # 1. Učitavamo projekat i segmente iz PostgreSQL-a da bismo bili potpuno stateless i ažurni
    db = SessionLocal()
    try:
        p_db = db.query(Project).filter(Project.id == project_id).first()
        if not p_db:
            return {"status": "error", "message": f"Projekat {project_id} nije pronađen u PostgreSQL-u."}
        
        project_name = p_db.name
        video_s3_key = p_db.video_s3_key
        vocals_s3_key = p_db.vocals_s3_key
        no_vocals_s3_key = p_db.no_vocals_s3_key
        visual_context_s3_key = p_db.visual_context_s3_key
        costs_val = p_db.costs or {"phases": {}, "total_usd": 0.0}
        created_at_val = p_db.created_at.isoformat() if p_db.created_at else ""
        video_title = p_db.video_title
        
        db_segments = db.query(Segment).filter(Segment.project_id == project_id).order_by(Segment.segment_id).all()
        segments = []
        for s in db_segments:
            segments.append({
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
                "tts_s3_key": s.tts_s3_key,
                "tts_duration": s.tts_duration,
                "status": s.status
            })
    finally:
        db.close()
        
    # Inicijalizujemo local workspace
    original_temp_workspace = settings.TEMP_WORKSPACE
    task_workspace = os.path.join(original_temp_workspace, task_id)
    os.makedirs(task_workspace, exist_ok=True)
    settings.TEMP_WORKSPACE = task_workspace
    
    progress_metadata = {
        'id': task_id,
        'current_step': "Učitavanje projekta...",
        'percent': 0,
        'completed_steps': [],
        'detail': "Priprema fajlova za renderovanje...",
        'logs': [],
        'costs': costs_val
    }
    
    def add_phase_cost(phase_id, name, gpu, duration, rate):
        cost = duration * rate
        progress_metadata['costs']['phases'][phase_id] = {
            "name": name,
            "gpu": gpu,
            "duration_sec": round(duration, 2),
            "cost_usd": round(cost, 5)
        }
        total = sum(p["cost_usd"] for p in progress_metadata['costs']['phases'].values())
        progress_metadata['costs']['total_usd'] = round(total, 5)
        
    def update_progress(step_name=None, percentage=None, completed_step=None, detail=None):
        if step_name: progress_metadata['current_step'] = step_name
        if percentage is not None: progress_metadata['percent'] = percentage
        if completed_step: progress_metadata['completed_steps'].append(completed_step)
        if detail:
            progress_metadata['detail'] = detail
            ts = datetime.now().strftime("%H:%M:%S")
            progress_metadata['logs'].append(f"[{ts}] {detail}")
            if len(progress_metadata['logs']) > 20:
                progress_metadata['logs'] = progress_metadata['logs'][-20:]
        self.update_state(task_id=task_id, state='PROGRESS', meta=progress_metadata)

    try:
        # --- PREUZIMANJE OSNOVNIH FAJLOVA SA S3 ---
        update_progress("Preuzimanje resursa...", 10, detail="Preuzimam originalni video i audio kanale sa S3...")
        local_video_path = os.path.join(task_workspace, "video.mp4")
        local_vocals_path = os.path.join(task_workspace, "vocals.wav")
        local_no_vocals_path = os.path.join(task_workspace, "no_vocals.wav")
        
        if not download_file_from_s3(settings.MINIO_BUCKET, video_s3_key, local_video_path):
            return {"status": "error", "message": "Preuzimanje video.mp4 sa S3 nije uspelo."}
        if not download_file_from_s3(settings.MINIO_BUCKET, vocals_s3_key, local_vocals_path):
            return {"status": "error", "message": "Preuzimanje vocals.wav sa S3 nije uspelo."}
        if not download_file_from_s3(settings.MINIO_BUCKET, no_vocals_s3_key, local_no_vocals_path):
            return {"status": "error", "message": "Preuzimanje no_vocals.wav sa S3 nije uspelo."}

        # --- KORAK 1: Sinteza Govora (TTS) ---
        update_progress("Sinteza govora...", 20, detail="Provera generisanih zvučnih fajlova...")
        
        missing_tts_segments = []
        
        # Proveravamo koji segmenti nemaju generisan audio i preuzimamo postojeće
        for s in segments:
            local_path = os.path.join(task_workspace, f"tts_seg_{s['id']}.wav")
            s["tts_path"] = local_path
            
            if s.get("tts_s3_key"):
                print(f"[RENDER] Preuzimam tts za segment {s['id']} sa S3...", flush=True)
                download_file_from_s3(settings.MINIO_BUCKET, s["tts_s3_key"], local_path)
                if not os.path.exists(local_path):
                    missing_tts_segments.append(s)
            else:
                missing_tts_segments.append(s)
                
        if missing_tts_segments:
            update_progress("Sinteza govora...", 30, detail=f"Sinteza preostalih {len(missing_tts_segments)} segmenata na Modalu...")
            from backend.worker.tts_engine import synthesize_audio
            
            # Formatiramo za synthesizer
            tts_input_segments = [{
                "id": s["id"],
                "start": s["start"],
                "end": s["end"],
                "text": s["translated"],
                "original_text": s["original"]
            } for s in missing_tts_segments]
            
            t_start_tts = time.time()
            tts_result = synthesize_audio(
                local_vocals_path,
                tts_input_segments,
                voice_type=voice_type,
                disable_openvoice=settings.DISABLE_OPENVOICE,
                disable_enhance=settings.DISABLE_ENHANCE,
                progress_callback=lambda detail: update_progress(detail=detail),
                all_segments=segments
            )
            duration_tts = time.time() - t_start_tts
            if tts_result["status"] == "error":
                return tts_result
                
            # Akumuliramo trošak
            existing_tts = progress_metadata['costs'].get("phases", {}).get("tts", {})
            existing_duration = existing_tts.get("duration_sec", 0.0)
            total_duration_tts = existing_duration + duration_tts
            add_phase_cost("tts", "Sinteza govora (OpenVoice)", "L4", total_duration_tts, 0.00025)
            
            # Ažuriramo putanje u našim segmentima i kopiramo ih u stabilnu lokaciju sa primenom modifikatora
            from backend.worker.utils import apply_audio_modifiers
            tts_map = {s["id"]: s for s in tts_result["tts_segments"]}
            
            db = SessionLocal()
            try:
                for s in segments:
                    if s["id"] in tts_map:
                        res_seg = tts_map[s["id"]]
                        local_raw_path = res_seg["path"]
                        local_processed_path = os.path.join(task_workspace, f"tts_seg_processed_{s['id']}.wav")
                        
                        apply_audio_modifiers(
                            local_raw_path,
                            local_processed_path,
                            volume=s.get("volume", 0.0),
                            speed=s.get("speed", 1.0),
                            pitch=s.get("pitch", 0.0)
                        )
                        
                        # Provera novog trajanja posle modifikatora
                        try:
                            from pydub import AudioSegment
                            updated_audio = AudioSegment.from_wav(local_processed_path)
                            actual_duration = len(updated_audio) / 1000.0
                        except Exception:
                            actual_duration = res_seg["duration"]
                            
                        # Upload na S3
                        tts_s3_key = f"projects/{project_id}/tts_seg_{s['id']}.wav"
                        upload_file_to_s3(local_processed_path, settings.MINIO_BUCKET, tts_s3_key)
                        
                        if os.path.exists(local_raw_path):
                            os.remove(local_raw_path)
                            
                        s["tts_path"] = local_processed_path
                        s["tts_duration"] = actual_duration
                        s["tts_s3_key"] = tts_s3_key
                        
                        # Ažuriranje u PostgreSQL
                        db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == s["id"]).first()
                        if db_seg:
                            db_seg.tts_s3_key = tts_s3_key
                            db_seg.tts_duration = actual_duration
                db.commit()
            except Exception as db_err:
                db.rollback()
                print(f"[RENDER ERROR] Greška pri upisu TTS-a u bazu: {db_err}", flush=True)
                raise db_err
            finally:
                db.close()
                
            if "dubbed_audio_path" in tts_result and os.path.exists(tts_result["dubbed_audio_path"]):
                os.remove(tts_result["dubbed_audio_path"])
            
        update_progress(completed_step="Svi vokali sintetizovani")
        
        # --- KORAK 2: FFmpeg merger i Dynamic Time Stretching ---
        update_progress("Finalni miks (FFmpeg)...", 60, detail="Dynamic time stretching i miksovanje zvuka...")
        
        # Formiramo tts_segments listu za merger
        merger_segments = [{
            "id": s["id"],
            "path": s["tts_path"],
            "duration": s["tts_duration"],
            "start": s["start"],
            "end": s["end"],
            "bg_volume": s.get("bg_volume", 0.0)
        } for s in segments]
        
        from backend.worker.merger import merge_audio_and_video_dynamic
        t_start_merge = time.time()
        
        merge_result = merge_audio_and_video_dynamic(
            local_video_path,
            local_no_vocals_path,
            merger_segments,
            background_vol=background_vol,
            dubbed_vol=dubbed_vol
        )
        duration_merge = time.time() - t_start_merge
        if merge_result["status"] == "error":
            return merge_result
            
        add_phase_cost("merger", "Audio-video miksovanje (Lokalno)", "Lokalni VPS", duration_merge, 0.0)
        update_progress(completed_step="Miks završen")
        
        # --- KORAK 3: Lip Sync ---
        update_progress("Lip Sync sinhronizacija...", 80, detail="Analiza i pokretanje Wav2Lip-a...")
        from backend.worker.lipsync import has_sufficient_faces, apply_selective_lip_sync
        
        t_start_lip = time.time()
        needs_lipsync = has_sufficient_faces(merge_result["final_video_path"], threshold_percentage=10.0)
        
        if needs_lipsync:
            update_progress("Lip Sync sinhronizacija...", 85, detail="Usklađivanje usana govornika (Wav2Lip)...")
            lip_vocals_path = merge_result["dubbed_audio_path"]
            lip_result = apply_selective_lip_sync(merge_result["final_video_path"], lip_vocals_path, segments)
            final_output = lip_result["lipsync_video_path"] if lip_result["status"] != "error" else merge_result["final_video_path"]
        else:
            final_output = merge_result["final_video_path"]
            
        duration_lip = time.time() - t_start_lip
        if needs_lipsync:
            add_phase_cost("lipsync", "Lip Sync sinhronizacija (Wav2Lip)", "Lokalni VPS", duration_lip, 0.0)
        else:
            add_phase_cost("lipsync", "Lip Sync preskočen (nema lica)", "Lokalni VPS", duration_lip, 0.0)
            
        update_progress(completed_step="Renderovanje završeno", percentage=95)
        
        # --- OTPREMANJE FINALNOG VIDEA NA S3 ---
        final_video_s3_key = f"projects/{project_id}/final_video.mp4"
        update_progress("Otpremanje finalnog videa...", 98, detail="Slanje gotovog video zapisa na S3...")
        if not upload_file_to_s3(final_output, settings.MINIO_BUCKET, final_video_s3_key):
            return {"status": "error", "message": "Otpremanje finalnog videa na S3 nije uspelo."}
            
        # Ažuriramo status projekta u bazi podataka
        db = SessionLocal()
        try:
            p_db = db.query(Project).filter(Project.id == project_id).first()
            if p_db:
                p_db.final_video_s3_key = final_video_s3_key
                p_db.status = "completed"
                p_db.costs = progress_metadata["costs"]
                db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"[RENDER ERROR] Greška pri upisu finalnog statusa u bazu: {db_err}", flush=True)
            raise db_err
        finally:
            db.close()
            
        # Obrišemo lokalne privremene audio/video fajlove
        if os.path.exists(final_output):
            os.remove(final_output)
            
        update_progress(completed_step="Renderovanje završeno", percentage=100)
        
        # Generišemo presigned URL za status kompatibilnost
        from backend.main import get_presigned_download_url
        final_presigned_url = get_presigned_download_url(settings.MINIO_BUCKET, final_video_s3_key)
        
        # Sinhronizujemo Redis draft za unazadnu kompatibilnost
        project_data = {
            "project_id": project_id,
            "name": project_name,
            "video_url": get_presigned_download_url(settings.MINIO_BUCKET, video_s3_key),
            "video_path": video_s3_key,
            "vocals_path": vocals_s3_key,
            "no_vocals_path": no_vocals_s3_key,
            "no_vocals_url": get_presigned_download_url(settings.MINIO_BUCKET, no_vocals_s3_key),
            "visual_context_url": get_presigned_download_url("previews", visual_context_s3_key) if visual_context_s3_key else "",
            "title": video_title,
            "segments": segments,
            "costs": progress_metadata["costs"],
            "status": "completed",
            "final_video_url": final_presigned_url,
            "created_at": created_at_val
        }
        r_client.set(f"project:{project_id}:draft", json.dumps(project_data), ex=604800)
        
        # Ažuriramo status projekta u metapodacima u Redisu
        meta_bytes = r_client.hget("projects:metadata", project_id)
        if meta_bytes:
            meta = json.loads(meta_bytes)
            meta["status"] = "completed"
            r_client.hset("projects:metadata", project_id, json.dumps(meta))
        
        return {
            "status": "completed",
            "project_id": project_id,
            "video_url": final_presigned_url,
            "costs": progress_metadata["costs"]
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Vraćamo status u metapodacima na 'ready' kako bi korisnik mogao opet pokrenuti render
        try:
            meta_bytes = r_client.hget("projects:metadata", project_id)
            if meta_bytes:
                meta = json.loads(meta_bytes)
                meta["status"] = "ready"
                r_client.hset("projects:metadata", project_id, json.dumps(meta))
        except:
            pass
        return {"status": "error", "message": str(e)}
    finally:
        # Vraćamo originalni workspace i čistimo render folder
        settings.TEMP_WORKSPACE = original_temp_workspace
        if os.path.exists(task_workspace):
            shutil.rmtree(task_workspace, ignore_errors=True)

# Definišemo legacy celery task radi kompatibilnosti, ali on sada interno poziva Fazu 1 i Fazu 2 za redom
@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, video_url: str, debug: bool = False):
    """
    Legacy task koji automatski radi i analizu i render (1-pass) bez prekidanja,
    kako ne bismo pokvarili stare testove i fallback mehanizme.
    """
    print("--- [LEGACY 1-PASS TASK] Pokrećem automatsku sinhronizaciju u jednom prolazu ---", flush=True)
    task_id = self.request.id
    
    # 1. Pokrećemo analizu
    analysis_res = analyze_video_task(self, video_url, debug)
    if analysis_res.get("status") == "error":
        return analysis_res
        
    # 2. Pokrećemo render sa podrazumevanim parametrima
    render_res = render_video_task(self, task_id, voice_type="clone", background_vol=-5.0, dubbed_vol=0.0)
    return render_res

@celery_app.task(name="backend.worker.tasks.cleanup_old_files")
def cleanup_old_files():
    """
    Zadatak 3: Periodično čišćenje starih fajlova (starijih od 24h) sa S3 i lokalnog diska.
    """
    import boto3
    print(f"[CLEANUP] Pokrećem čišćenje starih fajlova: {datetime.now()}")
    
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY
        )
        
        buckets = ['uploads', 'processed', 'input-audio']
        threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        
        for bucket in buckets:
            print(f"[CLEANUP] Proveravam bucket: {bucket}")
            try:
                objects = s3.list_objects_v2(Bucket=bucket)
                if 'Contents' in objects:
                    for obj in objects['Contents']:
                        if obj['LastModified'] < threshold:
                            print(f"[CLEANUP] Brišem {obj['Key']} iz {bucket}")
                            s3.delete_object(Bucket=bucket, Key=obj['Key'])
            except Exception as e:
                print(f"[CLEANUP] Bucket {bucket} nije dostupan ili je prazan: {e}")
                
    except Exception as e:
        print(f"[CLEANUP] S3 klijent greška: {e}")

    local_temp = "/app/temp_workspace"
    if os.path.exists(local_temp):
        threshold_ts = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
        for item in os.listdir(local_temp):
            item_path = os.path.join(local_temp, item)
            try:
                mtime = os.path.getmtime(item_path)
                if mtime < threshold_ts:
                    if os.path.isdir(item_path):
                        print(f"[CLEANUP] Brišem lokalni folder: {item_path}")
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        print(f"[CLEANUP] Brišem lokalni fajl: {item_path}")
                        os.remove(item_path)
            except Exception as e:
                print(f"[CLEANUP] Greška pri brisanju {item_path}: {e}")
