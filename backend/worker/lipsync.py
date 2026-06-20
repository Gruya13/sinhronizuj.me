import os
import cv2
import subprocess
import uuid
from backend.core.config import settings

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
    Pokrece masivni Wav2Lip model kao eksterni pod-proces na osnovu zvuka i slike.
    """
    print("[FAZA 7] Lica potvrdjena! Iniciram Wav2Lip modul (Lip Sync u toku)...")
    workspace = workspace_path or settings.TEMP_WORKSPACE
    output_path = os.path.join(workspace, f"sinhronizuj_me_lipsync_{uuid.uuid4().hex[:6]}.mp4")
    
    wav2lip_dir = os.getenv("WAV2LIP_PATH", "/opt/Wav2Lip")
    
    if not os.path.exists(wav2lip_dir):
        print("[FAZA 7 UPOZORENJE] Wav2Lip folder nije pronadjen na serveru. Preskacem Lip Sync obradu i vracam sinhronizovan original.")
        return {"status": "success", "lipsync_video_path": video_path, "skipped": True}
        
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
            "skipped": False
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
    if not os.path.exists(wav2lip_dir):
        print("[SELECTIVE LIP SYNC WARNING] Wav2Lip folder nije pronađen na serveru. Vraćam originalni video.", flush=True)
        return {"status": "success", "lipsync_video_path": video_path, "skipped": True}

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
    
    try:
        for idx, interval in enumerate(intervals):
            start = interval["start"]
            end = interval["end"]
            duration = end - start
            
            # Ako je trajanje premalo (npr. manje od 50ms), preskačemo da izbegnemo greške u FFmpeg-u
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
                
                # Pokretanje Wav2Lip-a na ovom malom delu
                sub_lipsync_path = os.path.join(workspace, f"sub_lipsync_{idx}_{uuid.uuid4().hex[:6]}.mp4")
                temp_files_to_clean.append(sub_lipsync_path)
                
                command = [
                    "python", os.path.join(wav2lip_dir, "inference.py"),
                    "--checkpoint_path", os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth"),
                    "--face", sub_video_path,
                    "--audio", sub_audio_path,
                    "--outfile", sub_lipsync_path
                ]
                
                res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0 and os.path.exists(sub_lipsync_path) and os.path.getsize(sub_lipsync_path) > 0:
                    sub_clips.append(sub_lipsync_path)
                else:
                    err = res.stderr.decode('utf-8', errors='ignore')
                    print(f"[SELECTIVE LIP SYNC WARNING] Wav2Lip nije uspeo za segment {idx}: {err}. Koristim original.", flush=True)
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
                # Koristimo apsolutnu putanju
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
        
        print("[SELECTIVE LIP SYNC SUCCESS] Selektivna sinhronizacija usana završena.", flush=True)
        return {
            "status": "success",
            "lipsync_video_path": final_output_path,
            "skipped": False
        }
        
    except Exception as e:
        print(f"[SELECTIVE LIP SYNC ERROR] Greška u selektivnom Lip-Sync-u: {e}", flush=True)
        return {"status": "error", "message": str(e)}
        
    finally:
        # Čišćenje privremenih fajlova osim finalnog video rezultata i prosleđenih
        for temp_file in temp_files_to_clean:
            if temp_file != final_output_path and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
