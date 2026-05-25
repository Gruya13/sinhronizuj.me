import time
import requests
from backend.core.config import settings

def call_modal_endpoint(url: str, payload: dict, timeout_seconds: int = 600, progress_callback=None) -> dict:
    """
    Poziva sinhroni Modal webhook endpoint (FastAPI) i čeka na rezultat.
    Modal automatski održava konekciju otvorenom dok se zadatak ne izvrši (ili do timeout-a).
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"[MODAL] Pozivam endpoint: {url}")
    if progress_callback:
        progress_callback(detail="Modal radnik se budi (Cold Start u toku)... ⏳")
        
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            raise Exception(f"Modal posao vratio grešku: {result['error']}")
            
        print(f"[MODAL] Posao završen uspešno!")
        if progress_callback:
            progress_callback(detail="Zadatak na Modal-u je uspešno završen.")
            
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Mrežna greška pri komunikaciji sa Modalom: {e}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)

def normalize_audio(audio_path: str, target_dbfs: float = -20.0):
    """
    Normalizuje jačinu zvuka na zadati target_dbfs.
    Modifikuje fajl na licu mesta.
    """
    from pydub import AudioSegment
    import os
    if not os.path.exists(audio_path):
        print(f"[NORMALIZE] Fajl nije pronađen: {audio_path}")
        return
    try:
        print(f"[NORMALIZE] Normalizujem audio: {audio_path} na {target_dbfs} dBFS")
        sound = AudioSegment.from_file(audio_path)
        change_in_dbfs = target_dbfs - sound.dBFS
        normalized_sound = sound.apply_gain(change_in_dbfs)
        normalized_sound.export(audio_path, format="wav")
        print(f"[NORMALIZE] Uspešno normalizovan audio.")
    except Exception as e:
        print(f"[NORMALIZE] Greška pri normalizaciji audia: {e}")

