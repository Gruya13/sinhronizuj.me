from backend.worker.celery_app import celery_app
from backend.worker.downloader import download_youtube_video
import os

@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, video_url: str):
    """
    Korenski Celery zadatak koji vodi Fazu 1 (yt-dlp preuzimanje) sa pracenjem progresa.
    """
    def update_progress(step_name, percentage, completed_steps):
        self.update_state(
            state='PROGRESS',
            meta={
                'current_step': step_name,
                'percent': percentage,
                'completed_steps': completed_steps
            }
        )

    completed = []
    
    # --- FAZA 1: Preuzimanje ---
    update_progress("Preuzimanje videa sa YouTube-a...", 10, completed)
    print(f"[FAZA 1] Pocinjem preuzimanje za URL: {video_url}")
    result = download_youtube_video(video_url)
    
    if result["status"] == "error":
        return result
        
    completed.append("Preuzimanje završeno")
    
    # --- FAZA 2: Separacija Zvuka ---
    update_progress("Izolacija vokala (AI Separacija)...", 30, completed)
    from backend.worker.audio_sep import separate_audio
    sep_result = separate_audio(result['audio_path'])
    
    if sep_result["status"] == "error":
        return sep_result
    
    completed.append("Vokal izolovan")
    
    # --- FAZA 3: Transkripcija ---
    update_progress("Prepoznavanje govora (Whisper AI)...", 45, completed)
    from backend.worker.transcriber import transcribe_audio
    transcription_result = transcribe_audio(sep_result["vocals_path"])
    
    if transcription_result["status"] == "error":
        return transcription_result
        
    completed.append("Govor prepoznat")
    
    # --- FAZA 4: Prevod ---
    update_progress("Prevođenje na srpski (Gemma 2 LLM)...", 55, completed)
    from backend.worker.translator import translate_segments
    translation_result = translate_segments(transcription_result["segments"])
    
    if translation_result["status"] == "error":
        return translation_result
        
    completed.append("Tekst preveden")
    
    # --- FAZA 5: Sinteza Govora ---
    update_progress("Kloniranje glasa i sinteza (XTTS v2)...", 75, completed)
    from backend.worker.tts_engine import synthesize_audio
    tts_result = synthesize_audio(sep_result["vocals_path"], translation_result["translated_segments"])
    
    if tts_result["status"] == "error":
        return tts_result
        
    completed.append("Glas generisan")
    
    # --- FAZA 6: Spajanje ---
    update_progress("Finalno spajanje slike i tona...", 85, completed)
    from backend.worker.merger import merge_audio_and_video
    merge_result = merge_audio_and_video(
        result["video_path"], 
        sep_result["no_vocals_path"], 
        tts_result["dubbed_audio_path"]
    )
    
    if merge_result["status"] == "error":
        return merge_result
        
    completed.append("Video spojen")
    
    # --- FAZA 7: Lip Sync ---
    update_progress("Optimizacija pokreta usana (Wav2Lip)...", 95, completed)
    from backend.worker.lipsync import has_sufficient_faces, apply_lip_sync
    needs_lipsync = has_sufficient_faces(merge_result["final_video_path"], threshold_percentage=10.0)
    
    if needs_lipsync:
        lip_result = apply_lip_sync(merge_result["final_video_path"], tts_result["dubbed_audio_path"])
        if lip_result["status"] == "error":
            final_output = merge_result["final_video_path"]
        else:
            final_output = lip_result["lipsync_video_path"]
    else:
        final_output = merge_result["final_video_path"]
    
    completed.append("Obrada završena")
    update_progress("Spremanje fajla...", 100, completed)
    
    return {
        "status": "completed", 
        "url": video_url,
        "final_video_path": final_output
    }
