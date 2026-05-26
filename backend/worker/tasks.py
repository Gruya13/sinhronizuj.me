from backend.worker.celery_app import celery_app
from backend.worker.downloader import download_video
from backend.core.config import settings
import os
import shutil
from datetime import datetime, timedelta, timezone

@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, video_url: str, debug: bool = False):
    print(f"--- [CELERY TASK] Započeta obrada. Debug: {debug} ---", flush=True)
    """
    Korenski Celery zadatak koji vodi Fazu 1-7 sa hibridnom Modal arhitekturom.
    """
    import redis
    import time
    import re
    match = re.search(r'@([^:/]+)', settings.REDIS_URL)
    redis_host = match.group(1) if match else "redis"
    r_client = redis.Redis(host=redis_host, password=settings.REDIS_PASSWORD, port=6379, db=0)
    task_id = self.request.id

    progress_metadata = {
        'id': task_id,
        'current_step': "Inicijalizacija...",
        'percent': 0,
        'completed_steps': [],
        'segments': [],
        'detail': "Priprema radnog prostora...",
        'logs': [],
        'waiting_for_user': False,
        'waiting_step': None
    }

    def update_progress(step_name=None, percentage=None, completed_step=None, segments=None, visual_context_url=None, detail=None, waiting=False, waiting_step=None):
        if step_name: progress_metadata['current_step'] = step_name
        if percentage is not None: progress_metadata['percent'] = percentage
        if completed_step: progress_metadata['completed_steps'].append(completed_step)
        if segments: progress_metadata['segments'] = segments
        if visual_context_url: progress_metadata['visual_context_url'] = visual_context_url
        progress_metadata['waiting_for_user'] = waiting
        if waiting_step is not None:
            progress_metadata['waiting_step'] = waiting_step
        elif not waiting:
            progress_metadata['waiting_step'] = None

        if detail:
            progress_metadata['detail'] = detail
            ts = datetime.now().strftime("%H:%M:%S")
            progress_metadata['logs'].append(f"[{ts}] {detail}")
            if len(progress_metadata['logs']) > 20:
                progress_metadata['logs'] = progress_metadata['logs'][-20:]
        
        self.update_state(task_id=task_id, state='PROGRESS', meta=progress_metadata)

    def wait_for_user(step_name, segments_to_update=None):
        if not debug:
            return
        
        update_progress(detail=f"DEBUG: Pauziram nakon koraka '{step_name}'. Čekam potvrdu korisnika...", waiting=True, waiting_step=step_name)
        
        # Brišemo stari signal ako postoji
        r_client.delete(f"task:{task_id}:continue")
        
        # Čekamo signal (max 30 minuta)
        start_wait = time.time()
        while time.time() - start_wait < 1800:
            if r_client.get(f"task:{task_id}:continue"):
                r_client.delete(f"task:{task_id}:continue")
                
                # Provera da li postoje editovani segmenti u Redis-u
                edited_bytes = r_client.get(f"task:{task_id}:edited_segments")
                if edited_bytes and segments_to_update is not None:
                    import json
                    try:
                        edited_data = json.loads(edited_bytes)
                        print(f"[DEBUG] Primena editovanih segmenata iz Redisa: {len(edited_data)} stavki.", flush=True)
                        for ed_seg in edited_data:
                            idx = ed_seg.get("id")
                            new_text = ed_seg.get("translated")
                            if idx is not None and new_text is not None:
                                if idx < len(segments_to_update):
                                    segments_to_update[idx]["text"] = new_text
                                    print(f"[DEBUG] Ažuriran segment [{idx}] na: {new_text}", flush=True)
                    except Exception as e:
                        print(f"Greška pri ažuriranju segmenata: {e}", flush=True)
                
                update_progress(detail=f"DEBUG: Signal primljen. Nastavljam dalje...", waiting=False, waiting_step=None)
                return
            time.sleep(1)
        
        raise TimeoutError("Korisnik nije potvrdio nastavak u predviđenom roku.")


    # --- FAZA 1: Preuzimanje ---
    update_progress("Preuzimanje videa...", 10, detail="Povezivanje sa izvorom i preuzimanje media fajlova...")
    result = download_video(video_url)
    if result["status"] == "error": return result
    update_progress(completed_step="Preuzimanje završeno")
    time.sleep(1)
    wait_for_user("Preuzimanje")
    
    # --- FAZA 2: Separacija Zvuka ---
    update_progress("Izolacija vokala...", 25, detail="Pokretanje Demucs modela na Modalu...")
    from backend.worker.audio_sep import separate_audio
    sep_result = separate_audio(
        result['audio_path'],
        progress_callback=lambda detail: update_progress(detail=detail)
    )
    if sep_result["status"] == "error": return sep_result
    update_progress(completed_step="Vokal izolovan")
    time.sleep(1)
    wait_for_user("Separacija vokala")
    
    # --- FAZA 3: Transkripcija ---
    update_progress("Prepoznavanje govora (Whisper Modal)...", 40, detail="Inicijalizacija Whisper zahteva...")
    
    # Korak 1: Kreiranje dinamičkog initial prompt-a na osnovu metapodataka videa
    video_title = result.get("title", "")
    video_desc = result.get("description", "")
    video_tags = result.get("tags", [])
    
    prompt_keywords = []
    if video_title:
        prompt_keywords.append(video_title)
    if video_tags:
        prompt_keywords.extend(video_tags[:5])
        
    keywords_str = ", ".join([str(kw) for kw in prompt_keywords[:8]])
    initial_prompt = "This is a clear speech. Please use punctuation: dots, commas, and capital letters."
    if keywords_str:
        initial_prompt = f"This is a video about {keywords_str}. Please use correct punctuation: dots, commas, and capital letters. Spell names and technical terms correctly."
        
    print(f"[ASR] Generisan dinamički prompt: {initial_prompt}", flush=True)

    from backend.worker.transcriber import transcribe_audio
    transcription_result = transcribe_audio(
        sep_result["vocals_path"],
        initial_prompt=initial_prompt,
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
    print(f"--- [DEBUG] Šaljem {len(segments_ui)} segmenata u update_progress", flush=True)
    update_progress(completed_step="Govor prepoznat", segments=segments_ui, detail="Transkripcija uspešno završena.")
    time.sleep(2) # Dajemo vremena frontendu da oseti promenu pre nego što radnik blokira
    wait_for_user("Transkripcija", transcription_result["segments"])
    
    # --- FAZA 4: Vizuelni Kontekst i Prevod ---
    update_progress("Generisanje vizuelnog konteksta...", 50, detail="Ekstrakcija ključnih frejmova za analizu...")
    from backend.worker.preprocessor import extract_visual_context, upload_to_minio
    preview_path = extract_visual_context(result["video_path"])
    
    visual_context_url = None
    if preview_path:
        visual_context_url = upload_to_minio(preview_path)
        update_progress(visual_context_url=visual_context_url)
    
    update_progress("Prevođenje (Modal + Multimodal)...", 60, detail="Analiza vizuelnog konteksta i slanje segmenata na Qwen-VL...")
    from backend.worker.translator import translate_segments
    
    translation_result = translate_segments(
        transcription_result["segments"],
        video_path=result["video_path"],
        progress_callback=lambda detail: update_progress(detail=detail)
    )
    if translation_result["status"] == "error": return translation_result
    
    for i, s in enumerate(translation_result["translated_segments"]):
        if i < len(segments_ui):
            segments_ui[i]["translated"] = s["text"]
            segments_ui[i]["status"] = "translated"
            
    update_progress(completed_step="Tekst preveden i lektorisan", percentage=70, segments=segments_ui)
    time.sleep(2)
    wait_for_user("Prevođenje", translation_result["translated_segments"])


    
    # --- FAZA 5: Sinteza Govora ---
    update_progress("Sinteza glasa (Modal TTS)...", 75, detail="Inicijalizacija Fish Speech modela...")
    from backend.worker.tts_engine import synthesize_audio
    
    # Ucitavanje odabira glasa iz Redisa
    selected_voice = "clone"
    try:
        voice_bytes = r_client.get(f"task:{task_id}:voice_settings")
        if voice_bytes:
            import json
            voice_data = json.loads(voice_bytes)
            selected_voice = voice_data.get("voice", "clone")
            print(f"[DEBUG] Primena glasa iz Redisa: {selected_voice}", flush=True)
    except Exception as e:
        print(f"Greska pri ucitavanju podesavanja glasa: {e}", flush=True)
        
    tts_result = synthesize_audio(
        sep_result["vocals_path"], 
        translation_result["translated_segments"],
        voice_type=selected_voice,
        progress_callback=lambda detail: update_progress(detail=detail)
    )
    if tts_result["status"] == "error": return tts_result
    update_progress(completed_step="Glas generisan", percentage=85)
    wait_for_user("TTS Sinteza")
    
    # --- FAZA 6: Spajanje ---
    update_progress("Finalni Mix...", 90)
    
    # Ucitavanje podesavanja miksera iz Redisa ako postoje
    background_vol = -5.0
    dubbed_vol = 0.0
    try:
        mixer_bytes = r_client.get(f"task:{task_id}:mixer_settings")
        if mixer_bytes:
            import json
            mixer_data = json.loads(mixer_bytes)
            background_vol = float(mixer_data.get("background_volume", -5.0))
            dubbed_vol = float(mixer_data.get("dubbed_volume", 0.0))
            print(f"[DEBUG] Primena jacina iz Redisa: bg={background_vol}dB, dub={dubbed_vol}dB", flush=True)
    except Exception as e:
        print(f"Greska pri ucitavanju podesavanja miksera: {e}", flush=True)

    from backend.worker.merger import merge_audio_and_video, merge_audio_and_video_dynamic
    if tts_result.get("tts_segments"):
        merge_result = merge_audio_and_video_dynamic(
            result["video_path"], 
            sep_result["no_vocals_path"], 
            tts_result["tts_segments"],
            background_vol=background_vol,
            dubbed_vol=dubbed_vol
        )
    else:
        merge_result = merge_audio_and_video(
            result["video_path"], 
            sep_result["no_vocals_path"], 
            tts_result["dubbed_audio_path"],
            background_vol=background_vol,
            dubbed_vol=dubbed_vol
        )
    if merge_result["status"] == "error": return merge_result
    update_progress(completed_step="Video spojen")
    
    # --- FAZA 7: Lip Sync ---
    update_progress("Lip Sync provera...", 95)
    from backend.worker.lipsync import has_sufficient_faces, apply_lip_sync
    needs_lipsync = has_sufficient_faces(merge_result["final_video_path"], threshold_percentage=10.0)
    
    if needs_lipsync:
        lip_vocals_path = merge_result.get("dubbed_audio_path") or tts_result["dubbed_audio_path"]
        lip_result = apply_lip_sync(merge_result["final_video_path"], lip_vocals_path)
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
