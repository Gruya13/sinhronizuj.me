import os
import cv2
import subprocess
import uuid
from backend.core.config import settings
from backend.services.s3 import (
    get_presigned_download_url,
    get_presigned_upload_url,
    upload_file_to_s3,
    download_file_from_s3,
    delete_file_from_s3
)

def has_sufficient_faces(video_path: str, sample_rate: int = 30, threshold_percentage: float = 10.0) -> bool:
    """
    Analizira video koristeći OpenCV Haar Cascades modele kako bi detektovao ljudska lica.
    Optimizacija: Uzorkuje svaki `sample_rate`-ti frejm (npr. svake sekunde u 30fps videu).
    Ako procenat frejmova sa licima prelazi zadati `threshold_percentage`, 
    funkcija vraca True sto znaci da video mora ici na Wav2Lip obradu.
    """
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("[FAZA 7 UPOZORENJE] Nije moguce otvoriti video za analizu lica.")
        return False
        
    total_frames_checked = 0
    frames_with_faces = 0
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        if frame_count % sample_rate == 0:
            total_frames_checked += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            
            if len(faces) > 0:
                frames_with_faces += 1
                
    cap.release()
    
    if total_frames_checked == 0:
        return False
        
    face_percentage = (frames_with_faces / total_frames_checked) * 100
    print(f"[FAZA 7] OpenCV Pred-Analiza Lica: {face_percentage:.2f}% detektovanih frejmova sadrzi ljudska lica.")
    
    return face_percentage >= threshold_percentage

def apply_lip_sync(video_path: str, audio_path: str, workspace_path: str = None) -> dict:
    """
    Pokreće Wav2Lip model. Može raditi preko serverless Modal GPU workera ili lokalnog podprocesa.
    """
    print("[FAZA 7] Lica potvrdjena! Iniciram Wav2Lip modul (Lip Sync u toku)...")
    workspace = workspace_path or settings.TEMP_WORKSPACE
    output_path = os.path.join(workspace, f"sinhronizuj_me_lipsync_{uuid.uuid4().hex[:6]}.mp4")
    
    # 1. Pokušavamo preko serverless Modal GPU workera ako je URL definisan
    modal_url = os.getenv("MODAL_WAV2LIP_URL", "")
    if modal_url:
        print(f"[FAZA 7] Koristim serverless Modal GPU worker za Wav2Lip na: {modal_url}")
        s3_keys_to_clean = []
        try:
            from backend.worker.utils import call_modal_endpoint
            
            temp_id = uuid.uuid4().hex
            video_key = f"temp/lipsync/{temp_id}_input_vid.mp4"
            audio_key = f"temp/lipsync/{temp_id}_input_aud.wav"
            output_key = f"temp/lipsync/{temp_id}_output_vid.mp4"
            
            if not upload_file_to_s3(video_path, settings.MINIO_BUCKET, video_key):
                raise Exception("Neuspešno otpremanje video zapisa na S3")
            s3_keys_to_clean.append(video_key)
            
            if not upload_file_to_s3(audio_path, settings.MINIO_BUCKET, audio_key):
                raise Exception("Neuspešno otpremanje audio zapisa na S3")
            s3_keys_to_clean.append(audio_key)
            
            video_url = get_presigned_download_url(settings.MINIO_BUCKET, video_key, expires_in=900)
            audio_url = get_presigned_download_url(settings.MINIO_BUCKET, audio_key, expires_in=900)
            result_upload_url = get_presigned_upload_url(settings.MINIO_BUCKET, output_key, expires_in=900)
            
            payload = {
                "video_url": video_url,
                "audio_url": audio_url,
                "result_upload_url": result_upload_url
            }
            
            res = call_modal_endpoint(modal_url, payload, timeout_seconds=900)
            if "error" in res:
                raise Exception(res["error"])
                
            s3_keys_to_clean.append(output_key)
            if not download_file_from_s3(settings.MINIO_BUCKET, output_key, output_path):
                raise Exception("Neuspešno preuzimanje obrađenog videa sa S3")
                
            return {
                "status": "success",
                "lipsync_video_path": output_path,
                "skipped": False,
                "provider": "modal"
            }
        except Exception as modal_err:
            print(f"[FAZA 7 WARNING] Greška pri pozivanju serverless Wav2Lip-a: {modal_err}. Pokušavam lokalni fallback...")
        finally:
            for k in s3_keys_to_clean:
                delete_file_from_s3(settings.MINIO_BUCKET, k)
            
    # 2. Lokalni fallback
    wav2lip_dir = os.getenv("WAV2LIP_PATH", "/opt/Wav2Lip")
    if not os.path.exists(wav2lip_dir):
        print("[FAZA 7 UPOZORENJE] Wav2Lip folder nije pronadjen na serveru. Preskacem Lip Sync obradu i vracam sinhronizovan original.")
        return {"status": "success", "lipsync_video_path": video_path, "skipped": True, "provider": "skipped"}
        
    command = [
        "python", os.path.join(wav2lip_dir, "inference.py"),
        "--checkpoint_path", os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth"),
        "--face", video_path,
        "--audio", audio_path,
        "--outfile", output_path
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return {
            "status": "success",
            "lipsync_video_path": output_path,
            "skipped": False,
            "provider": "local"
        }
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Wav2Lip greska procesa: {e.stderr.decode('utf-8', errors='ignore')}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def apply_selective_lip_sync(video_path: str, audio_path: str, segments: list, workspace_path: str = None) -> dict:
    """
    Pokreće Wav2Lip selektivno samo na onim segmentima gde je active_speaker == True.
    """
    workspace = workspace_path or settings.TEMP_WORKSPACE
    print("[SELECTIVE LIP SYNC] Započinjem selektivnu obradu usana...", flush=True)
    final_output_path = None
    
    wav2lip_dir = os.getenv("WAV2LIP_PATH", "/opt/Wav2Lip")
    modal_url = os.getenv("MODAL_WAV2LIP_URL", "")
    
    # Ako nemamo ni Modal ni lokalni Wav2Lip, vraćamo original
    if not modal_url and not os.path.exists(wav2lip_dir):
        print("[SELECTIVE LIP SYNC WARNING] Ni Modal ni lokalni Wav2Lip folder nisu dostupni. Vraćam originalni video.", flush=True)
        return {"status": "success", "lipsync_video_path": video_path, "skipped": True, "provider": "skipped"}

    # Učitavamo trajanje originalnog videa preko OpenCV-a
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / fps if fps > 0 else 0.0
    cap.release()
    
    if video_duration <= 0.0:
        print("[SELECTIVE LIP SYNC ERROR] Nije moguće učitati dužinu videa.", flush=True)
        return {"status": "error", "message": "Nevažeća dužina videa."}

    # Sortiramo segmente po vremenu početka
    sorted_segments = sorted(segments, key=lambda x: x.get("start", 0.0))
    
    # Podela timeline-a na aktivne i originalne (pasivne) opsege
    intervals = []
    current_time = 0.0
    
    for seg in sorted_segments:
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        is_active = seg.get("active_speaker", True)
        
        # Praznina pre početka segmenta
        if start > current_time + 0.02:
            intervals.append({
                "type": "original",
                "start": current_time,
                "end": start
            })
            
        if is_active:
            intervals.append({
                "type": "active",
                "start": start,
                "end": end
            })
        else:
            intervals.append({
                "type": "original",
                "start": start,
                "end": end
            })
            
        current_time = end
        
    # Preostalo vreme do kraja videa
    if video_duration > current_time + 0.02:
        intervals.append({
            "type": "original",
            "start": current_time,
            "end": video_duration
        })

    print(f"[SELECTIVE LIP SYNC] Ukupno detektovano {len(intervals)} video intervala za procesiranje.", flush=True)

    sub_clips = []
    temp_files_to_clean = []
    used_providers = []
    
    try:
        for idx, interval in enumerate(intervals):
            start = interval["start"]
            end = interval["end"]
            duration = end - start
            
            # Ako je trajanje premalo, preskačemo
            if duration < 0.05:
                continue
                
            sub_video_path = os.path.join(workspace, f"sub_video_{idx}_{uuid.uuid4().hex[:6]}.mp4")
            temp_files_to_clean.append(sub_video_path)
            
            # Sečenje videa pomoću FFmpeg-a
            cmd_cut_video = [
                "ffmpeg", "-y",
                "-ss", f"{start:.3f}",
                "-to", f"{end:.3f}",
                "-i", video_path,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                "-an",
                sub_video_path
            ]
            subprocess.run(cmd_cut_video, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if interval["type"] == "active":
                print(f"[SELECTIVE LIP SYNC] Segment {idx}: Obrada usana (Wav2Lip) od {start:.2f}s do {end:.2f}s...", flush=True)
                
                # Isecanje audio dela
                sub_audio_path = os.path.join(workspace, f"sub_audio_{idx}_{uuid.uuid4().hex[:6]}.wav")
                temp_files_to_clean.append(sub_audio_path)
                
                cmd_cut_audio = [
                    "ffmpeg", "-y",
                    "-ss", f"{start:.3f}",
                    "-to", f"{end:.3f}",
                    "-i", audio_path,
                    sub_audio_path
                ]
                subprocess.run(cmd_cut_audio, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Pokretanje Wav2Lip-a
                sub_lipsync_path = os.path.join(workspace, f"sub_lipsync_{idx}_{uuid.uuid4().hex[:6]}.mp4")
                temp_files_to_clean.append(sub_lipsync_path)
                
                success_lipsync = False
                
                # Prvi pokušaj: Serverless Modal
                if modal_url:
                    print(f"[SELECTIVE LIP SYNC] Segment {idx}: Koristim serverless Modal za Wav2Lip...", flush=True)
                    s3_keys_to_clean_sub = []
                    try:
                        from backend.worker.utils import call_modal_endpoint
                        
                        temp_id = uuid.uuid4().hex
                        video_key = f"temp/lipsync/{temp_id}_sub_vid_{idx}.mp4"
                        audio_key = f"temp/lipsync/{temp_id}_sub_aud_{idx}.wav"
                        output_key = f"temp/lipsync/{temp_id}_sub_out_{idx}.mp4"
                        
                        if upload_file_to_s3(sub_video_path, settings.MINIO_BUCKET, video_key):
                            s3_keys_to_clean_sub.append(video_key)
                        else:
                            raise Exception("Neuspešno otpremanje pod-videa na S3")
                            
                        if upload_file_to_s3(sub_audio_path, settings.MINIO_BUCKET, audio_key):
                            s3_keys_to_clean_sub.append(audio_key)
                        else:
                            raise Exception("Neuspešno otpremanje pod-audia na S3")
                            
                        video_url = get_presigned_download_url(settings.MINIO_BUCKET, video_key, expires_in=600)
                        audio_url = get_presigned_download_url(settings.MINIO_BUCKET, audio_key, expires_in=600)
                        result_upload_url = get_presigned_upload_url(settings.MINIO_BUCKET, output_key, expires_in=600)
                        
                        payload = {
                            "video_url": video_url,
                            "audio_url": audio_url,
                            "result_upload_url": result_upload_url
                        }
                        
                        res = call_modal_endpoint(modal_url, payload, timeout_seconds=600)
                        if "error" not in res:
                            s3_keys_to_clean_sub.append(output_key)
                            if download_file_from_s3(settings.MINIO_BUCKET, output_key, sub_lipsync_path):
                                success_lipsync = True
                                used_providers.append("modal")
                            else:
                                print(f"[SELECTIVE LIP SYNC WARNING] Greška pri preuzimanju pod-videa sa S3 za segment {idx}", flush=True)
                        else:
                            err_msg = res.get("error", "Nepoznata greška")
                            print(f"[SELECTIVE LIP SYNC WARNING] Modal greška za segment {idx}: {err_msg}", flush=True)
                    except Exception as modal_err:
                        print(f"[SELECTIVE LIP SYNC WARNING] Greška pri pozivanju serverless Wav2Lip za segment {idx}: {modal_err}", flush=True)
                    finally:
                        for k in s3_keys_to_clean_sub:
                            delete_file_from_s3(settings.MINIO_BUCKET, k)
                
                # Drugi pokušaj (fallback): Lokalni podproces
                if not success_lipsync and os.path.exists(wav2lip_dir):
                    print(f"[SELECTIVE LIP SYNC] Segment {idx}: Koristim lokalni fallback...", flush=True)
                    command = [
                        "python", os.path.join(wav2lip_dir, "inference.py"),
                        "--checkpoint_path", os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth"),
                        "--face", sub_video_path,
                        "--audio", sub_audio_path,
                        "--outfile", sub_lipsync_path
                    ]
                    
                    res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if res.returncode == 0 and os.path.exists(sub_lipsync_path) and os.path.getsize(sub_lipsync_path) > 0:
                        success_lipsync = True
                        used_providers.append("local")
                    else:
                        err = res.stderr.decode('utf-8', errors='ignore')
                        print(f"[SELECTIVE LIP SYNC WARNING] Lokalni Wav2Lip nije uspeo za segment {idx}: {err}. Koristim original.", flush=True)
                
                if success_lipsync:
                    sub_clips.append(sub_lipsync_path)
                else:
                    sub_clips.append(sub_video_path)
            else:
                print(f"[SELECTIVE LIP SYNC] Segment {idx}: Preskačem obradu usana (original) od {start:.2f}s do {end:.2f}s...", flush=True)
                sub_clips.append(sub_video_path)
                
        if not sub_clips:
            return {"status": "error", "message": "Nijedan video segment nije izgenerisan."}

        # Kreiranje concat tekstualnog fajla
        concat_list_path = os.path.join(workspace, f"concat_list_{uuid.uuid4().hex[:6]}.txt")
        temp_files_to_clean.append(concat_list_path)
        
        with open(concat_list_path, "w") as f:
            for clip in sub_clips:
                f.write(f"file '{os.path.abspath(clip)}'\n")
                
        # Spajanje svih isečaka pomoću concat demuxer-a
        joined_video_path = os.path.join(workspace, f"joined_video_{uuid.uuid4().hex[:6]}.mp4")
        temp_files_to_clean.append(joined_video_path)
        
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            joined_video_path
        ]
        subprocess.run(concat_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Spajanje videa bez zvuka sa finalnom dubbed audio trakom
        final_output_path = os.path.join(workspace, f"final_lipsync_{uuid.uuid4().hex[:6]}.mp4")
        
        merge_cmd = [
            "ffmpeg", "-y",
            "-i", joined_video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            final_output_path
        ]
        subprocess.run(merge_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        provider = "modal" if "modal" in used_providers else ("local" if "local" in used_providers else "skipped")
        print(f"[SELECTIVE LIP SYNC SUCCESS] Selektivna sinhronizacija usana završena (provajder: {provider}).", flush=True)
        return {
            "status": "success",
            "lipsync_video_path": final_output_path,
            "skipped": False,
            "provider": provider
        }
        
    except Exception as e:
        print(f"[SELECTIVE LIP SYNC ERROR] Greška u selektivnom Lip-Sync-u: {e}", flush=True)
        return {"status": "error", "message": str(e)}
        
    finally:
        for temp_file in temp_files_to_clean:
            if temp_file != final_output_path and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
