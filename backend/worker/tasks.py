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
    import threading
    match = re.search(r'@([^:/]+)', settings.REDIS_URL)
    redis_host = match.group(1) if match else "redis"
    r_client = redis.Redis(host=redis_host, password=settings.REDIS_PASSWORD, port=6379, db=0)
    task_id = self.request.id

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
        'waiting_for_user': False,
        'waiting_step': None,
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
            return "continue"
        
        update_progress(detail=f"DEBUG: Pauziram nakon koraka '{step_name}'. Čekam potvrdu korisnika...", waiting=True, waiting_step=step_name)
        
        # Brišemo stari signal ako postoji
        r_client.delete(f"task:{task_id}:continue")
        
        # Čekamo signal (max 30 minuta)
        start_wait = time.time()
        while time.time() - start_wait < 1800:
            val = r_client.get(f"task:{task_id}:continue")
            if val:
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
                return val.decode("utf-8") if isinstance(val, bytes) else str(val)
            time.sleep(1)
        
        raise TimeoutError("Korisnik nije potvrdio nastavak u predviđenom roku.")

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
        # --- FAZA 1: Preuzimanje ---
        update_progress("Preuzimanje videa...", 10, detail="Povezivanje sa izvorom i preuzimanje media fajlova...")
        result = download_video(video_url)
        if result["status"] == "error": return result
        update_progress(completed_step="Preuzimanje završeno")
        
        # Pokrećemo ekstrakciju vizuelnog konteksta u pozadini odmah nakon preuzimanja videa
        vc_thread = threading.Thread(target=run_vc_extraction, args=(result["video_path"],))
        vc_thread.daemon = True
        vc_thread.start()
        
        time.sleep(1)
        wait_for_user("Preuzimanje")
        
        # --- FAZA 2: Separacija Zvuka ---
        update_progress("Izolacija vokala...", 25, detail="Pokretanje Demucs modela na Modalu...")
        from backend.worker.audio_sep import separate_audio
        t_start_sep = time.time()
        sep_result = separate_audio(
            result['audio_path'],
            progress_callback=lambda detail: update_progress(detail=detail)
        )
        duration_sep = time.time() - t_start_sep
        if sep_result["status"] == "error": return sep_result
        add_phase_cost("separation", "Izolacija vokala (Demucs)", "T4", duration_sep, 0.00018)
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
        t_start_trans = time.time()
        transcription_result = transcribe_audio(
            sep_result["vocals_path"],
            initial_prompt=initial_prompt,
            progress_callback=lambda detail: update_progress(detail=detail)
        )
        duration_trans = time.time() - t_start_trans
        if transcription_result["status"] == "error": return transcription_result
        add_phase_cost("transcription", "Prepoznavanje govora (Whisper)", "T4", duration_trans, 0.00018)
        
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
        update_progress("Generisanje vizuelnog konteksta...", 50, detail="Čekam pozadinsku ekstrakciju ključnih frejmova...")
        
        # Čekamo da se završi pozadinska ekstrakcija frejmova
        if vc_thread.is_alive():
            vc_thread.join()
            
        visual_context_url = vc_result.get("url")
        duration_vc = vc_result.get("duration", 0.0)
        if visual_context_url:
            update_progress(visual_context_url=visual_context_url)
        add_phase_cost("visual_context", "Generisanje vizuelnog konteksta (Lokalno)", "Lokalni VPS", duration_vc, 0.0)
        
        update_progress("Prevođenje (Modal + Multimodal)...", 60, detail="Analiza vizuelnog konteksta i slanje segmenata na Qwen-VL...")
        from backend.worker.translator import translate_segments
        
        translation_result = translate_segments(
            transcription_result["segments"],
            video_path=result["video_path"],
            progress_callback=lambda detail: update_progress(detail=detail)
        )
        if translation_result["status"] == "error": return translation_result
        
        # Dodajemo cene za prevođenje i lekturu
        metrics = translation_result.get("metrics", {})
        duration_trans = metrics.get("translator_duration", 0.0)
        duration_lektor = metrics.get("lektor_duration", 0.0)
        
        if duration_trans > 0:
            add_phase_cost("translation", "Prevođenje (Qwen-VL)", "A10G", duration_trans, 0.00033)
        if duration_lektor > 0:
            add_phase_cost("lektor", "Lektura teksta (Qwen 32B AWQ)", "A10G", duration_lektor, 0.00033)
        
        for i, s in enumerate(translation_result["translated_segments"]):
            if i < len(segments_ui):
                segments_ui[i]["translated"] = s["text"]
                segments_ui[i]["status"] = "translated"
                
        update_progress(completed_step="Tekst preveden i lektorisan", percentage=70, segments=segments_ui)
        time.sleep(2)
        wait_for_user("Prevođenje", translation_result["translated_segments"])
    
        # --- FAZA 5: Sinteza Govora ---
        from backend.worker.tts_engine import synthesize_audio
        
        while True:
            update_progress("Sinteza glasa (Modal TTS)...", 75, detail="Inicijalizacija i generisanje srpskih vokala...")
            
            # Učitavanje odabira glasa iz Redisa
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
                
            # Primenjujemo najnoviji prevod/tekst iz Redisa ako postoji
            edited_bytes = r_client.get(f"task:{task_id}:edited_segments")
            if edited_bytes:
                import json
                try:
                    edited_data = json.loads(edited_bytes)
                    print(f"[DEBUG] Primena editovanih segmenata pre TTS-a: {len(edited_data)} stavki.", flush=True)
                    for ed_seg in edited_data:
                        idx = ed_seg.get("id")
                        new_text = ed_seg.get("translated")
                        if idx is not None and new_text is not None:
                            if idx < len(translation_result["translated_segments"]):
                                translation_result["translated_segments"][idx]["text"] = new_text
                except Exception as e:
                    print(f"Greska pri ucitavanju editovanih segmenata za TTS: {e}", flush=True)
    
            t_start_tts = time.time()
            tts_result = synthesize_audio(
                sep_result["vocals_path"], 
                translation_result["translated_segments"],
                voice_type=selected_voice,
                disable_openvoice=settings.DISABLE_OPENVOICE,
                disable_enhance=settings.DISABLE_ENHANCE,
                progress_callback=lambda detail: update_progress(detail=detail)
            )
            duration_tts = time.time() - t_start_tts
            if tts_result["status"] == "error": return tts_result
            
            # Akumuliramo trošak u slučaju da korisnik regeneriše glas više puta
            existing_tts = progress_metadata['costs']['phases'].get("tts", {})
            existing_duration = existing_tts.get("duration_sec", 0.0)
            total_duration_tts = existing_duration + duration_tts
            add_phase_cost("tts", "Sinteza glasa (OpenVoice)", "L4", total_duration_tts, 0.00025)
            
            # Eksponiramo generisani audio URL za preslušavanje na frontendu
            dubbed_filename = os.path.basename(tts_result["dubbed_audio_path"])
            progress_metadata['dubbed_audio_url'] = f"/videos/{dubbed_filename}"
            
            segments_ui = [{
                "id": s.get("id", idx),
                "original": s.get("original_text", ""),
                "translated": s.get("text", ""),
                "status": "translated"
            } for idx, s in enumerate(translation_result["translated_segments"])]
            update_progress(completed_step="Glas generisan", percentage=85, segments=segments_ui)
            
            # Čekamo odluku korisnika
            action = wait_for_user("TTS Sinteza", translation_result["translated_segments"])
            if action == "regenerate":
                print("[DEBUG] Korisnik je zatražio ponovno generisanje glasa. Ponavljam sintezu...", flush=True)
                continue
            else:
                break
        
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
        t_start_merge = time.time()
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
        duration_merge = time.time() - t_start_merge
        if merge_result["status"] == "error": return merge_result
        add_phase_cost("merger", "Audio-video miksovanje (Lokalno)", "Lokalni VPS", duration_merge, 0.0)
        update_progress(completed_step="Video spojen")
        
        # --- FAZA 7: Lip Sync ---
        update_progress("Lip Sync provera...", 95)
        from backend.worker.lipsync import has_sufficient_faces, apply_lip_sync
        t_start_lip = time.time()
        needs_lipsync = has_sufficient_faces(merge_result["final_video_path"], threshold_percentage=10.0)
        
        if needs_lipsync:
            lip_vocals_path = merge_result.get("dubbed_audio_path") or tts_result["dubbed_audio_path"]
            lip_result = apply_lip_sync(merge_result["final_video_path"], lip_vocals_path)
            final_output = lip_result["lipsync_video_path"] if lip_result["status"] != "error" else merge_result["final_video_path"]
        else:
            final_output = merge_result["final_video_path"]
        duration_lip = time.time() - t_start_lip
        
        if needs_lipsync:
            add_phase_cost("lipsync", "Lip Sync sinhronizacija (Wav2Lip)", "Lokalni VPS", duration_lip, 0.0)
        else:
            add_phase_cost("lipsync", "Lip Sync preskočen (nema lica)", "Lokalni VPS", duration_lip, 0.0)
        
        update_progress("Obrada završena", 100, "Obrada završena")
        
        # Pomeranje finalnih fajlova u korenski temp_workspace kako bi ih web server mogao servirati
        if os.path.exists(final_output):
            final_output_filename = os.path.basename(final_output)
            destination_final_output = os.path.join(original_temp_workspace, final_output_filename)
            shutil.move(final_output, destination_final_output)
            final_output = destination_final_output
            
        if "dubbed_audio_path" in tts_result and os.path.exists(tts_result["dubbed_audio_path"]):
            dubbed_filename = os.path.basename(tts_result["dubbed_audio_path"])
            dest_dubbed = os.path.join(original_temp_workspace, dubbed_filename)
            shutil.move(tts_result["dubbed_audio_path"], dest_dubbed)
            tts_result["dubbed_audio_path"] = dest_dubbed
            progress_metadata['dubbed_audio_url'] = f"/videos/{dubbed_filename}"
            # Ažuriramo stanje i na Celery-u
            self.update_state(task_id=task_id, state='PROGRESS', meta=progress_metadata)

        return {
            "status": "completed", 
            "url": video_url,
            "final_video_path": final_output,
            "costs": progress_metadata.get("costs")
        }
    finally:
        # Vraćamo originalni TEMP_WORKSPACE
        settings.TEMP_WORKSPACE = original_temp_workspace
        # Brišemo izolovani radni prostor
        if os.path.exists(task_workspace):
            print(f"[CELERY TASK] Čistim privremeni radni prostor za task {task_id}: {task_workspace}", flush=True)
            shutil.rmtree(task_workspace, ignore_errors=True)

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
