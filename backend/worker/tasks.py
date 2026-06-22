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
import hashlib

import numpy as np

class NumpySafeEncoder(json.JSONEncoder):
    """JSON encoder koji automatski konvertuje numpy tipove u Python native tipove."""
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

def sanitize_for_json(obj):
    """Rekurzivno konvertuje SVE numpy tipove u Python native tipove.
    Koristi se pre upisa u SQLAlchemy JSON kolone i Redis jer
    SQLAlchemy i Celery koriste sopstveni json.dumps koji ne zna za numpy."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

def safe_json_dumps(obj, **kwargs):
    """json.dumps wrapper koji bezbedno serijalizuje numpy tipove."""
    return json.dumps(sanitize_for_json(obj), **kwargs)

from datetime import datetime, timedelta, timezone
import boto3
from botocore.config import Config
from backend.core.database import SessionLocal
from backend.core.models import Project, Segment, Job

def get_file_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_sha256_of_data(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def check_s3_file_exists(bucket_name: str, object_key: str) -> bool:
    s3_internal = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name=settings.S3_REGION
    )
    try:
        s3_internal.head_object(Bucket=bucket_name, Key=object_key)
        return True
    except Exception:
        return False

def create_or_update_job(project_id: str, job_type: str, status: str, current_phase: str = None, attempt: int = None, artifact_keys: dict = None, error_code: str = None, error_message: str = None, job_id: str = None):
    db = SessionLocal()
    try:
        import uuid
        job = None
        if job_id:
            try:
                job_uuid = uuid.UUID(job_id)
                job = db.query(Job).filter(Job.id == job_uuid).first()
            except ValueError:
                pass
        if not job:
            try:
                project_uuid = uuid.UUID(project_id)
                job = db.query(Job).filter(Job.project_id == project_uuid, Job.type == job_type).order_by(Job.created_at.desc()).first()
            except ValueError:
                pass
            
        if not job:
            job = Job(
                id=uuid.UUID(job_id) if job_id else uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                type=job_type,
                status=status,
                current_phase=current_phase,
                attempt=attempt or 1,
                current_artifact_keys=artifact_keys or {},
                error_code=error_code,
                error_message=error_message
            )
            db.add(job)
        else:
            job.status = status
            if current_phase:
                job.current_phase = current_phase
            if attempt is not None:
                job.attempt = attempt
            if artifact_keys:
                existing_keys = job.current_artifact_keys or {}
                existing_keys.update(artifact_keys)
                job.current_artifact_keys = existing_keys
            if error_code is not None:
                job.error_code = error_code
            if error_message is not None:
                job.error_message = error_message
                
        db.commit()
        return str(job.id)
    except Exception as e:
        db.rollback()
        print(f"[STATE MACHINE ERROR] Greška pri ažuriranju posla u bazi: {e}", flush=True)
        return job_id
    finally:
        db.close()

def handle_task_failure(self, exc, task_id, args, kwargs, einfo):
    print(f"[CELERY FAILURE HANDLER] Task {self.name} failed. Task ID: {task_id}. Exc: {exc}", flush=True)
    project_id = None
    if self.name == "analyze_video_task":
        project_id = kwargs.get("project_id") or (args[2] if len(args) > 2 else task_id)
    elif self.name == "render_video_task":
        project_id = kwargs.get("project_id") or (args[0] if len(args) > 0 else None)
    elif self.name == "process_video_task":
        project_id = task_id
        
    if project_id:
        create_or_update_job(
            project_id=project_id,
            job_type="analysis" if self.name == "analyze_video_task" else ("render" if self.name == "render_video_task" else "dubbing"),
            status="failed",
            error_code=type(exc).__name__,
            error_message=str(exc)
        )
        
    try:
        r_client = get_redis_client()
        dlq_payload = {
            "task_id": task_id,
            "task_name": self.name,
            "args": [str(a) for a in args],
            "kwargs": {k: str(v) for k, v in kwargs.items()},
            "exception": type(exc).__name__,
            "error_message": str(exc),
            "traceback": einfo.traceback if einfo else "",
            "failed_at": datetime.now(timezone.utc).isoformat()
        }
        r_client.rpush("dead_letter_queue", json.dumps(dlq_payload))
        print(f"[DLQ] Uspešno poslata poruka u dead_letter_queue za task {task_id}", flush=True)
    except Exception as redis_err:
        print(f"[DLQ ERROR] Greška pri slanju u Redis DLQ: {redis_err}", flush=True)

def handle_task_success(self, retval, task_id, args, kwargs):
    print(f"[CELERY SUCCESS HANDLER] Task {self.name} completed successfully. Task ID: {task_id}", flush=True)
    project_id = None
    if self.name == "analyze_video_task":
        project_id = kwargs.get("project_id") or (args[2] if len(args) > 2 else task_id)
    elif self.name == "render_video_task":
        project_id = kwargs.get("project_id") or (args[0] if len(args) > 0 else None)
    elif self.name == "process_video_task":
        project_id = task_id
        
    if project_id:
        create_or_update_job(
            project_id=project_id,
            job_type="analysis" if self.name == "analyze_video_task" else ("render" if self.name == "render_video_task" else "dubbing"),
            status="completed"
        )

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
        region_name=settings.S3_REGION
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
        region_name=settings.S3_REGION
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
    return redis.Redis.from_url(settings.REDIS_URL)

@celery_app.task(
    name="translate_segments_chunk_task",
    acks_late=True,
    time_limit=600
)
def translate_segments_chunk_task(segments: list, video_path: str, user_avg_speedup: float, skip_lektor: bool, skip_gating: bool, skip_deduplication: bool, project_id: str):
    from backend.worker.translator import translate_segments
    return translate_segments(
        segments=segments,
        video_path=video_path,
        progress_callback=None,
        user_avg_speedup=user_avg_speedup,
        skip_lektor=skip_lektor,
        skip_gating=skip_gating,
        skip_deduplication=skip_deduplication,
        project_id=project_id
    )

@celery_app.task(
    bind=True,
    name="analyze_video_task",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    time_limit=2400,
    soft_time_limit=2300,
    on_failure=handle_task_failure,
    on_success=handle_task_success
)
def analyze_video_task(self, video_url: str, debug: bool = False, project_id: str = None):
    print(f"--- [CELERY TASK] Započeta FAZA 1 (Analiza). Debug: {debug}, project_id: {project_id} ---", flush=True)
    r_client = get_redis_client()
    task_id = self.request.id
    effective_project_id = project_id if project_id else task_id
    
    # Inicijalizacija stanja u Job tabeli
    attempt_num = self.request.retries + 1
    create_or_update_job(
        project_id=effective_project_id,
        job_type="analysis",
        status="running",
        current_phase="downloading",
        attempt=attempt_num,
        job_id=task_id
    )

    # Uspostavljanje izolovanog radnog prostora za ovaj task
    task_workspace = os.path.join(settings.TEMP_WORKSPACE, task_id)
    os.makedirs(task_workspace, exist_ok=True)
    print(f"[CELERY TASK] Izolovani task_workspace kreiran na: {task_workspace}", flush=True)

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
        cost = float(duration) * float(rate)
        progress_metadata['costs']['phases'][phase_id] = {
            "name": name,
            "gpu": gpu,
            "duration_sec": round(float(duration), 2),
            "cost_usd": round(float(cost), 5)
        }
        total = sum(p["cost_usd"] for p in progress_metadata['costs']['phases'].values())
        progress_metadata['costs']['total_usd'] = round(float(total), 5)

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
            preview_path = extract_visual_context(video_path, workspace_path=task_workspace)
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
        result = download_video(video_url, workspace_path=task_workspace)
        if result["status"] == "error": 
            return result
        update_progress(completed_step="Preuzimanje završeno")
        
        # Izračunavanje hash-a preuzetog fajla
        video_hash = get_file_sha256(result["video_path"])
        audio_hash = get_file_sha256(result["audio_path"])
        
        # Pokrećemo ekstrakciju vizuelnog konteksta u pozadini
        vc_thread = threading.Thread(target=run_vc_extraction, args=(result["video_path"],))
        vc_thread.daemon = True
        vc_thread.start()
        
        # --- KORAK 2: Separacija Zvuka ---
        create_or_update_job(project_id=effective_project_id, job_type="analysis", status="running", current_phase="separating", job_id=task_id)
        update_progress("Izolacija vokala...", 25, detail="Provera keša za izolaciju vokala...")
        
        vocals_cache_key = f"cache/separation/{audio_hash}_vocals.wav"
        no_vocals_cache_key = f"cache/separation/{audio_hash}_no_vocals.wav"
        
        vocals_filename = f"vocals_{effective_project_id}.wav"
        no_vocals_filename = f"no_vocals_{effective_project_id}.wav"
        stable_vocals_path = os.path.join(task_workspace, vocals_filename)
        stable_no_vocals_path = os.path.join(task_workspace, no_vocals_filename)
        
        if check_s3_file_exists(settings.MINIO_BUCKET, vocals_cache_key) and check_s3_file_exists(settings.MINIO_BUCKET, no_vocals_cache_key):
            print("[CACHE HIT] Separacija vokala pronađena u kešu na S3. Preuzimam...", flush=True)
            update_progress("Izolacija vokala...", 25, detail="Preuzimam izolovani vokal iz keša...")
            download_file_from_s3(settings.MINIO_BUCKET, vocals_cache_key, stable_vocals_path)
            download_file_from_s3(settings.MINIO_BUCKET, no_vocals_cache_key, stable_no_vocals_path)
            add_phase_cost("separation", "Izolacija vokala (Keširano)", "Nema GPU", 0.0, 0.0)
        else:
            from backend.worker.audio_sep import separate_audio
            t_start_sep = time.time()
            sep_result = separate_audio(
                result['audio_path'],
                progress_callback=lambda detail: update_progress(detail=detail),
                workspace_path=task_workspace
            )
            duration_sep = time.time() - t_start_sep
            if sep_result["status"] == "error": 
                return sep_result
            add_phase_cost("separation", "Izolacija vokala (Demucs)", "T4", duration_sep, 0.00018)
            
            # Kopiramo u stabilnu lokaciju
            shutil.copy2(sep_result["vocals_path"], stable_vocals_path)
            shutil.copy2(sep_result["no_vocals_path"], stable_no_vocals_path)
            
            # Otpremamo u keš na S3
            upload_file_to_s3(stable_vocals_path, settings.MINIO_BUCKET, vocals_cache_key)
            upload_file_to_s3(stable_no_vocals_path, settings.MINIO_BUCKET, no_vocals_cache_key)
            
        update_progress(completed_step="Vokal izolovan")
        
        # Zabeležimo intermedijalni rezultat u Job tabeli
        create_or_update_job(
            project_id=effective_project_id,
            job_type="analysis",
            status="running",
            artifact_keys={"vocals_s3_key": vocals_cache_key, "no_vocals_s3_key": no_vocals_cache_key},
            job_id=task_id
        )
        
        # --- KORAK 3: Transkripcija ---
        create_or_update_job(project_id=effective_project_id, job_type="analysis", status="running", current_phase="transcribing", job_id=task_id)
        update_progress("Prepoznavanje govora (Whisper)...", 50, detail="Provera keša za transkripciju...")
        
        video_title = result.get("title", "")
        video_tags = result.get("tags", [])
        prompt_keywords = []
        if video_title: prompt_keywords.append(video_title)
        if video_tags: prompt_keywords.extend(video_tags[:5])
        keywords_str = ", ".join([str(kw) for kw in prompt_keywords[:8]])
        
        initial_prompt = "This is a clear speech. Please use punctuation: dots, commas, and capital letters."
        if keywords_str:
            initial_prompt = f"This is a video about {keywords_str}. Please use correct punctuation: dots, commas, and capital letters. Spell names and technical terms correctly."
            
        vocals_hash = get_file_sha256(stable_vocals_path)
        transcription_hash = get_sha256_of_data(vocals_hash + initial_prompt)
        trans_cache_key = f"cache/transcription/{transcription_hash}.json"
        
        transcription_result = None
        if check_s3_file_exists(settings.MINIO_BUCKET, trans_cache_key):
            print("[CACHE HIT] Transkripcija pronađena u kešu na S3. Preuzimam...", flush=True)
            update_progress("Prepoznavanje govora (Whisper)...", 50, detail="Preuzimam transkripciju iz keša...")
            local_trans_path = os.path.join(task_workspace, "trans_cache.json")
            if download_file_from_s3(settings.MINIO_BUCKET, trans_cache_key, local_trans_path):
                with open(local_trans_path, "r", encoding="utf-8") as f:
                    transcription_result = json.load(f)
                add_phase_cost("transcription", "Prepoznavanje govora (Keširano)", "Nema GPU", 0.0, 0.0)
                
        if not transcription_result:
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
            
            # Otpremamo u keš na S3
            local_trans_path = os.path.join(task_workspace, "trans_cache.json")
            with open(local_trans_path, "w", encoding="utf-8") as f:
                json.dump(transcription_result, f, ensure_ascii=False)
            upload_file_to_s3(local_trans_path, settings.MINIO_BUCKET, trans_cache_key)
            if os.path.exists(local_trans_path):
                os.remove(local_trans_path)
                
        update_progress(completed_step="Govor prepoznat")
        create_or_update_job(
            project_id=effective_project_id,
            job_type="analysis",
            status="running",
            artifact_keys={"transcription_s3_key": trans_cache_key},
            job_id=task_id
        )
        
        # --- KORAK 4: Prevođenje & Lektura ---
        create_or_update_job(project_id=effective_project_id, job_type="analysis", status="running", current_phase="translating", job_id=task_id)
        update_progress("Prevođenje (Modal + Multimodal)...", 75, detail="Čekam pozadinsku ekstrakciju slika...")
        
        if vc_thread.is_alive():
            vc_thread.join()
            
        visual_context_url = vc_result.get("url")
        duration_vc = vc_result.get("duration", 0.0)
        if visual_context_url:
            update_progress(visual_context_url=visual_context_url)
        add_phase_cost("visual_context", "Generisanje vizuelnog konteksta (Lokalno)", "Lokalni VPS", duration_vc, 0.0)
        
        # Kopiramo originalni video u stabilnu lokaciju
        video_filename = f"video_{effective_project_id}.mp4"
        stable_video_path = os.path.join(task_workspace, video_filename)
        shutil.copy2(result["video_path"], stable_video_path)
        
        from backend.worker.segment_optimizer import optimize_segments_for_translation
        optimized_segments = optimize_segments_for_translation(transcription_result["segments"])
        
        # Provera keša za prevod
        video_hash = get_file_sha256(stable_video_path)
        translation_hash = get_sha256_of_data(safe_json_dumps(optimized_segments) + video_hash)
        translation_cache_key = f"cache/translation/{translation_hash}.json"
        
        translation_result = None
        if check_s3_file_exists(settings.MINIO_BUCKET, translation_cache_key):
            print("[CACHE HIT] Prevod pronađen u kešu na S3. Preuzimam...", flush=True)
            update_progress("Prevođenje (Modal + Multimodal)...", 85, detail="Preuzimam prevod iz keša...")
            local_trans_path = os.path.join(task_workspace, "translation_cache.json")
            if download_file_from_s3(settings.MINIO_BUCKET, translation_cache_key, local_trans_path):
                with open(local_trans_path, "r", encoding="utf-8") as f:
                    translation_result = json.load(f)
                add_phase_cost("translation", "Prevođenje (Keširano)", "Nema GPU", 0.0, 0.0)
                
        if not translation_result:
            update_progress("Prevođenje (Modal + Multimodal)...", 85, detail="Prevođenje i lektura teksta preko Qwen modela...")
            
            # Celery Paralelizacija (Chunking) na osnovu tišine
            split_indices = None
            if len(optimized_segments) >= 6:
                try:
                    start_time = optimized_segments[0]["start"]
                    end_time = optimized_segments[-1]["end"]
                    total_duration = end_time - start_time
                    
                    t1 = start_time + total_duration / 3.0
                    t2 = start_time + 2.0 * total_duration / 3.0
                    
                    # Prozor pretrage oko 1/3 i 2/3 (npr. 1/6 trajanja sa svake strane)
                    w = total_duration / 6.0
                    
                    best_i = -1
                    max_gap1 = -1.0
                    
                    best_j = -1
                    max_gap2 = -1.0
                    
                    for idx_s in range(len(optimized_segments) - 1):
                        seg_end = optimized_segments[idx_s]["end"]
                        next_start = optimized_segments[idx_s+1]["start"]
                        gap = next_start - seg_end
                        
                        if t1 - w <= seg_end <= t1 + w:
                            if gap > max_gap1:
                                max_gap1 = gap
                                best_i = idx_s
                                
                        if t2 - w <= seg_end <= t2 + w:
                            if gap > max_gap2:
                                max_gap2 = gap
                                best_j = idx_s
                                
                    if best_i != -1 and best_j != -1 and best_i < best_j:
                        split_indices = (best_i, best_j)
                        print(f"[CHUNKING] Pronađeni split markeri: segmenti {best_i} i {best_j} (pauze: {max_gap1:.2f}s i {max_gap2:.2f}s)", flush=True)
                except Exception as e:
                    print(f"[CHUNKING WARNING] Greška pri računanju split markera: {e}", flush=True)

            # Izvršavanje prevoda
            if split_indices:
                try:
                    idx1, idx2 = split_indices
                    chunk1 = optimized_segments[:idx1+1]
                    chunk2 = optimized_segments[idx1+1:idx2+1]
                    chunk3 = optimized_segments[idx2+1:]
                    
                    print(f"[CHUNKING] Pokrećem 3 paralelna Celery zadatka za chunks veličina: {len(chunk1)}, {len(chunk2)}, {len(chunk3)}", flush=True)
                    
                    from celery import group
                    job = group(
                        translate_segments_chunk_task.s(
                            chunk1, stable_video_path, 1.0, False, False, False, project_id
                        ),
                        translate_segments_chunk_task.s(
                            chunk2, stable_video_path, 1.0, False, False, False, project_id
                        ),
                        translate_segments_chunk_task.s(
                            chunk3, stable_video_path, 1.0, False, False, False, project_id
                        )
                    )
                    
                    res_group = job.apply_async()
                    group_outputs = res_group.get(timeout=600)
                    
                    merged_segments = []
                    total_trans_dur = 0.0
                    total_lek_dur = 0.0
                    
                    for out in group_outputs:
                        if out.get("status") == "error":
                            raise Exception(f"Pod-zadatak prevođenja vratio grešku: {out.get('message')}")
                        merged_segments.extend(out.get("translated_segments", []))
                        metrics = out.get("metrics", {})
                        total_trans_dur += metrics.get("translator_duration", 0.0)
                        total_lek_dur += metrics.get("lektor_duration", 0.0)
                    
                    merged_segments = sorted(merged_segments, key=lambda x: x["id"])
                    
                    translation_result = {
                        "status": "success",
                        "translated_segments": merged_segments,
                        "metrics": {
                            "translator_duration": total_trans_dur,
                            "lektor_duration": total_lek_dur
                        }
                    }
                    print(f"[CHUNKING SUCCESS] Uspešno spojen prevod. Ukupno segmenata: {len(merged_segments)}", flush=True)
                except Exception as e:
                    print(f"[CHUNKING ERROR] Greška u paralelnoj obradi, radim fallback na sekvencijalnu obradu: {e}", flush=True)
                    translation_result = None

            if not translation_result:
                from backend.worker.translator import translate_segments
                translation_result = translate_segments(
                    optimized_segments,
                    video_path=stable_video_path,
                    progress_callback=lambda detail: update_progress(detail=detail),
                    project_id=project_id
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
                
            # Otpremamo u keš na S3
            local_trans_path = os.path.join(task_workspace, "translation_cache.json")
            with open(local_trans_path, "w", encoding="utf-8") as f:
                f.write(safe_json_dumps(translation_result, ensure_ascii=False))
            upload_file_to_s3(local_trans_path, settings.MINIO_BUCKET, translation_cache_key)
            if os.path.exists(local_trans_path):
                os.remove(local_trans_path)
                
        update_progress(completed_step="Prevedeno i lekturisano", percentage=85)
        create_or_update_job(
            project_id=effective_project_id,
            job_type="analysis",
            status="running",
            artifact_keys={"translation_s3_key": translation_cache_key},
            job_id=task_id
        )
        
        # --- KORAK 5: Lokalna detekcija roda i govornika (diarizacija i ASD) ---
        create_or_update_job(project_id=effective_project_id, job_type="analysis", status="running", current_phase="diarizing", job_id=task_id)
        update_progress("Diarizacija i vizuelna analiza...", 90, detail="Analiziram pokrete usana na celom ekranu (skeniranje)...")
        
        from backend.worker.audio_gender import detect_gender_from_audio
        from backend.worker.active_speaker import precompute_active_speakers, check_speaker_activity_from_timeline
        
        # Precompute aktivnih govornika sekvencijalno za ceo video (veoma brzo)
        t_asd_start = time.time()
        asd_timeline = precompute_active_speakers(stable_video_path)
        duration_asd = time.time() - t_asd_start
        print(f"[ACTIVE SPEAKER] Skeniranje usana završeno za {duration_asd:.2f}s. Ukupno frejmova: {len(asd_timeline)}", flush=True)
        
        processed_segments = []
        for i, s in enumerate(translation_result["translated_segments"]):
            update_progress(detail=f"Analiziram segment {i+1}/{len(translation_result['translated_segments'])}...")
            
            # Detektujemo rod iz audio trake
            gender = detect_gender_from_audio(stable_vocals_path, s["start"], s["end"])
            voice_type = "male" if gender == "male" else "clone"
            
            # Proveravamo aktivnost govornika iz precomputovanog timeline-a
            is_active = check_speaker_activity_from_timeline(asd_timeline, s["start"], s["end"])
            
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
                "status": "draft",
                "qe_score": float(s.get("qe_score")) if s.get("qe_score") is not None else None,
                "confidence_score": int(s.get("confidence_score", 5))
            })
            
        update_progress(completed_step="Diarizacija i vizuelna analiza završene", percentage=100)
        create_or_update_job(project_id=effective_project_id, job_type="analysis", status="running", current_phase="ready", job_id=task_id)
            
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
                p_db.costs = sanitize_for_json(progress_metadata["costs"])
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
                        status="draft",
                        confidence_score=int(s.get("confidence_score", 5)),
                        qe_score=float(s.get("qe_score")) if s.get("qe_score") is not None else None
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
                "status": "draft",
                "confidence_score": int(s.get("confidence_score", 5)),
                "qe_score": float(s.get("qe_score")) if s.get("qe_score") is not None else None
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
        r_client.set(f"project:{effective_project_id}:draft", safe_json_dumps(draft_data), ex=604800)
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
            r_client.hset("projects:metadata", project_id, safe_json_dumps(meta_data))
            
        return sanitize_for_json({
            "status": "success",
            "project_id": effective_project_id,
            "visual_context_url": visual_context_url,
            "segments": redis_segments,
            "costs": progress_metadata["costs"]
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(task_workspace):
            shutil.rmtree(task_workspace, ignore_errors=True)
@celery_app.task(
    bind=True,
    name="render_video_task",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    time_limit=1800,
    soft_time_limit=1700,
    on_failure=handle_task_failure,
    on_success=handle_task_success
)
def render_video_task(self, project_id: str, voice_type: str = "clone", background_vol: float = -5.0, dubbed_vol: float = 0.0):
    print(f"--- [CELERY TASK] Započeta FAZA 2 (Render). Projekat: {project_id} ---", flush=True)
    r_client = get_redis_client()
    task_id = self.request.id
    
    # Inicijalizacija stanja u Job tabeli
    attempt_num = self.request.retries + 1
    create_or_update_job(
        project_id=project_id,
        job_type="render",
        status="running",
        current_phase="tts",
        attempt=attempt_num,
        job_id=task_id
    )

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
    task_workspace = os.path.join(settings.TEMP_WORKSPACE, task_id)
    os.makedirs(task_workspace, exist_ok=True)
    
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
        
        # Proveravamo koji segmenti nemaju generisan audio i preuzimamo postojeće (projekat-specifične ili iz globalnog keša)
        for s in segments:
            local_path = os.path.join(task_workspace, f"tts_seg_{s['id']}.wav")
            s["tts_path"] = local_path
            
            if s.get("tts_s3_key"):
                print(f"[RENDER] Preuzimam tts za segment {s['id']} sa S3...", flush=True)
                download_file_from_s3(settings.MINIO_BUCKET, s["tts_s3_key"], local_path)
                if not os.path.exists(local_path):
                    missing_tts_segments.append(s)
            else:
                # Provera globalnog keša na osnovu teksta i modifikatora
                text = s.get("translated", "") or ""
                v_type = s.get("voice_type", "clone")
                vol = s.get("volume", 0.0)
                spd = s.get("speed", 1.0)
                ptc = s.get("pitch", 0.0)
                tts_data_str = f"{text}|{v_type}|{vol:.2f}|{spd:.2f}|{ptc:.2f}"
                tts_hash = get_sha256_of_data(tts_data_str)
                tts_cache_key = f"cache/tts/{tts_hash}.wav"
                
                if check_s3_file_exists(settings.MINIO_BUCKET, tts_cache_key):
                    print(f"[CACHE HIT] Pronađen TTS za segment {s['id']} u kešu S3. Preuzimam...", flush=True)
                    if download_file_from_s3(settings.MINIO_BUCKET, tts_cache_key, local_path):
                        s["tts_s3_key"] = tts_cache_key
                        # Izmerimo trajanje
                        try:
                            from pydub import AudioSegment
                            aud = AudioSegment.from_wav(local_path)
                            s["tts_duration"] = len(aud) / 1000.0
                        except Exception:
                            s["tts_duration"] = s.get("end", 0.0) - s.get("start", 0.0)
                            
                        # Ažuriramo u bazi podataka odmah
                        db = SessionLocal()
                        try:
                            db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == s["id"]).first()
                            if db_seg:
                                db_seg.tts_s3_key = tts_cache_key
                                db_seg.tts_duration = s["tts_duration"]
                                db.commit()
                        except Exception:
                            db.rollback()
                        finally:
                            db.close()
                    else:
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
                all_segments=segments,
                workspace_path=task_workspace
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
                            
                        # Upload na S3 (projekat-specifičan)
                        tts_s3_key = f"projects/{project_id}/tts_seg_{s['id']}.wav"
                        upload_file_to_s3(local_processed_path, settings.MINIO_BUCKET, tts_s3_key)
                        
                        # Upload na S3 (globalni keš)
                        text = s.get("translated", "") or ""
                        v_type = s.get("voice_type", "clone")
                        vol = s.get("volume", 0.0)
                        spd = s.get("speed", 1.0)
                        ptc = s.get("pitch", 0.0)
                        tts_data_str = f"{text}|{v_type}|{vol:.2f}|{spd:.2f}|{ptc:.2f}"
                        tts_hash = get_sha256_of_data(tts_data_str)
                        tts_cache_key = f"cache/tts/{tts_hash}.wav"
                        upload_file_to_s3(local_processed_path, settings.MINIO_BUCKET, tts_cache_key)
                        
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
            
           # --- KORAK 2: FFmpeg merger i Dynamic Time Stretching ---
        create_or_update_job(project_id=project_id, job_type="render", status="running", current_phase="mixing", job_id=task_id)
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
            dubbed_vol=dubbed_vol,
            workspace_path=task_workspace
        )
        duration_merge = time.time() - t_start_merge
        if merge_result["status"] == "error":
            return merge_result
        
        # --- FEEDBACK PETLJA POREĐENJA BRZINA GOVORA ---
        # Računamo prosečan istorijski speedup korisnika za potrebe kalibracije limita
        db = SessionLocal()
        user_avg_speedup = 1.0
        try:
            proj_obj = db.query(Project).filter(Project.id == project_id).first()
            if proj_obj:
                user_id = proj_obj.user_id
                from sqlalchemy import func
                avg_val = db.query(func.avg(Segment.actual_speed_factor))\
                            .join(Project)\
                            .filter(Project.user_id == user_id, Segment.actual_speed_factor > 1.0)\
                            .scalar()
                if avg_val is not None:
                    user_avg_speedup = float(avg_val)
        except Exception as e:
            print(f"[WARNING] Greška pri dobijanju prosečnog speedup-a za korisnika: {e}", flush=True)
        finally:
            db.close()

        speech_speedups = merge_result.get("speech_speedups", {})
        problem_ids = []
        for s_id, speedup in speech_speedups.items():
            if speedup > 1.15:
                problem_ids.append((s_id, speedup))
                
        # Pokrećemo re-translation samo ako ima problema i ako nismo već odradili retranslation u ovom tasku
        if problem_ids and not locals().get("retranslation_done", False):
            print(f"[FEEDBACK LOOP] Detektovano {len(problem_ids)} segmenata sa brzinom preko 1.15x: {problem_ids}", flush=True)
            
            db = SessionLocal()
            try:
                # 1. Upisujemo needs_retranslation i actual_speed_factor u bazu
                for s_id, speedup in problem_ids:
                    db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == s_id).first()
                    if db_seg:
                        db_seg.needs_retranslation = True
                        db_seg.actual_speed_factor = speedup
                db.commit()
                
                # 2. Re-prevedemo oštećene segmente sa strožim vremenskim limitima
                db_segs_to_retranslate = db.query(Segment).filter(Segment.project_id == project_id, Segment.needs_retranslation == True).all()
                segments_to_retranslate = []
                for s in db_segs_to_retranslate:
                    segments_to_retranslate.append({
                        "id": s.segment_id,
                        "start": s.start,
                        "end": s.end,
                        "text": s.original,
                        "speed": s.speed,
                        "voice_type": s.voice_type,
                        "actual_speed_factor": s.actual_speed_factor
                    })
                
                if segments_to_retranslate:
                    print(f"[FEEDBACK LOOP] Pokrećem re-prevođenje za {len(segments_to_retranslate)} segmenata sa faktorom {user_avg_speedup:.2f}...", flush=True)
                    from backend.worker.translator import translate_segments
                    
                    retrans_res = translate_segments(
                        segments_to_retranslate,
                        video_path=local_video_path,
                        progress_callback=None,
                        user_avg_speedup=user_avg_speedup,
                        project_id=project_id
                    )
                    
                    if retrans_res["status"] != "error":
                        # Ažuriramo prevode u bazi i resetujemo flagove
                        for s_res in retrans_res["translated_segments"]:
                            db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == s_res["id"]).first()
                            if db_seg:
                                db_seg.translated = s_res["text"]
                                db_seg.needs_retranslation = False
                                db_seg.confidence_score = s_res.get("confidence_score", 5)
                        db.commit()
                        
                        # 3. Regenerišemo TTS samo za te re-prevedene segmente
                        print("[FEEDBACK LOOP] Ponovo generišem TTS za re-prevedene segmente...", flush=True)
                        db_segs_to_tts = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id.in_([s["id"] for s in segments_to_retranslate])).all()
                        
                        from backend.worker.tts_engine import synthesize_audio
                        from backend.worker.utils import apply_audio_modifiers
                        
                        tts_list = [{
                            "id": s.segment_id,
                            "start": s.start,
                            "end": s.end,
                            "text": s.translated,
                            "original_text": s.original
                        } for s in db_segs_to_tts]
                        
                        all_segs_db = db.query(Segment).filter(Segment.project_id == project_id).all()
                        
                        tts_result = synthesize_audio(
                            local_vocals_path,
                            tts_list,
                            voice_type=voice_type,
                            disable_openvoice=settings.DISABLE_OPENVOICE,
                            disable_enhance=settings.DISABLE_ENHANCE,
                            all_segments=[{"id": s.segment_id, "start": s.start, "end": s.end, "original": s.original, "translated": s.translated} for s in all_segs_db],
                            workspace_path=task_workspace
                        )
                        
                        if tts_result["status"] != "error":
                            for res_seg in tts_result.get("tts_segments", []):
                                local_raw_path = res_seg["path"]
                                db_seg = db.query(Segment).filter(Segment.project_id == project_id, Segment.segment_id == res_seg["id"]).first()
                                if db_seg:
                                    local_processed_path = local_raw_path.replace(".wav", "_processed.wav")
                                    apply_audio_modifiers(
                                        local_raw_path,
                                        local_processed_path,
                                        volume=db_seg.volume,
                                        speed=db_seg.speed,
                                        pitch=db_seg.pitch
                                    )
                                    tts_s3_key = f"projects/{project_id}/tts_seg_{res_seg['id']}.wav"
                                    upload_file_to_s3(local_processed_path, settings.MINIO_BUCKET, tts_s3_key)
                                    
                                    if os.path.exists(local_raw_path):
                                        os.remove(local_raw_path)
                                    
                                    db_seg.tts_s3_key = tts_s3_key
                                    
                                    from pydub import AudioSegment
                                    try:
                                        aud = AudioSegment.from_wav(local_processed_path)
                                        db_seg.tts_duration = len(aud) / 1000.0
                                    except Exception:
                                        db_seg.tts_duration = res_seg["duration"]
                                        
                                    for mem_seg in segments:
                                        if mem_seg["id"] == res_seg["id"]:
                                            mem_seg["tts_path"] = local_processed_path
                                            mem_seg["tts_duration"] = db_seg.tts_duration
                                            break
                            db.commit()
                            
                            # 4. Ponovo pokrećemo FFmpeg merger sa novim kraćim audio zapisima
                            print("[FEEDBACK LOOP] Ponovo pokrećem dynamic time stretching sa novim audio zapisima...", flush=True)
                            re_merger_segments = [{
                                "id": s["id"],
                                "path": s["tts_path"],
                                "duration": s["tts_duration"],
                                "start": s["start"],
                                "end": s["end"],
                                "bg_volume": s.get("bg_volume", 0.0)
                            } for s in segments]
                            
                            if os.path.exists(merge_result["final_video_path"]):
                                os.remove(merge_result["final_video_path"])
                            if os.path.exists(merge_result["dubbed_audio_path"]):
                                os.remove(merge_result["dubbed_audio_path"])
                                
                            merge_result = merge_audio_and_video_dynamic(
                                local_video_path,
                                local_no_vocals_path,
                                re_merger_segments,
                                background_vol=background_vol,
                                dubbed_vol=dubbed_vol,
                                workspace_path=task_workspace
                            )
                            if merge_result["status"] == "error":
                                return merge_result
                                
                            retranslation_done = True
                            print("[FEEDBACK LOOP] Automatska optimizacija završena!", flush=True)
            except Exception as loop_err:
                db.rollback()
                print(f"[FEEDBACK LOOP ERROR] Greška tokom automatske optimizacije: {loop_err}", flush=True)
            finally:
                db.close()
                
        add_phase_cost("merger", "Audio-video miksovanje (Lokalno)", "Lokalni VPS", duration_merge, 0.0)
        update_progress(completed_step="Miks završen")
        
        # --- KORAK 3: Lip Sync ---
        create_or_update_job(project_id=project_id, job_type="render", status="running", current_phase="lipsyncing", job_id=task_id)
        update_progress("Lip Sync sinhronizacija...", 80, detail="Analiza i pokretanje Wav2Lip-a...")
        from backend.worker.lipsync import has_sufficient_faces, apply_selective_lip_sync
        
        t_start_lip = time.time()
        needs_lipsync = has_sufficient_faces(merge_result["final_video_path"], threshold_percentage=10.0)
        
        if needs_lipsync:
            update_progress("Lip Sync sinhronizacija...", 85, detail="Usklađivanje usana govornika (Wav2Lip)...")
            lip_vocals_path = merge_result["dubbed_audio_path"]
            lip_result = apply_selective_lip_sync(merge_result["final_video_path"], lip_vocals_path, segments, workspace_path=task_workspace)
            final_output = lip_result["lipsync_video_path"] if lip_result["status"] != "error" else merge_result["final_video_path"]
        else:
            final_output = merge_result["final_video_path"]
            
        provider = lip_result.get("provider", "local") if 'lip_result' in locals() else "skipped"
        duration_lip = time.time() - t_start_lip
        if needs_lipsync:
            if provider == "modal":
                add_phase_cost("lipsync", "Lip Sync sinhronizacija (Wav2Lip na Modalu)", "T4", duration_lip, 0.00018)
            else:
                add_phase_cost("lipsync", "Lip Sync sinhronizacija (Lokalni fallback)", "Lokalni VPS", duration_lip, 0.0)
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
        r_client.set(f"project:{project_id}:draft", safe_json_dumps(project_data), ex=604800)
        
        # Ažuriramo status projekta u metapodacima u Redisu
        meta_bytes = r_client.hget("projects:metadata", project_id)
        if meta_bytes:
            meta = json.loads(meta_bytes)
            meta["status"] = "completed"
            r_client.hset("projects:metadata", project_id, safe_json_dumps(meta))
            
        # Ažuriranje završne faze u Job tabeli
        create_or_update_job(
            project_id=project_id,
            job_type="render",
            status="completed",
            current_phase="completed",
            artifact_keys={"final_video_s3_key": final_video_s3_key},
            job_id=task_id
        )
        
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
                r_client.hset("projects:metadata", project_id, safe_json_dumps(meta))
        except:
            pass
        return {"status": "error", "message": str(e)}
    finally:
        # Čistimo render folder
        if os.path.exists(task_workspace):
            shutil.rmtree(task_workspace, ignore_errors=True)
 
# Definišemo legacy celery task radi kompatibilnosti, ali on sada interno poziva Fazu 1 i Fazu 2 za redom
@celery_app.task(
    bind=True,
    name="process_video_task",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    time_limit=2400,
    soft_time_limit=2300,
    on_failure=handle_task_failure,
    on_success=handle_task_success
)
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


@celery_app.task(name="learn_user_glossary_task")
def learn_user_glossary_task(user_id: str, original: str, old_translated: str, new_translated: str):
    """
    Pozadinski Celery task koji poredi stari i novi prevod i uči korisničke preferencije
    tako što ih automatski dodaje u korisnički glosar.
    """
    if not settings.MODAL_LEKTOR_URL:
        return
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "Korisnik je ručno ispravio prevod rečenice u našoj aplikaciji za sinhronizaciju videa.\n"
        "Tvoj zadatak je da utvrdiš da li je korisnik ispravio prevod nekog specifičnog stručnog pojma ili termina, "
        "i da izvučeš taj par (originalni engleski pojam i korisnikov novi srpski prevod).\n\n"
        f"Originalni engleski tekst: \"{original}\"\n"
        f"Prethodni automatski prevod: \"{old_translated}\"\n"
        f"Novi ručno korigovani prevod: \"{new_translated}\"\n\n"
        "PRAVILA ZA EKSTRAKCIJU:\n"
        "1. Ako je korisnik samo preformulisao rečenicu (npr. promenio red reči, promenio rod/padež bez promene prevoda ključnih reči), vrati prazan rečnik {}.\n"
        "2. Ako je korisnik promenio prevod neke konkretne engleske imenice, fraze ili stručnog termina (npr. promenio 'welding machine' sa 'mašina za varenje' na 'aparat za zavarivanje'), izvuci taj termin.\n"
        "3. Srpski prevod u rečniku treba da bude u svom osnovnom obliku (nominativ), ako je moguće.\n\n"
        "Odgovori isključivo u validnom JSON formatu kao jednostavan rečnik gde su ključevi engleske reči, a vrednosti srpski prevodi, bez ikakvog dodatnog teksta ili uvoda:\n"
        "{\n"
        "  \"english term\": \"serbian translation\"\n"
        "}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 150
    }
    
    try:
        from backend.worker.utils import call_modal_endpoint
        from backend.core.database import SessionLocal
        from backend.core.models import Glossary, TranslationMemory
        from backend.services.embedding import embedding_service
        import json
        
        res = call_modal_endpoint(url=url, payload=payload)
        content = res["choices"][0]["message"]["content"].strip()
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL).strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
            
        data = json.loads(content)
        if isinstance(data, dict) and data:
            db = SessionLocal()
            try:
                # 1. Učenje pojedinačnih reči za glosar
                for eng, srb in data.items():
                    if not eng or not srb:
                        continue
                    eng_clean = eng.strip().lower()
                    srb_clean = srb.strip().lower()
                    
                    existing = db.query(Glossary).filter(
                        Glossary.user_id == user_id,
                        Glossary.source_word == eng_clean
                    ).first()
                    
                    if existing:
                        existing.target_word = srb_clean
                    else:
                        new_g = Glossary(
                            user_id=user_id,
                            source_word=eng_clean,
                            target_word=srb_clean
                        )
                        db.add(new_g)
                
                # 2. Učenje cele rečenice u Translation Memory (RAG)
                emb = embedding_service.get_embedding(original)
                if emb:
                    existing_tm = db.query(TranslationMemory).filter(
                        TranslationMemory.user_id == user_id,
                        TranslationMemory.source_text == original
                    ).first()
                    
                    if existing_tm:
                        existing_tm.target_text = new_translated
                        existing_tm.embedding = emb
                    else:
                        new_tm = TranslationMemory(
                            user_id=user_id,
                            source_text=original,
                            target_text=new_translated,
                            embedding=emb
                        )
                        db.add(new_tm)
                    print(f"[RAG LEARNING] Uspešno naučena rečenica u TM za korisnika {user_id}", flush=True)

                db.commit()
                print(f"[CROSS-PROJECT LEARNING] Uspešno naučeni termini za korisnika {user_id}: {data}", flush=True)
            except Exception as e:
                db.rollback()
                print(f"[CROSS-PROJECT LEARNING ERROR] {e}", flush=True)
            finally:
                db.close()
    except Exception as e:
        print(f"[CROSS-PROJECT LEARNING ERROR] Greška pri pozivu LLM-a: {e}", flush=True)

@celery_app.task(name="learn_user_glossary_batch_task")
def learn_user_glossary_batch_task(user_id: str, corrections: list):
    """
    Pozadinski Celery task koji prima listu korekcija (dict sa keys: original, old_translated, new_translated)
    i uči korisničke preferencije u jednom batch pozivu ka LLM-u.
    """
    if not settings.MODAL_LEKTOR_URL or not corrections:
        return
        
    # Formiramo prompt za sve korekcije odjednom
    corrections_str = ""
    for idx, c in enumerate(corrections):
        corrections_str += (
            f"KOREKCIJA #{idx+1}:\n"
            f"Originalni engleski tekst: \"{c.get('original', '')}\"\n"
            f"Prethodni automatski prevod: \"{c.get('old_translated', '')}\"\n"
            f"Novi ručno korigovani prevod: \"{c.get('new_translated', '')}\"\n\n"
        )
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "Korisnik je ručno ispravio prevode rečenica u našoj aplikaciji za sinhronizaciju videa.\n"
        "Tvoj zadatak je da za svaku korekciju utvrdiš da li je korisnik ispravio prevod nekog specifičnog stručnog pojma ili termina, "
        "i da izvučeš te parove (originalni engleski pojam i korisnikov novi srpski prevod).\n\n"
        f"{corrections_str}"
        "PRAVILA ZA EKSTRAKCIJU:\n"
        "1. Ako je korisnik samo preformulisao rečenicu (npr. promenio red reči, promenio rod/padež bez promene prevoda ključnih reči), preskoči i ne dodaj u izlaz.\n"
        "2. Ako je korisnik promenio prevod neke konkretne engleske imenice, fraze ili stručnog termina (npr. promenio 'welding machine' sa 'mašina za varenje' na 'aparat za zavarivanje'), izvuci taj termin.\n"
        "3. Srpski prevod u rečniku treba da bude u svom osnovnom obliku (nominativ), ako je moguće.\n\n"
        "Odgovori isključivo u validnom JSON formatu kao jednostavan rečnik gde su ključevi engleske reči, a vrednosti srpski prevodi, bez ikakvog dodatnog teksta ili uvoda:\n"
        "{\n"
        "  \"english term\": \"serbian translation\"\n"
        "}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500
    }
    
    try:
        from backend.worker.utils import call_modal_endpoint
        from backend.core.database import SessionLocal
        from backend.core.models import Glossary, TranslationMemory
        from backend.services.embedding import embedding_service
        import json
        
        res = call_modal_endpoint(url=url, payload=payload)
        content = res["choices"][0]["message"]["content"].strip()
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL).strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
            
        data = json.loads(content)
        if isinstance(data, dict) and data:
            db = SessionLocal()
            try:
                # 1. Učenje pojedinačnih reči za glosar
                for eng, srb in data.items():
                    if not eng or not srb:
                        continue
                    eng_clean = eng.strip().lower()
                    srb_clean = srb.strip().lower()
                    
                    existing = db.query(Glossary).filter(
                        Glossary.user_id == user_id,
                        Glossary.source_word == eng_clean
                    ).first()
                    
                    if existing:
                        existing.target_word = srb_clean
                    else:
                        new_g = Glossary(
                            user_id=user_id,
                            source_word=eng_clean,
                            target_word=srb_clean
                        )
                        db.add(new_g)
                        
                # 2. Učenje celih segmenata za Translation Memory (RAG)
                for c in corrections:
                    original = c.get('original', '')
                    new_translated = c.get('new_translated', '')
                    if not original or not new_translated:
                        continue
                    emb = embedding_service.get_embedding(original)
                    if emb:
                        existing_tm = db.query(TranslationMemory).filter(
                            TranslationMemory.user_id == user_id,
                            TranslationMemory.source_text == original
                        ).first()
                        
                        if existing_tm:
                            existing_tm.target_text = new_translated
                            existing_tm.embedding = emb
                        else:
                            new_tm = TranslationMemory(
                                user_id=user_id,
                                source_text=original,
                                target_text=new_translated,
                                embedding=emb
                            )
                            db.add(new_tm)
                            
                db.commit()
                print(f"[CROSS-PROJECT BATCH LEARNING] Uspešno naučeni termini za korisnika {user_id}: {data}", flush=True)
            except Exception as e:
                db.rollback()
                print(f"[CROSS-PROJECT BATCH LEARNING ERROR] {e}", flush=True)
            finally:
                db.close()
    except Exception as e:
        print(f"[CROSS-PROJECT BATCH LEARNING ERROR] Greška pri pozivu LLM-a: {e}", flush=True)

@celery_app.task(
    name="promote_pending_tm_task",
    acks_late=True,
    time_limit=1800
)
def promote_pending_tm_task():
    from backend.core.database import SessionLocal
    from backend.core.models import TranslationMemory, PendingTranslationMemory
    from backend.services.embedding import embedding_service
    from sqlalchemy import func

    db = SessionLocal()
    try:
        pending_groups = db.query(
            PendingTranslationMemory.user_id,
            PendingTranslationMemory.source_text,
            func.max(PendingTranslationMemory.target_text).label("target_text"),
            func.max(PendingTranslationMemory.project_id).label("project_id"),
            func.sum(PendingTranslationMemory.occurrence_count).label("total_occurrence")
        ).group_by(
            PendingTranslationMemory.user_id,
            PendingTranslationMemory.source_text
        ).having(
            func.sum(PendingTranslationMemory.occurrence_count) >= 2
        ).all()

        promoted_count = 0
        for group in pending_groups:
            user_id = group.user_id
            source_text = group.source_text
            target_text = group.target_text
            project_id = group.project_id

            exists = db.query(TranslationMemory).filter(
                TranslationMemory.user_id == user_id,
                TranslationMemory.source_text == source_text
            ).first()

            if not exists:
                emb = embedding_service.get_embedding(source_text)
                tm_entry = TranslationMemory(
                    user_id=user_id,
                    project_id=project_id,
                    source_text=source_text,
                    target_text=target_text,
                    embedding=emb,
                    auto_approved=True
                )
                db.add(tm_entry)
                promoted_count += 1
                print(f"[ALPHA] Promovišem '{source_text}' -> '{target_text}' u glavnu TM tabelu za korisnika {user_id}", flush=True)
            
            db.query(PendingTranslationMemory).filter(
                PendingTranslationMemory.user_id == user_id,
                PendingTranslationMemory.source_text == source_text
            ).delete()

        db.commit()
        print(f"[ALPHA SUCCESS] promote_pending_tm_task završen. Promovisano: {promoted_count}", flush=True)
        return {"status": "success", "promoted_count": promoted_count}
    except Exception as e:
        db.rollback()
        print(f"[ALPHA ERROR] Greška u promote_pending_tm_task: {e}", flush=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

@celery_app.task(
    name="run_nightly_pattern_analysis_task",
    acks_late=True,
    time_limit=3600
)
def run_nightly_pattern_analysis_task():
    from backend.worker.translation.pattern_miner import run_nightly_pattern_analysis
    return run_nightly_pattern_analysis()

@celery_app.task(
    name="deploy_lora_task",
    acks_late=True,
    time_limit=14400
)
def deploy_lora_task(dry_run: bool = False, user_id: str = None):
    from backend.worker.training.data_generator import run_data_generation
    from backend.worker.training.train_lora import run_lora_training
    import redis

    print(f"[BLUE-GREEN DEPLOY] Započinjem proces generisanja podataka i LoRA finetuning-a (dry_run={dry_run}, user_id={user_id})...", flush=True)
    
    data_res = run_data_generation(user_id=user_id)
    if data_res.get("status") != "success":
        print(f"[BLUE-GREEN DEPLOY ERROR] Generisanje podataka nije uspelo: {data_res.get('message')}", flush=True)
        return data_res

    if data_res.get("examples_generated", 0) == 0:
        print("[BLUE-GREEN DEPLOY] Nema dovoljno primera za trening. Preskačem finetuning.", flush=True)
        return {"status": "success", "message": "Nema primera za trening."}

    train_res = run_lora_training(dry_run=dry_run)
    if train_res.get("status") != "success":
        print(f"[BLUE-GREEN DEPLOY ERROR] Trening nije uspeo: {train_res.get('message')}", flush=True)
        return train_res

    adapter_dir = train_res.get("adapter_dir", "/models/qwen3-32b-lora")
    try:
        r_client = redis.Redis.from_url(settings.REDIS_URL)
        r_client.set("active_lora_path", adapter_dir)
        print(f"[BLUE-GREEN DEPLOY SUCCESS] Novi adapter uspešno postavljen u Redis active_lora_path: {adapter_dir}", flush=True)
        return {"status": "success", "active_lora_path": adapter_dir}
    except Exception as redis_err:
        print(f"[BLUE-GREEN DEPLOY ERROR] Greška pri upisu u Redis: {redis_err}", flush=True)
        return {"status": "error", "message": f"Greška pri upisu u Redis: {redis_err}"}

def refresh_project_draft(project_id: str, db: SessionLocal):
    import uuid
    from backend.main import get_presigned_download_url
    
    project_uuid = uuid.UUID(project_id) if isinstance(project_id, str) else project_id
    p = db.query(Project).filter(Project.id == project_uuid).first()
    if not p:
        return
        
    db_segments = db.query(Segment).filter(Segment.project_id == project_uuid).order_by(Segment.segment_id).all()
    
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
        "video_path": p.video_s3_key,
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
    
    r_client = get_redis_client()
    r_client.set(f"project:{project_id}:draft", safe_json_dumps(project_data), ex=604800)

@celery_app.task(
    bind=True,
    name="generate_segment_tts_task",
    acks_late=True,
    time_limit=300
)
def generate_segment_tts_task(self, project_id: str, segment_id: int, text: str, voice_type: str, volume: float, speed: float, pitch: float, bg_volume: float):
    print(f"--- [CELERY TASK] Započeta asinhrona sinteza segmenta {segment_id} za projekat {project_id} ---", flush=True)
    task_id = self.request.id
    db = SessionLocal()
    
    task_workspace = os.path.join(settings.TEMP_WORKSPACE, task_id)
    os.makedirs(task_workspace, exist_ok=True)
    
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name=settings.S3_REGION
    )
    
    try:
        import uuid
        project_uuid = uuid.UUID(project_id)
        p = db.query(Project).filter(Project.id == project_uuid).first()
        if not p:
            return {"status": "error", "message": "Projekat nije pronađen."}
            
        db_seg = db.query(Segment).filter(Segment.project_id == project_uuid, Segment.segment_id == segment_id).first()
        if not db_seg:
            return {"status": "error", "message": "Segment nije pronađen."}
            
        old_tts_duration = db_seg.tts_duration or (db_seg.end - db_seg.start)
            
        probni_filename = f"tts_probni_{project_id}_{segment_id}.wav"
        stable_probni_path = os.path.join(task_workspace, probni_filename)
        
        raw_filename = f"tts_raw_{project_id}_{segment_id}.wav"
        stable_raw_path = os.path.join(task_workspace, raw_filename)
        
        from backend.worker.utils import apply_audio_modifiers
        from pydub import AudioSegment
        
        is_fast_adjust = (
            db_seg.translated == text and 
            db_seg.voice_type == voice_type
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
                volume=volume,
                speed=speed,
                pitch=pitch
            )
            try:
                updated_audio = AudioSegment.from_wav(stable_probni_path)
                actual_duration = len(updated_audio) / 1000.0
            except Exception:
                actual_duration = db_seg.tts_duration or (db_seg.end - db_seg.start)
        else:
            local_vocals_path = os.path.join(task_workspace, f"vocals_temp_{project_id}.wav")
            if not os.path.exists(local_vocals_path) and p.vocals_s3_key:
                try:
                    s3.download_file(settings.MINIO_BUCKET, p.vocals_s3_key, local_vocals_path)
                except Exception as e:
                    return {"status": "error", "message": f"Greška pri preuzimanju vokala sa S3: {e}"}
                    
            db_segs = db.query(Segment).filter(Segment.project_id == project_uuid).order_by(Segment.segment_id).all()
            segments_list_dicts = [{"id": s.segment_id, "start": s.start, "end": s.end, "original": s.original, "translated": s.translated} for s in db_segs]
            
            from backend.worker.tts_engine import synthesize_audio
            
            single_tts_segment = [{
                "id": db_seg.segment_id,
                "start": db_seg.start,
                "end": db_seg.end,
                "text": text,
                "original_text": db_seg.original
            }]
            
            tts_result = synthesize_audio(
                local_vocals_path,
                single_tts_segment,
                voice_type=voice_type,
                disable_openvoice=settings.DISABLE_OPENVOICE,
                disable_enhance=settings.DISABLE_ENHANCE,
                all_segments=segments_list_dicts,
                workspace_path=task_workspace
            )
            
            if tts_result["status"] == "error":
                return tts_result
                
            res_segments = tts_result.get("tts_segments", [])
            if not res_segments:
                return {"status": "error", "message": "TTS nije vratio metapodatke o segmentu."}
                
            generated_seg = res_segments[0]
            
            shutil.copy2(generated_seg["path"], stable_raw_path)
            
            apply_audio_modifiers(
                generated_seg["path"],
                stable_probni_path,
                volume=volume,
                speed=speed,
                pitch=pitch
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
            return {"status": "error", "message": f"S3 upload TTS neuspešan: {e}"}
            
        db_seg.translated = text
        db_seg.voice_type = voice_type
        db_seg.volume = volume
        db_seg.speed = speed
        db_seg.pitch = pitch
        db_seg.bg_volume = bg_volume
        db_seg.tts_s3_key = probni_s3_key
        db_seg.tts_duration = actual_duration
        db_seg.status = "previewed"
        db.commit()
        
        if p.dubbed_audio_s3_key:
            local_dubbed_path = os.path.join(task_workspace, f"dubbed_temp_{project_id}.wav")
            try:
                s3.download_file(settings.MINIO_BUCKET, p.dubbed_audio_s3_key, local_dubbed_path)
                full_audio = AudioSegment.from_wav(local_dubbed_path)
                
                temp_seg_local = os.path.join(task_workspace, f"temp_seg_{segment_id}.wav")
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
                
        refresh_project_draft(project_id, db)
        
        from backend.main import get_presigned_download_url
        presigned_url = get_presigned_download_url(settings.MINIO_BUCKET, probni_s3_key)
        
        return {
            "status": "success",
            "audio_url": presigned_url,
            "duration": actual_duration
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
        if os.path.exists(task_workspace):
            shutil.rmtree(task_workspace, ignore_errors=True)

@celery_app.task(
    bind=True,
    name="generate_all_tts_task",
    acks_late=True,
    time_limit=1800
)
def generate_all_tts_task(self, project_id: str, voice_type: str):
    print(f"--- [CELERY TASK] Započeta asinhrona sinteza svih segmenata za projekat {project_id} ---", flush=True)
    task_id = self.request.id
    db = SessionLocal()
    
    task_workspace = os.path.join(settings.TEMP_WORKSPACE, task_id)
    os.makedirs(task_workspace, exist_ok=True)
    
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name=settings.S3_REGION
    )
    
    try:
        import uuid
        project_uuid = uuid.UUID(project_id)
        p = db.query(Project).filter(Project.id == project_uuid).first()
        if not p:
            return {"status": "error", "message": "Projekat nije pronađen."}
            
        db_segments = db.query(Segment).filter(Segment.project_id == project_uuid).order_by(Segment.segment_id).all()
        if not db_segments:
            return {"status": "error", "message": "Projekat nema segmenata za sintezu."}
            
        local_vocals_path = os.path.join(task_workspace, f"vocals_temp_{project_id}.wav")
        if not os.path.exists(local_vocals_path) and p.vocals_s3_key:
            try:
                s3.download_file(settings.MINIO_BUCKET, p.vocals_s3_key, local_vocals_path)
            except Exception as e:
                return {"status": "error", "message": f"Greška pri preuzimanju vokala sa S3: {e}"}
                
        tts_segments = []
        segments_list_dicts = []
        for s in db_segments:
            item = {
                "id": s.segment_id,
                "start": s.start,
                "end": s.end,
                "text": s.translated,
                "original_text": s.original,
                "voice_type": s.voice_type or voice_type
            }
            tts_segments.append(item)
            segments_list_dicts.append(item)
            
        from backend.worker.tts_engine import synthesize_audio
        from pydub import AudioSegment
        
        tts_result = synthesize_audio(
            local_vocals_path,
            tts_segments,
            voice_type=voice_type,
            disable_openvoice=settings.DISABLE_OPENVOICE,
            disable_enhance=settings.DISABLE_ENHANCE,
            all_segments=segments_list_dicts,
            workspace_path=task_workspace
        )
        
        if tts_result["status"] == "error":
            return tts_result
            
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
                stable_seg_path = os.path.join(task_workspace, seg_filename)
                
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
                temp_seg_local = os.path.join(task_workspace, f"temp_seg_{s.segment_id}.wav")
                try:
                    s3.download_file(settings.MINIO_BUCKET, s.tts_s3_key, temp_seg_local)
                    seg_audio = AudioSegment.from_wav(temp_seg_local)
                    start_ms = int(s.start * 1000)
                    final_mix = final_mix.overlay(seg_audio, position=start_ms)
                    if os.path.exists(temp_seg_local): os.remove(temp_seg_local)
                except Exception:
                    pass
                    
        dubbed_filename = f"tts_full_{project_id}.wav"
        stable_dubbed_path = os.path.join(task_workspace, dubbed_filename)
        final_mix.export(stable_dubbed_path, format="wav")
        
        dubbed_audio_s3_key = f"projects/{project_id}/dubbed_audio.wav"
        try:
            s3.upload_file(stable_dubbed_path, settings.MINIO_BUCKET, dubbed_audio_s3_key)
        except Exception as e:
            return {"status": "error", "message": f"S3 upload celog tona neuspešan: {e}"}
            
        p.dubbed_audio_s3_key = dubbed_audio_s3_key
        db.commit()
        
        refresh_project_draft(project_id, db)
        
        from backend.main import get_presigned_download_url
        presigned_dubbed_url = get_presigned_download_url(settings.MINIO_BUCKET, dubbed_audio_s3_key)
        
        return {
            "status": "success",
            "audio_url": presigned_dubbed_url,
            "segments": [{"id": s.segment_id, "tts_path": get_presigned_download_url(settings.MINIO_BUCKET, s.tts_s3_key)} for s in db_segments if s.tts_s3_key]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
        if os.path.exists(task_workspace):
            shutil.rmtree(task_workspace, ignore_errors=True)




