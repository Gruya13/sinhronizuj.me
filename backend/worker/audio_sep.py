import os
import base64
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

def separate_audio(audio_path: str, progress_callback=None, workspace_path: str = None, project_id: str = None) -> dict:
    """
    Koristi Demucs na Modal.com za odvajanje vokala od pozadinske muzike.
    Zahvaljujući --two-stems vocals, Demucs generiše samo dva fajla:
    vocals.wav i no_vocals.wav čime drastično štedi vreme i CPU resurse.
    """
    print(f"[DEMUCS-CLIENT] Pokrećem separaciju na Modalu za: {audio_path}")
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronađen: {audio_path}"}

    try:
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        return {"status": "error", "message": f"Greška pri čitanju audio fajla: {str(e)}"}

    if progress_callback:
        progress_callback(detail="Separacija vokala na Modal-u... ⏳")

    # Računamo trajanje audia za procenu progresa na Modalu
    audio_duration = 0.0
    try:
        from pydub import AudioSegment
        aud = AudioSegment.from_file(audio_path)
        audio_duration = len(aud) / 1000.0
    except Exception as e:
        print(f"[DEMUCS-CLIENT] Upozorenje: Računanje trajanja nije uspelo: {e}")

    try:
        payload = {
            "audio_base64": audio_b64,
            "project_id": project_id,
            "audio_duration": audio_duration,
            "callback_url": f"{settings.BACKEND_URL}/api/v1/project/{project_id}/progress" if project_id and settings.BACKEND_URL else None
        }
        output = call_modal_endpoint(
            url=settings.MODAL_DEMUCS_URL,
            payload=payload,
            timeout_seconds=900,
            progress_callback=progress_callback
        )
        
        if "error" in output:
            return {"status": "error", "message": output["error"]}

        # Kreiramo lokalni direktorijum za izlaz
        workspace = workspace_path or settings.TEMP_WORKSPACE
        output_dir = os.path.join(workspace, "demucs_output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        base_filename = os.path.splitext(os.path.basename(audio_path))[0]
        model_output_dir = os.path.join(output_dir, "htdemucs", base_filename)
        os.makedirs(model_output_dir, exist_ok=True)

        vocals_path = os.path.join(model_output_dir, "vocals.wav")
        no_vocals_path = os.path.join(model_output_dir, "no_vocals.wav")

        # Dekodiramo i snimamo fajlove
        vocals_data = base64.b64decode(output["vocals_base64"])
        no_vocals_data = base64.b64decode(output["no_vocals_base64"])

        with open(vocals_path, "wb") as f_vocals:
            f_vocals.write(vocals_data)
        with open(no_vocals_path, "wb") as f_no_vocals:
            f_no_vocals.write(no_vocals_data)

        print(f"[DEMUCS-CLIENT] Uspeh! Vokali na: {vocals_path}")
        return {
            "status": "success",
            "vocals_path": vocals_path,
            "no_vocals_path": no_vocals_path
        }

    except Exception as e:
        print(f"[DEMUCS-CLIENT] Greška: {e}")
        return {"status": "error", "message": str(e)}

