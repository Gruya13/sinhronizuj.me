import time
import requests
from backend.core.config import settings

def call_modal_endpoint(url: str, payload: dict, timeout_seconds: int = 300, progress_callback=None) -> dict:
    """
    Poziva sinhroni Modal webhook endpoint (FastAPI) i čeka na rezultat.
    Modal automatski održava konekciju otvorenom dok se zadatak ne izvrši (ili do timeout-a).
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"[MODAL] Pozivam endpoint: {url}")
    if progress_callback:
        progress_callback(detail="Slanje zahteva na Modal (Cold Start može trajati 10-20s)...")
        
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
