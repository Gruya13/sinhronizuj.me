import cv2
import os
import numpy as np
import mediapipe as mp

def is_speaker_active_on_screen(video_path: str, start_time: float, end_time: float, sample_rate_fps: float = 8.0) -> bool:
    """
    Analizira segment videa pomoću MediaPipe FaceMesh i utvrđuje da li se usne
    govornika na ekranu pomeraju (Active Speaker Detection).
    Lokalno, brzo i besplatno.
    """
    if not video_path or not os.path.exists(video_path):
        print(f"[ACTIVE SPEAKER] Video fajl ne postoji: {video_path}")
        return False

    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if video_fps <= 0 or total_frames <= 0:
        cap.release()
        return False

    # Izračunavanje opsega frejmova
    start_frame = int(start_time * video_fps)
    end_frame = min(total_frames, int(end_time * video_fps))
    
    if start_frame >= end_frame:
        cap.release()
        return False

    # Određivanje koraka za uzorkovanje (sampling) radi brzine
    # Želimo da analiziramo npr. 8 frejmova po sekundi videa
    frame_step = max(1, int(video_fps / sample_rate_fps))
    
    # Inicijalizacija MediaPipe FaceMesh
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1, # Pratimo samo primarno lice u krupnom planu
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    mouth_openness_values = []
    frames_with_faces = 0
    total_sampled_frames = 0

    # Pozicioniranje na početni frejm
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    for f_idx in range(start_frame, end_frame, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret:
            break
            
        total_sampled_frames += 1
        
        # Konverzija frejma u RGB za MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)
        
        if results.multi_face_landmarks:
            frames_with_faces += 1
            landmarks = results.multi_face_landmarks[0].landmark
            
            # Ključne tačke usana:
            # 13: centar gornje usne (unutrašnja ivica)
            # 14: centar donje usne (unutrašnja ivica)
            # 78: levi ugao usana
            # 308: desni ugao usana
            p13 = np.array([landmarks[13].x, landmarks[13].y])
            p14 = np.array([landmarks[14].x, landmarks[14].y])
            p78 = np.array([landmarks[78].x, landmarks[78].y])
            p308 = np.array([landmarks[308].x, landmarks[308].y])
            
            # Računanje rastojanja
            vertical_dist = np.linalg.norm(p13 - p14)
            horizontal_dist = np.linalg.norm(p78 - p308)
            
            # Normalizovana otvorenost usta (skalirano prema širini usta da eliminišemo uticaj dubine i daljine kamere)
            if horizontal_dist > 0:
                openness = vertical_dist / horizontal_dist
                mouth_openness_values.append(openness)

    cap.release()
    face_mesh.close()

    # Evaluacija rezultata
    if total_sampled_frames == 0:
        return False
        
    face_presence_ratio = frames_with_faces / total_sampled_frames
    
    # Ako se lice vidi na manje od 30% trajanja segmenta govora, smatramo da nema govornika na ekranu (to je narator)
    if face_presence_ratio < 0.3:
        print(f"[ACTIVE SPEAKER] Lice detektovano na samo {face_presence_ratio:.1%} frejmova -> Naracija/Voiceover")
        return False

    # Izračunavanje varijanse otvorenosti usana
    if len(mouth_openness_values) > 1:
        variance = np.var(mouth_openness_values)
        
        # Prag varijanse: ako se usne pomeraju više od 0.0015, osoba govori.
        # Ako je manje, usne su statične (mirne ili zatvorene).
        is_active = variance > 0.0015
        print(f"[ACTIVE SPEAKER] Varijansa usana: {variance:.5f} (lice na {face_presence_ratio:.1%} slika) -> Aktivan govornik: {is_active}")
        return bool(is_active)

    return False


def precompute_active_speakers(video_path: str, sample_rate_fps: float = 8.0) -> list:
    """
    Skenira ceo video sekvencijalno i pre-računa otvorenost usta i prisustvo lica.
    To eliminiše stotine seek operacija i reinstanciranje MediaPipe FaceMesh modela.
    Lokalno, brzo i besplatno.
    """
    if not video_path or not os.path.exists(video_path):
        print(f"[ACTIVE SPEAKER] Video fajl ne postoji: {video_path}")
        return []

    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if video_fps <= 0 or total_frames <= 0:
        cap.release()
        return []

    # Određivanje koraka za uzorkovanje (sampling) radi brzine
    frame_step = max(1, int(video_fps / sample_rate_fps))
    
    # Inicijalizacija MediaPipe FaceMesh
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    results_timeline = []
    frame_idx = 0
    
    print(f"[ACTIVE SPEAKER] Pokrećem precompute za {video_path} (ukupno frejmova: {total_frames}, korak: {frame_step})", flush=True)

    while True:
        # Čitamo sekvencijalno
        if frame_idx % frame_step == 0:
            ret, frame = cap.read()
            if not ret:
                break
            
            timestamp = frame_idx / video_fps
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)
            
            face_detected = False
            openness = None
            
            if results.multi_face_landmarks:
                face_detected = True
                landmarks = results.multi_face_landmarks[0].landmark
                
                p13 = np.array([landmarks[13].x, landmarks[13].y])
                p14 = np.array([landmarks[14].x, landmarks[14].y])
                p78 = np.array([landmarks[78].x, landmarks[78].y])
                p308 = np.array([landmarks[308].x, landmarks[308].y])
                
                vertical_dist = np.linalg.norm(p13 - p14)
                horizontal_dist = np.linalg.norm(p78 - p308)
                
                if horizontal_dist > 0:
                    openness = float(vertical_dist / horizontal_dist)
            
            results_timeline.append({
                "timestamp": timestamp,
                "face_detected": face_detected,
                "openness": openness
            })
        else:
            # Grab je ekstremno brz jer ne dekodira sliku u memoriju
            ret = cap.grab()
            if not ret:
                break
                
        frame_idx += 1

    cap.release()
    face_mesh.close()
    
    print(f"[ACTIVE SPEAKER] Precompute završen. Uzorkovano {len(results_timeline)} frejmova.", flush=True)
    return results_timeline


def check_speaker_activity_from_timeline(timeline: list, start_time: float, end_time: float) -> bool:
    """
    Proverava da li je govornik aktivan u opsegu [start_time, end_time] na osnovu precomputed timeline-a.
    """
    if not timeline:
        return False
        
    # Filtriramo frejmova koji upadaju u opseg
    sampled_in_range = [f for f in timeline if start_time <= f["timestamp"] <= end_time]
    
    if not sampled_in_range:
        # Ako nismo ulovili frejmove u opsegu (npr. prekratak segment), uzmi najbliži frejm
        closest = min(timeline, key=lambda f: abs(f["timestamp"] - (start_time + end_time)/2))
        sampled_in_range = [closest]

    total_sampled = len(sampled_in_range)
    frames_with_faces = sum(1 for f in sampled_in_range if f["face_detected"])
    
    face_presence_ratio = frames_with_faces / total_sampled if total_sampled > 0 else 0.0
    
    # Ako se lice vidi na manje od 30% trajanja segmenta govora, smatramo da nema govornika na ekranu
    if face_presence_ratio < 0.3:
        return False
        
    mouth_openness_values = [f["openness"] for f in sampled_in_range if f["face_detected"] and f["openness"] is not None]
    
    if len(mouth_openness_values) > 1:
        variance = np.var(mouth_openness_values)
        is_active = variance > 0.0015
        return bool(is_active)
        
    return False

