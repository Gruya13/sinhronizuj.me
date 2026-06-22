import time
import requests
from backend.core.config import settings

def _call_modal_endpoint_sync(url: str, payload: dict, timeout_seconds: int = 600, progress_callback=None) -> dict:
    """
    Interna sinhrona verzija (originalna logika).
    """
    headers = {
        "Content-Type": "application/json"
    }
    if getattr(settings, "MODAL_API_KEY", None):
        headers["X-API-Key"] = settings.MODAL_API_KEY
        headers["Authorization"] = f"Bearer {settings.MODAL_API_KEY}"

    max_retries = 5
    retry_delay = 5.0
    
    for attempt in range(1, max_retries + 1):
        print(f"[MODAL] Pozivam endpoint (Pokušaj {attempt}/{max_retries}): {url}")
        if progress_callback:
            if attempt == 1:
                progress_callback(detail="Inicijalizujem Modal radnika (Cold Start u toku)... ⏳")
            else:
                progress_callback(detail=f"Ponovni pokušaj poziva Modal-a ({attempt}/{max_retries})... ⏳")
                
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
            
            # Ako dobijemo 502/503/504, to ukazuje na hladan start ili privremeno preopterećenje
            if response.status_code in [502, 503, 504]:
                print(f"[MODAL WARNING] Dobijen status {response.status_code} od Modala. Mogući hladni start. Čekam...")
                time.sleep(retry_delay * attempt)
                continue
                
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                raise Exception(f"Modal posao vratio grešku: {result['error']}")
                
            print("[MODAL] Posao završen uspešno!")
            if progress_callback:
                progress_callback(detail="Zadatak na Modal-u je uspešno završen.")
                
            return result
            
        except (requests.exceptions.RequestException, Exception) as e:
            print(f"[MODAL WARNING] Pokušaj {attempt} nije uspeo. Greška: {e}")
            if attempt == max_retries:
                error_msg = f"Greška pri komunikaciji sa Modalom nakon {max_retries} pokušaja: {e}"
                print(f"[ERROR] {error_msg}")
                raise Exception(error_msg)
            time.sleep(retry_delay * attempt)

def call_modal_endpoint_async(url: str, payload: dict, timeout_seconds: int = 600, progress_callback=None) -> dict:
    """
    Poziva asinhroni Modal endpoint koristeći polling model.
    Prvo šalje zahtev na {url}/submit da započne zadatak i dobije job_id.
    Zatim periodično ispituje {url}/status/{job_id} dok zadatak ne bude gotov.
    Ako endpoint ne podržava asinhroni rad (npr. vrati 404), vrši se fallback na sinhroni poziv.
    """
    if not url:
        raise ValueError("URL endpoint za Modal ne sme biti prazan.")

    headers = {
        "Content-Type": "application/json"
    }
    if getattr(settings, "MODAL_API_KEY", None):
        headers["X-API-Key"] = settings.MODAL_API_KEY
        headers["Authorization"] = f"Bearer {settings.MODAL_API_KEY}"

    base_url = url.rstrip('/')
    submit_url = f"{base_url}/submit"

    print(f"[MODAL ASYNC] Pokušavam asinhroni submit na: {submit_url}")
    if progress_callback:
        progress_callback(detail="Slanje asinhronog zadatka Modal radniku... ⏳")

    try:
        response = requests.post(submit_url, json=payload, headers=headers, timeout=30)
        
        # Fallback na sinhroni ako submit ne postoji (404, 405)
        if response.status_code in [404, 405]:
            print("[MODAL ASYNC WARNING] Submit endpoint nije podržan (404/405). Radim fallback na sinhroni poziv.")
            return _call_modal_endpoint_sync(url, payload, timeout_seconds, progress_callback)
            
        response.raise_for_status()
        submit_data = response.json()
        
        job_id = submit_data.get("job_id")
        if not job_id:
            if "error" in submit_data:
                raise Exception(f"Modal posao vratio grešku: {submit_data['error']}")
            return submit_data

    except Exception as e:
        print(f"[MODAL ASYNC WARNING] Greška pri asinhronom pokretanju: {e}. Pokušavam sinhroni fallback...")
        return _call_modal_endpoint_sync(url, payload, timeout_seconds, progress_callback)

    # Polling petlja
    status_url = f"{base_url}/status/{job_id}"
    print(f"[MODAL ASYNC] Uspešno pokrenut posao {job_id}. Započinjem polling na: {status_url}")
    
    start_time = time.time()
    poll_interval = 3.0
    
    while True:
        if time.time() - start_time > timeout_seconds:
            raise TimeoutError(f"Prekoračeno maksimalno vreme čekanja ({timeout_seconds}s) za asinhroni Modal posao {job_id}.")
            
        try:
            status_resp = requests.get(status_url, headers=headers, timeout=15)
            status_resp.raise_for_status()
            job_data = status_resp.json()
            
            status = job_data.get("status", "running")
            
            if status == "completed":
                print(f"[MODAL ASYNC] Posao {job_id} uspešno završen!")
                result = job_data.get("result", {})
                if "error" in result:
                    raise Exception(f"Modal posao vratio grešku: {result['error']}")
                return result
                
            elif status == "failed":
                error_msg = job_data.get("error", "Nepoznata greška na radniku")
                raise Exception(f"Modal posao {job_id} nije uspeo: {error_msg}")
                
            else:
                elapsed = int(time.time() - start_time)
                if progress_callback:
                    progress_callback(detail=f"Modal izvršava zadatak (Prošlo {elapsed}s)... ⚙️")
                time.sleep(poll_interval)
                
        except requests.exceptions.RequestException as req_err:
            print(f"[MODAL ASYNC WARNING] Greška pri pollingu posla {job_id}: {req_err}. Pokušaću ponovo...")
            time.sleep(poll_interval)

def call_modal_endpoint(url: str, payload: dict, timeout_seconds: int = 600, progress_callback=None) -> dict:
    """
    Glavna funkcija za poziv Modal endpoint-a. Preusmerava na asinhronu verziju koja ima ugrađen fallback.
    """
    return call_modal_endpoint_async(url, payload, timeout_seconds, progress_callback)


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
        print("[NORMALIZE] Uspešno normalizovan audio.")
    except Exception as e:
        print(f"[NORMALIZE] Greška pri normalizaciji audia: {e}")


def apply_audio_modifiers(input_path: str, output_path: str, volume: float = 0.0, speed: float = 1.0, pitch: float = 0.0):
    """
    Primenjuje jačinu zvuka (volume u dB), brzinu (speed/tempo) i visinu tona (pitch u semitonima)
    koristeći FFmpeg sa rubberband filterom za visinu i brzinu.
    """
    import os
    import shutil
    import subprocess
    
    if not os.path.exists(input_path):
        print(f"[AUDIO OPT] Izlazni fajl nije pronađen: {input_path}")
        return
        
    filters = []
    if volume is not None and volume != 0.0:
        filters.append(f"volume={volume}dB")
    if (speed is not None and speed != 1.0) or (pitch is not None and pitch != 0.0):
        s_val = speed if speed is not None else 1.0
        p_val = pitch if pitch is not None else 0.0
        pitch_factor = 2.0 ** (p_val / 12.0)
        filters.append(f"rubberband=tempo={s_val}:pitch={pitch_factor}")
        
    if not filters:
        shutil.copy2(input_path, output_path)
        return
        
    filter_str = ",".join(filters)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", filter_str,
        output_path
    ]
    try:
        print(f"[AUDIO OPT] Primenjujem filtere: {filter_str} na {input_path} -> {output_path}")
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.decode('utf-8', errors='ignore')
        print(f"[AUDIO OPT ERROR] FFmpeg nije uspeo: {stderr_output}")
        shutil.copy2(input_path, output_path)
