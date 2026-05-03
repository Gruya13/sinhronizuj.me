import os
import subprocess
from backend.core.config import settings

def separate_audio(audio_path: str) -> dict:
    """
    Koristi Demucs za odvajanje vokala od pozadinske muzike.
    Zahvaljujući --two-stems vocals, Demucs generise samo dva fajla:
    vocals.wav i no_vocals.wav cime drasticno stedi vreme.
    """
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronadjen: {audio_path}"}

    output_dir = os.path.join(settings.TEMP_WORKSPACE, "demucs_output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Demucs CLI komanda
    # -n htdemucs: Optimizovan model
    # --two-stems vocals: Izdvaja samo glas, a sve ostalo spaja u no_vocals
    import shutil
    demucs_bin = shutil.which("demucs") or "/usr/local/bin/demucs"
    
    command = [
        demucs_bin,
        "-n", "htdemucs",
        "--two-stems", "vocals",
        "-o", output_dir,
        audio_path
    ]

    try:
        # Podesavamo podproces, capture_output=True cuva logove za debagiranje
        subprocess.run(command, check=True, capture_output=True, text=True)
        
        # Demucs kreira izlazne fajlove u podfolderu: output_dir/htdemucs/{ime_audio_fajla}/
        base_filename = os.path.splitext(os.path.basename(audio_path))[0]
        model_output_dir = os.path.join(output_dir, "htdemucs", base_filename)
        
        vocals_path = os.path.join(model_output_dir, "vocals.wav")
        no_vocals_path = os.path.join(model_output_dir, "no_vocals.wav")
        
        if os.path.exists(vocals_path) and os.path.exists(no_vocals_path):
            return {
                "status": "success",
                "vocals_path": vocals_path,
                "no_vocals_path": no_vocals_path
            }
        else:
            return {"status": "error", "message": "Demucs nije uspesno kreirao sve .wav fajlove."}

    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Demucs podproces greska: {e.stderr}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
