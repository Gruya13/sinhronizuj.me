import os
import uuid
import torch
import requests
import base64
from pydub import AudioSegment
from backend.core.config import settings

def create_reference_audio(vocals_path: str) -> str:
    """
    Iseca kratak, cist uzorak originalnog vokala (5 sekundi).
    Fish Speech koristi ovaj uzorak kako bi isklonirao boju glasa.
    """
    audio = AudioSegment.from_wav(vocals_path)
    
    # Uzimamo od 1. do 6. sekunde kako bismo izbegli pocetnu tisinu
    start_ms = 1000
    end_ms = 6000
    
    if len(audio) < end_ms:
        ref_audio = audio
    else:
        ref_audio = audio[start_ms:end_ms]
        
    ref_path = os.path.join(settings.TEMP_WORKSPACE, f"ref_{uuid.uuid4().hex[:6]}.wav")
    ref_audio.export(ref_path, format="wav")
    return ref_path

def synthesize_audio(vocals_path: str, translated_segments: list, original_segments: list = None) -> dict:
    """
    Generise srpski glas koristeci Fish Speech 1.5 API i stapa ga sa vremenskim oznakama.
    """
    if not os.path.exists(vocals_path):
        return {"status": "error", "message": "Fajl sa vokalom nije pronadjen."}

    try:
        ref_path = create_reference_audio(vocals_path)
        
        # Procitamo referentni audio za Fish Speech
        with open(ref_path, "rb") as f:
            ref_audio_data = f.read()

        # OSIGURANJE FORMATA: Ponekad LLM vrati dikt umesto liste
        if isinstance(translated_segments, dict):
            found_list = None
            for key, val in translated_segments.items():
                if isinstance(val, list) and len(val) > 0:
                    found_list = val
                    break
            if found_list:
                translated_segments = found_list
                
        if isinstance(translated_segments, dict):
            translated_segments = [translated_segments]

        # NUKLEARNI FALLBACK: Ako LLM vrati samo listu stringova umesto rečnika
        if isinstance(translated_segments, list) and len(translated_segments) > 0 and not isinstance(translated_segments[0], dict):
            new_segments = []
            for i, text in enumerate(translated_segments):
                if original_segments and i < len(original_segments):
                    new_segments.append({
                        "start": original_segments[i]["start"],
                        "end": original_segments[i]["end"],
                        "text": str(text)
                    })
            translated_segments = new_segments

        # KRPLJENJE TAJMINGA
        final_segments = []
        for i, segment in enumerate(translated_segments):
            text = ""
            start = None
            end = None
            
            if isinstance(segment, dict):
                text = segment.get("text", "")
                start = segment.get("start") if segment.get("start") is not None else segment.get("start_time")
                end = segment.get("end") if segment.get("end") is not None else segment.get("end_time")
            else:
                text = str(segment)

            if (start is None or end is None) and original_segments and i < len(original_segments):
                start = original_segments[i]["start"]
                end = original_segments[i]["end"]
            
            if text and start is not None and end is not None:
                final_segments.append({"start": start, "end": end, "text": text})

        if not final_segments:
            return {"status": "error", "message": "Nema validnih segmenata za generisanje govora."}

        translated_segments = final_segments

        # Kreiramo prazno platno (tisinu)
        last_end_time_ms = int(translated_segments[-1]["end"] * 1000) + 2000
        final_audio = AudioSegment.silent(duration=last_end_time_ms)
        
        output_dir = os.path.join(settings.TEMP_WORKSPACE, "generated_speech")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print(f"[FAZA 5] Pozivam Fish Speech API za {len(translated_segments)} segmenta...")
        
        for i, segment in enumerate(translated_segments):
            text = segment["text"]
            start_time_ms = int(segment["start"] * 1000)
            
            if len(text.strip()) <= 1:
                continue

            temp_wav = os.path.join(output_dir, f"seg_{i}.wav")
            
            # --- POZIV FISH SPEECH API-ja ---
            try:
                # Fish Speech 1.5 API format (OpenAI kompatibilan ili MsgPack)
                # Ovde koristimo njihov FastAPI server direktno
                payload = {
                    "text": text,
                    "references": [
                        {
                            "audio": base64.b64encode(ref_audio_data).decode("utf-8"),
                            "text": "" # Opciono: originalni tekst referentnog snimka
                        }
                    ],
                    "top_p": 0.7,
                    "temperature": 0.7,
                    "format": "wav"
                }
                
                response = requests.post("http://localhost:8080/v1/tts", json=payload, timeout=60)
                
                if response.status_code == 200:
                    with open(temp_wav, "wb") as f:
                        f.write(response.content)
                else:
                    print(f"   [GREŠKA] Fish API vratio status {response.status_code}: {response.text}")
                    continue

                generated_segment = AudioSegment.from_wav(temp_wav)
                
                # --- PAMETNO UBRZAVANJE (AUDIO FIT) ---
                target_duration_ms = int((segment["end"] - segment["start"]) * 1000)
                current_duration_ms = len(generated_segment)
                
                if current_duration_ms > target_duration_ms * 1.1:
                    speed_factor = current_duration_ms / target_duration_ms
                    if speed_factor > 2.0:
                        speed_factor = 2.0
                        
                    print(f"   [!] Ubrzavam Fish segment {i} za {speed_factor:.2f}x.")
                    temp_speed_wav = temp_wav.replace(".wav", "_fast.wav")
                    
                    import subprocess
                    subprocess.run([
                        "ffmpeg", "-y", "-i", temp_wav,
                        "-filter:a", f"atempo={speed_factor}",
                        temp_speed_wav
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    generated_segment = AudioSegment.from_wav(temp_speed_wav)
                    os.remove(temp_speed_wav)
                
                final_audio = final_audio.overlay(generated_segment, position=start_time_ms)
                os.remove(temp_wav)

            except Exception as api_err:
                print(f"   [GREŠKA] Problem sa Fish Speech API-jem na segmentu {i}: {str(api_err)}")

        # Ciscenje
        if os.path.exists(ref_path):
            os.remove(ref_path)
            
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        final_output_path = os.path.join(settings.TEMP_WORKSPACE, f"fish_dub_{uuid.uuid4().hex[:6]}.wav")
        final_audio.export(final_output_path, format="wav")
        
        return {
            "status": "success",
            "dubbed_audio_path": final_output_path
        }
        
    except Exception as e:
        import traceback
        print(f"DEBUG FISH TTS GRESKA:\n{traceback.format_exc()}")
        return {"status": "error", "message": f"Greska pri Fish TTS sintezi: {str(e)}"}
