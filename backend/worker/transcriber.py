import os
from faster_whisper import WhisperModel

def transcribe_audio(audio_path: str, model_size: str = "base") -> dict:
    """
    Koristi faster-whisper za transkripciju izolovanog vokala.
    Vraća kompletan tekst i listu segmenata sa preciznim vremenskim oznakama (timestamps).
    """
    if not os.path.exists(audio_path):
        return {"status": "error", "message": f"Fajl nije pronadjen: {audio_path}"}

    try:
        print(f"[FAZA 3] Ucitavam Whisper model ('{model_size}')...")
        # Iniciramo model unutar funkcije u skladu sa dogovorom o "Sekvencijalnom ucitavanju modela"
        # kako bismo oslobodili VRAM kada funkcija zavrsi (Python Garbage Collector ce ga ukloniti)
        model = WhisperModel(model_size, device="auto", compute_type="default")
        
        print("[FAZA 3] Započinjem slusanje i transkripciju...")
        # Prepoznajemo jezik iz samog fajla
        segments, info = model.transcribe(audio_path, beam_size=5)
        
        print(f"[FAZA 3] Detektovan jezik: '{info.language}' (Verovatnoca: {info.language_probability:.2f})")
        
        segments_data = []
        full_text = ""
        
        # Iteriranje kroz generatore i cuvanje rezultata
        for segment in segments:
            segments_data.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip()
            })
            full_text += segment.text + " "
            
        # Rucno uklanjanje reference na model radi oslobadjanja memorije
        del model 
            
        return {
            "status": "success",
            "language": info.language,
            "full_text": full_text.strip(),
            "segments": segments_data
        }

    except Exception as e:
        return {"status": "error", "message": f"Greska pri transkripciji: {str(e)}"}
