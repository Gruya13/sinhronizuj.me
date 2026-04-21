import os
import subprocess
import uuid
from pydub import AudioSegment
from backend.core.config import settings

def merge_audio_and_video(video_path: str, background_path: str, dubbed_path: str) -> dict:
    """
    Spaja originalnu pozadinsku muziku/efekte sa nasim novim srpskim glasom.
    Zatim, zamenjuje originalni zvuk videa ovim novim "Final Mix-om" pomocu FFmpeg-a.
    """
    if not all(os.path.exists(p) for p in [video_path, background_path, dubbed_path]):
        return {"status": "error", "message": "Neki od potrebnih fajlova za spajanje ne postoje."}

    try:
        print("[FAZA 6] Miksam pozadinu i srpski glas u Final Mix...")
        
        # Ucitavamo audio fajlove u memoriju
        bg_audio = AudioSegment.from_wav(background_path)
        dub_audio = AudioSegment.from_wav(dubbed_path)
        
        # Audio inzenjering: blago utisavamo pozadinu (za 5 decibela) kako bi glas bio jasniji
        bg_audio = bg_audio - 5
        
        # Stapanje (overlay)
        final_mix = bg_audio.overlay(dub_audio)
        
        # Cuvanje Final Mix-a
        final_mix_path = os.path.join(settings.TEMP_WORKSPACE, f"final_mix_{uuid.uuid4().hex[:6]}.wav")
        final_mix.export(final_mix_path, format="wav")
        
        print("[FAZA 6] Final Mix zavrsen. Lepim sinhronizovani zvuk na video...")
        
        final_video_path = os.path.join(settings.TEMP_WORKSPACE, f"daca_dub_final_{uuid.uuid4().hex[:6]}.mp4")
        
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
