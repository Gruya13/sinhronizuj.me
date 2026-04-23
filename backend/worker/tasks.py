from backend.worker.celery_app import celery_app
from backend.worker.downloader import download_youtube_video
import os

@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, video_url: str):
    """
    Korenski Celery zadatak koji vodi Fazu 1-7 sa granularnim praćenjem.
    """
    progress_metadata = {
        'current_step': "Inicijalizacija...",
        'percent': 0,
        'completed_steps': [],
        'segments': [],
        'active_instances': {8080: "idle", 8081: "idle", 8082: "idle"}
    }

    def update_progress(step_name=None, percentage=None, completed_step=None, segments=None, active_port=None):
        if step_name: progress_metadata['current_step'] = step_name
        if percentage: progress_metadata['percent'] = percentage
        if completed_step: progress_metadata['completed_steps'].append(completed_step)
        if segments: progress_metadata['segments'] = segments
        if active_port:
            # Resetujemo sve i palimo samo aktivni
            for p in progress_metadata['active_instances']:
                progress_metadata['active_instances'][p] = "idle"
            if active_port in progress_metadata['active_instances']:
                progress_metadata['active_instances'][active_port] = "active"
        
        self.update_state(state='PROGRESS', meta=progress_metadata)

    # --- FAZA 1: Preuzimanje ---
    update_progress("Preuzimanje videa...", 10)
    result = download_youtube_video(video_url)
    if result["status"] == "error": return result
    update_progress(completed_step="Preuzimanje završeno")
    
    # --- FAZA 2: Separacija Zvuka ---
    update_progress("Izolacija vokala...", 25)
    from backend.worker.audio_sep import separate_audio
    sep_result = separate_audio(result['audio_path'])
    if sep_result["status"] == "error": return sep_result
    update_progress(completed_step="Vokal izolovan")
    
    # --- FAZA 3: Transkripcija ---
    update_progress("Prepoznavanje govora...", 40)
    from backend.worker.transcriber import transcribe_audio
    transcription_result = transcribe_audio(sep_result["vocals_path"])
    if transcription_result["status"] == "error": return transcription_result
    
    # Inicijalizujemo segmente za UI
    segments_ui = []
    for i, s in enumerate(transcription_result["segments"]):
        segments_ui.append({
            "id": i,
            "original": s["text"],
            "translated": "",
            "status": "pending"
        })
    update_progress(completed_step="Govor prepoznat", segments=segments_ui)
    
    # --- FAZA 4: Prevod ---
    update_progress("Prevođenje i Lektura...", 55)
    from backend.worker.translator import translate_segments
    
    def translation_callback(idx, total, engine, translated_text):
        if idx < len(segments_ui):
            segments_ui[idx]["translated"] = translated_text
            segments_ui[idx]["status"] = "translated"
            # Blago povećavamo procenat unutar faze (55-70%)
            sub_percent = 55 + int((idx / total) * 15)
            update_progress(percentage=sub_percent, segments=segments_ui)

    translation_result = translate_segments(
        transcription_result["segments"], 
        progress_callback=translation_callback
    )
    if translation_result["status"] == "error": return translation_result
    update_progress(completed_step="Tekst preveden", percentage=70)
    
    # --- FAZA 5: Sinteza Govora ---
    update_progress("Sinteza glasa (Multi-instance)...", 70)
    from backend.worker.tts_engine import synthesize_audio
    
    def tts_callback(idx, total, port, text):
        if idx < len(segments_ui):
            segments_ui[idx]["status"] = "synthesized"
            sub_percent = 70 + int((idx / total) * 15)
            update_progress(percentage=sub_percent, segments=segments_ui, active_port=port)

    tts_result = synthesize_audio(
        sep_result["vocals_path"], 
        translation_result["translated_segments"],
        transcription_result["segments"],
        progress_callback=tts_callback
    )
    if tts_result["status"] == "error": return tts_result
    update_progress(completed_step="Glas generisan", percentage=85, active_port=None)
    
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

