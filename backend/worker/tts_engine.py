import os
import uuid
import torch
from pydub import AudioSegment
from TTS.api import TTS
from backend.core.config import settings

# --- UNIVERZALNI FIKS ZA PYTORCH 2.6/2.11+ ---
# Coqui TTS koristi torch.load interno, sto u novim verzijama PyTorch-a puca zbog 'weights_only' restrikcije.
# Monkey-patching torch.load funkcije da uvek koristi weights_only=False dok se model ucitava.
original_torch_load = torch.load
def patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return original_torch_load(*args, **kwargs)
torch.load = patched_torch_load
# --------------------------------------------

def create_reference_audio(vocals_path: str) -> str:
    """
    Iseca kratak, cist uzorak originalnog vokala (5 sekundi).
    XTTS v2 zahteva ovaj uzorak kako bi isklonirao boju glasa (Zero-shot Voice Cloning).
    """
    audio = AudioSegment.from_wav(vocals_path)
    
    # Uzimamo od 1. do 6. sekunde kako bismo izbegli pocetnu tisinu
    # (U produkciji bi se ovde koristio VAD algoritam za trazenje najboljeg uzorka)
    start_ms = 1000
    end_ms = 6000
    
    if len(audio) < end_ms:
        ref_audio = audio
    else:
        ref_audio = audio[start_ms:end_ms]
        
    ref_path = os.path.join(settings.TEMP_WORKSPACE, f"ref_{uuid.uuid4().hex[:6]}.wav")
    ref_audio.export(ref_path, format="wav")
    return ref_path

def synthesize_audio(vocals_path: str, translated_segments: list) -> dict:
    """
    Generise srpski glas koristeci XTTS v2 i stapa ga sa vremenskim oznakama.
    Kreira prazno platno (tisinu) i postavlja svaku izgovorenu recenicu na 
    njen tacan 'start' tajming kako bi ostala uskladjena sa videom.
    """
    if not os.path.exists(vocals_path):
        return {"status": "error", "message": "Fajl sa vokalom nije pronadjen."}

    try:
        ref_path = create_reference_audio(vocals_path)
        
        print("[FAZA 5] Ucitavam XTTS v2 model u graficku memoriju (ovo moze potrajati)...")
        # Pristup sekvencijalnog ucitavanja - drzi se u memoriji samo dok traje funkcija
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Postavljamo varijablu okruzenja koja automatski prihvata Coqui TOS
        os.environ["COQUI_TOS_AGREED"] = "1"
        
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        # OSIGURANJE FORMATA: Ponekad LLM vrati dikt umesto liste (uzrok KeyError -1)
        if isinstance(translated_segments, dict):
            print("[UPOZORENJE] LLM je vratio rečnik umesto liste. Vrsim konverziju...")
            if "segments" in translated_segments:
                translated_segments = translated_segments["segments"]
            elif "translated_segments" in translated_segments:
                translated_segments = translated_segments["translated_segments"]
            else:
                # Ako su kljucevi brojevi ("0", "1"...), uzimamo vrednosti
                translated_segments = list(translated_segments.values())

        if not isinstance(translated_segments, list) or len(translated_segments) == 0:
            return {"status": "error", "message": "Prevedeni segmenti nisu u ispravnom formatu liste."}

        # Kreiramo prazno platno (tisinu) dugo koliko i kraj poslednjeg segmenta
        last_end_time_ms = int(translated_segments[-1]["end"] * 1000) + 2000
        final_audio = AudioSegment.silent(duration=last_end_time_ms)
        
        output_dir = os.path.join(settings.TEMP_WORKSPACE, "generated_speech")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print("[FAZA 5] Generisem srpski govor segment po segment...")
        for i, segment in enumerate(translated_segments):
            text = segment["text"]
            start_time_ms = int(segment["start"] * 1000)
            
            temp_wav = os.path.join(output_dir, f"seg_{i}.wav")
            
            # XTTS blokira na skroz praznim ili prekratkim recenicama
            if len(text.strip()) > 1:
                tts.tts_to_file(
                    text=text,
                    file_path=temp_wav,
                    speaker_wav=ref_path,
                    language="sr"
                )
                
                generated_segment = AudioSegment.from_wav(temp_wav)
                
                # TODO za buduce optimizacije: Ovde mozemo iskoristiti pydub 'speedup' funkciju 
                # ako je generated_segment duzi od (segment['end'] - segment['start'])
                
                # Lepimo srpsku recenicu tacno na milisekundu kad je pocela engleska
                final_audio = final_audio.overlay(generated_segment, position=start_time_ms)
                
                os.remove(temp_wav) # Cistimo privremene fajlove

        # Agresivno ciscenje graficke memorije 
        os.remove(ref_path)
        del tts
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Izvoz konacnog srpskog audio dub-a
        final_output_path = os.path.join(settings.TEMP_WORKSPACE, f"serbian_dub_{uuid.uuid4().hex[:6]}.wav")
        final_audio.export(final_output_path, format="wav")
        
        return {
            "status": "success",
            "dubbed_audio_path": final_output_path
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG TTS GRESKA:\n{error_details}")
        return {"status": "error", "message": f"Greska pri TTS sintezi: {str(e)}"}
