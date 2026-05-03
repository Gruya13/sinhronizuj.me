import os
import subprocess
import sys
from backend.core.config import settings

def separate_audio(audio_path: str) -> dict:
    """
    Koristi Demucs za odvajanje vokala od pozadinske muzike.
    Zahvaljujući --two-stems vocals, Demucs generise samo dva fajla:
    vocals.wav i no_vocals.wav cime drasticno stedi vreme.
    """
    print(f"[DEMUCS] Pokrećem separaciju za: {audio_path}")
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronadjen: {audio_path}"}

    output_dir = os.path.join(settings.TEMP_WORKSPACE, "demucs_output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Koristimo direktno pozivanje modula preko trenutnog interpretera
    # Ovo je najsigurniji nacin u Docker-u
    command = [
        sys.executable, "-m", "demucs.separate",
        "-n", "htdemucs",
        "--two-stems", "vocals",
        "-o", output_dir,
        audio_path
    ]

    print(f"[DEMUCS] Komanda: {' '.join(command)}")

    try:
        # Podesavamo podproces, capture_output=True cuva logove za debagiranje
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"[DEMUCS] Greška (Return Code {result.returncode}): {result.stderr}")
            return {"status": "error", "message": f"Demucs podproces greska: {result.stderr}"}
        
        # Demucs kreira izlazne fajlove u podfolderu: output_dir/htdemucs/{ime_audio_fajla}/
        base_filename = os.path.splitext(os.path.basename(audio_path))[0]
        model_output_dir = os.path.join(output_dir, "htdemucs", base_filename)
        
        vocals_path = os.path.join(model_output_dir, "vocals.wav")
        no_vocals_path = os.path.join(model_output_dir, "no_vocals.wav")
        
        if os.path.exists(vocals_path) and os.path.exists(no_vocals_path):
            print(f"[DEMUCS] Uspeh! Vokali na: {vocals_path}")
            return {
                "status": "success",
                "vocals_path": vocals_path,
                "no_vocals_path": no_vocals_path
            }
        else:
            return {"status": "error", "message": "Demucs nije uspesno kreirao sve .wav fajlove."}

    except Exception as e:
        print(f"[DEMUCS] Neočekivana greška: {e}")
        return {"status": "error", "message": str(e)}
