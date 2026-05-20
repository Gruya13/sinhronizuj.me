import os
import subprocess
import uuid
from pydub import AudioSegment
from backend.core.config import settings

def merge_audio_and_video(video_path: str, background_path: str, dubbed_path: str, background_vol: float = -5.0, dubbed_vol: float = 0.0) -> dict:
    """
    Spaja originalnu pozadinsku muziku/efekte sa nasim novim srpskim glasom.
    Zatim, zamenjuje originalni zvuk videa ovim novim "Final Mix-om" pomocu FFmpeg-a.
    """
    if not all(os.path.exists(p) for p in [video_path, background_path, dubbed_path]):
        return {"status": "error", "message": "Neki od potrebnih fajlova za spajanje ne postoje."}

    try:
        print(f"[FAZA 6] Miksam pozadinu ({background_vol}dB) i srpski glas ({dubbed_vol}dB) u Final Mix...")
        
        # Ucitavamo audio fajlove u memoriju
        bg_audio = AudioSegment.from_wav(background_path)
        dub_audio = AudioSegment.from_wav(dubbed_path)
        
        # Audio inzenjering: podesavamo jacinu prema parametrima
        if background_vol != 0.0:
            bg_audio = bg_audio + background_vol
        if dubbed_vol != 0.0:
            dub_audio = dub_audio + dubbed_vol
        
        # Stapanje (overlay)
        final_mix = bg_audio.overlay(dub_audio)
        
        # Cuvanje Final Mix-a
        final_mix_path = os.path.join(settings.TEMP_WORKSPACE, f"final_mix_{uuid.uuid4().hex[:6]}.wav")
        final_mix.export(final_mix_path, format="wav")
        
        print("[FAZA 6] Final Mix zavrsen. Lepim sinhronizovani zvuk na video...")
        
        final_video_path = os.path.join(settings.TEMP_WORKSPACE, f"sinhronizuj_me_final_{uuid.uuid4().hex[:6]}.mp4")
        
        # Ekstremno brza FFmpeg komanda za spajanje:
        # -c:v copy preuzima video frejmove kakvi jesu (nema potrebe za renderingom = 100x brze)
        command = [
            "ffmpeg",
            "-y", # Prepisuje postojeci fajl ako postoji
            "-i", video_path,
            "-i", final_mix_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0", # Uzmi prvu video traku iz prvog ulaza
            "-map", "1:a:0", # Uzmi prvu audio traku iz drugog ulaza
            "-shortest", # Seci na duzinu kraceg fajla (sprecava bug-ove sa praznim krajevima)
            final_video_path
        ]
        
        # Okidamo komandu na nivou sistema
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Brisemo medju-fajl Final Mix-a
        os.remove(final_mix_path)
        
        return {
            "status": "success",
            "final_video_path": final_video_path
        }
        
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"FFmpeg greska: {e.stderr.decode('utf-8', errors='ignore')}"}
    except Exception as e:
        return {"status": "error", "message": f"Greska pri spajanju videa: {str(e)}"}
