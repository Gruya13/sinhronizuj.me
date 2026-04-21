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
    # Ucitavamo ugradjeni OpenCV model za prepoznavanje frontalnog lica
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
        
        # Skeniramo samo uzorke (zbog brzine)
        if frame_count % sample_rate == 0:
            total_frames_checked += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Detektuje lica razlicitih velicina (od malih lica u igricama do krupnog kadra)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            
            if len(faces) > 0:
                frames_with_faces += 1
                
    cap.release()
    
    if total_frames_checked == 0:
        return False
        
    face_percentage = (frames_with_faces / total_frames_checked) * 100
    print(f"[FAZA 7] OpenCV Pred-Analiza Lica: {face_percentage:.2f}% detektovanih frejmova sadrzi ljudska lica.")
    
    # Ako lica cine dovoljan deo videa, mora se raditi LipSync
    return face_percentage >= threshold_percentage

def apply_lip_sync(video_path: str, audio_path: str) -> dict:
    """
    Pokrece masivni Wav2Lip model kao eksterni pod-proces na osnovu zvuka i slike.
    (Ovo zahteva posebnu Wav2Lip instalaciju na serveru)
    """
    print("[FAZA 7] Lica potvrdjena! Iniciram Wav2Lip modul (Lip Sync u toku)...")
    output_path = os.path.join(settings.TEMP_WORKSPACE, f"daca_dub_lipsync_{uuid.uuid4().hex[:6]}.mp4")
    
    # Wav2Lip arhitektura se najcesce pokrece iz zasebnog foldera van glavnog koda
    wav2lip_dir = os.getenv("WAV2LIP_PATH", "/opt/Wav2Lip")
    
    if not os.path.exists(wav2lip_dir):
        print("[FAZA 7 UPOZORENJE] Wav2Lip folder nije pronadjen na serveru. Preskacem Lip Sync obradu i vracam sinhronizovan original.")
        # Fallback sistem: ako LipSync pukne ili ga nema, vracamo korisniku video iz Faze 6
        return {"status": "success", "lipsync_video_path": video_path, "skipped": True}
        
    # Komanda za pokretanje Wav2Lip modela
    command = [
        "python", os.path.join(wav2lip_dir, "inference.py"),
        "--checkpoint_path", os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth"),
        "--face", video_path,
        "--audio", audio_path, # Ovde prosledjujemo XTTS nas srpski glas
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
