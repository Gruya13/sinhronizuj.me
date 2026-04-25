import time
import requests
from backend.core.config import settings

def wait_for_runpod_result(job_id: str, endpoint_id: str, timeout_seconds: int = 600, progress_callback=None) -> dict:
    """
    Univerzalna polling petlja za RunPod Serverless poslove sa podrškom za mikro-statuse.
    """
    status_url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    start_time = time.time()
    
    print(f"[RUNPOD] Započinjem polling za posao: {job_id}")
    
    last_status = None
    
    while True:
        if time.time() - start_time > timeout_seconds:
            raise Exception(f"RunPod timeout nakon {timeout_seconds}s (Job ID: {job_id})")
            
        try:
            response = requests.get(status_url, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            status = result.get("status")
            
            if status != last_status:
                last_status = status
                if progress_callback:
                    detail = ""
                    if status == "IN_QUEUE":
                        detail = "Cold Start: RunPod podiže radnika i učitava model u VRAM..."
                    elif status == "IN_PROGRESS":
                        detail = "Model je aktivan. Obrada podataka u toku..."
                    
                    if detail:
                        progress_callback(detail=detail)
            
            if status == "COMPLETED":
                print(f"[RUNPOD] Posao završen uspešno!")
                if progress_callback:
                    progress_callback(detail="Zadatak na RunPod-u je uspešno završen.")
                return result["output"]
            elif status == "FAILED":
                error_msg = result.get("error", "Nepoznata greška")
                raise Exception(f"RunPod posao nije uspeo: {error_msg}")
            
            # Čekamo malo pre sledeće provere
            time.sleep(5)
                
        except requests.exceptions.RequestException as e:
            print(f"[WARNING] Mrežna greška pri pollingu (pokušavam ponovo): {e}")
            time.sleep(5)
