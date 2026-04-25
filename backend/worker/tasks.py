from backend.worker.celery_app import celery_app
from backend.worker.downloader import download_video
from backend.core.config import settings
import os
import shutil
from datetime import datetime, timedelta, timezone

@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, video_url: str):
    """
    Korenski Celery zadatak koji vodi Fazu 1-7 sa hibridnom RunPod arhitekturom.
    """
    # Zadatak 1: Fallback učitavanje API ključa ako je izgubljen u forkovanom procesu
    if not settings.RUNPOD_API_KEY:
        settings.RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY", "")
        print(f"[WORKER] Fallback: RUNPOD_API_KEY učitan iz os.environ (Dužina: {len(settings.RUNPOD_API_KEY)})")

    progress_metadata = {
        'current_step': "Inicijalizacija...",
        'percent': 0,
        'completed_steps': [],
        'segments': [],
        'detail': "Priprema radnog prostora...",
        'logs': []
    }

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
        
        self.update_state(state='PROGRESS', meta=progress_metadata)

    # --- FAZA 1: Preuzimanje ---
    update_progress("Preuzimanje videa...", 10, detail="Povezivanje sa izvorom i preuzimanje media fajlova...")
    result = download_video(video_url)
    if result["status"] == "error": return result
    update_progress(completed_step="Preuzimanje završeno")
    
    # --- FAZA 2: Separacija Zvuka ---
    update_progress("Izolacija vokala...", 25, detail="Pokretanje Demucs modela na CPU-u. Ovo može potrajati par minuta...")
    from backend.worker.audio_sep import separate_audio
    sep_result = separate_audio(result['audio_path'])
    if sep_result["status"] == "error": return sep_result
    update_progress(completed_step="Vokal izolovan")
    
    # --- FAZA 3: Transkripcija ---
    update_progress("Prepoznavanje govora (Whisper RunPod)...", 40, detail="Inicijalizacija Whisper zahteva...")
    from backend.worker.transcriber import transcribe_audio
    transcription_result = transcribe_audio(
        sep_result["vocals_path"],
        progress_callback=lambda detail: update_progress(detail=detail)
    )
    if transcription_result["status"] == "error": return transcription_result
    
    segments_ui = []
    for i, s in enumerate(transcription_result["segments"]):
        segments_ui.append({
            "id": i,
            "original": s["text"],
            "translated": "",
            "status": "pending"
        })
    update_progress(completed_step="Govor prepoznat", segments=segments_ui, detail="Transkripcija uspešno završena.")
    
    # --- FAZA 4: Vizuelni Kontekst i Prevod ---
    update_progress("Generisanje vizuelnog konteksta...", 50, detail="Ekstrakcija ključnih frejmova za analizu...")
    from backend.worker.preprocessor import extract_visual_context, upload_to_minio
    preview_path = extract_visual_context(result["video_path"])
    
    visual_context_url = None
    if preview_path:
        visual_context_url = upload_to_minio(preview_path)
        update_progress(visual_context_url=visual_context_url)
    
    update_progress("Prevođenje (RunPod + TOON)...", 60, detail="Slanje segmenata na Qwen 32B model...")
    from backend.worker.translator import translate_segments
    
    translation_result = translate_segments(
        transcription_result["segments"],
        progress_callback=lambda detail: update_progress(detail=detail)
    )
    if translation_result["status"] == "error": return translation_result
    
    for i, s in enumerate(translation_result["translated_segments"]):
        if i < len(segments_ui):
            segments_ui[i]["translated"] = s["text"]
            segments_ui[i]["status"] = "translated"
            
    update_progress(completed_step="Tekst preveden", percentage=70, segments=segments_ui)
    
    # --- FAZA 5: Sinteza Govora ---
    update_progress("Sinteza glasa (RunPod TTS)...", 75, detail="Inicijalizacija Fish Speech modela...")
    from backend.worker.tts_engine import synthesize_audio
    
    tts_result = synthesize_audio(
        sep_result["vocals_path"], 
        translation_result["translated_segments"],
        progress_callback=lambda detail: update_progress(detail=detail)
    )
    if tts_result["status"] == "error": return tts_result
    update_progress(completed_step="Glas generisan", percentage=85)
    
    # --- FAZA 6: Spajanje ---
    update_progress("Finalni Mix...", 90)
    from backend.worker.merger import merge_audio_and_video
    merge_result = merge_audio_and_video(
        result["video_path"], 
        sep_result["no_vocals_path"], 
        tts_result["dubbed_audio_path"]
    )
    if merge_result["status"] == "error": return merge_result
    update_progress(completed_step="Video spojen")
    
    # --- FAZA 7: Lip Sync ---
    update_progress("Lip Sync provera...", 95)
    from backend.worker.lipsync import has_sufficient_faces, apply_lip_sync
    needs_lipsync = has_sufficient_faces(merge_result["final_video_path"], threshold_percentage=10.0)
    
    if needs_lipsync:
        lip_result = apply_lip_sync(merge_result["final_video_path"], tts_result["dubbed_audio_path"])
        final_output = lip_result["lipsync_video_path"] if lip_result["status"] != "error" else merge_result["final_video_path"]
    else:
        final_output = merge_result["final_video_path"]
    
    update_progress("Obrada završena", 100, "Obrada završena")
    
    return {
        "status": "completed", 
        "url": video_url,
        "final_video_path": final_output
    }

@celery_app.task(name="backend.worker.tasks.cleanup_old_files")
def cleanup_old_files():
    """
    Zadatak 3: Periodično čišćenje starih fajlova (starijih od 24h) sa S3 i lokalnog diska.
    """
    import boto3
    print(f"[CLEANUP] Pokrećem čišćenje starih fajlova: {datetime.now()}")
    
    # 1. Čišćenje MinIO bucketa (uploads i processed)
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_SECURE else f"https://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY
        )
        
        buckets = ['uploads', 'processed', 'input-audio'] # Dodajemo i input-audio za svaki slučaj
        threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        
        for bucket in buckets:
            print(f"[CLEANUP] Proveravam bucket: {bucket}")
            # Provera da li bucket postoji pre listanja
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

    # 2. Čišćenje lokalnog /app/temp_workspace
    local_temp = "/app/temp_workspace"
    if os.path.exists(local_temp):
        threshold_ts = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
        for item in os.listdir(local_temp):
            item_path = os.path.join(local_temp, item)
            try:
                # Brišemo podfoldere i fajlove starije od 24h
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
