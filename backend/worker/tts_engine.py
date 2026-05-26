import os
import requests
import uuid
import base64
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint
from backend.worker.preprocessor import upload_to_minio

def synthesize_audio(vocals_path: str, translated_segments: list, voice_type: str = "clone", progress_callback=None) -> dict:
    """
    Poziva Modal Serverless Fish Speech (TTS) za paralelnu sintezu segmenata.
    Zatim spaja izgenerisane audio delove na tacne vremenske pozicije pomocu pydub-a.
    """
    import io
    from pydub import AudioSegment

    if not translated_segments:
        return {"status": "error", "message": "Nema segmenata za sintezu."}

    if not settings.MODAL_TTS_URL:
        print("[WARNING] MODAL_TTS_URL nije definisan. Preskacem sintezu.")
        return {"status": "error", "message": "MODAL_TTS_URL nedostaje."}

    # 1. Priprema i isecanje referentnog audia za kloniranje glasa
    if progress_callback:
        progress_callback(detail="Priprema referentnog audia...")
    
    try:
        # Pronađi prvi segment sa validnim original_text i vremenima
        ref_segment = None
        for seg in translated_segments:
            if seg.get("original_text") and seg.get("start") is not None and seg.get("end") is not None:
                duration = seg["end"] - seg["start"]
                if 3.0 <= duration <= 15.0: # Idealno 3 do 15 sekundi
                    ref_segment = seg
                    break
                    
        # Ako nismo našli idealan, uzmi bilo koji koji ima original_text i traje bar 1 sekundu
        if not ref_segment:
            for seg in translated_segments:
                if seg.get("original_text") and seg.get("start") is not None and seg.get("end") is not None:
                    if seg["end"] - seg["start"] > 1.0:
                        ref_segment = seg
                        break
                        
        ref_audio_all = AudioSegment.from_wav(vocals_path)
        
        if ref_segment and "original_text" in ref_segment and ref_segment.get("start") is not None:
            start_ms = int(ref_segment["start"] * 1000)
            end_ms = int(ref_segment["end"] * 1000)
            
            # Iseci audio za taj segment
            ref_sub_audio = ref_audio_all[start_ms:end_ms]
            
            # Izvoz u buffer
            buffer = io.BytesIO()
            ref_sub_audio.export(buffer, format="wav")
            ref_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            ref_text = ref_segment["original_text"]
            print(f"[TTS V2] Uspešno isečen referentni segment ({ref_segment['start']}s - {ref_segment['end']}s) za glas: '{ref_text}'")
        else:
            # Fallback na prvih 15 sekundi celog vokala
            duration_ms = len(ref_audio_all)
            limit_ms = min(duration_ms, 15000) # Max 15 sekundi
            ref_sub_audio = ref_audio_all[:limit_ms]
            
            buffer = io.BytesIO()
            ref_sub_audio.export(buffer, format="wav")
            ref_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            ref_text = "Ovo je originalni glas iz videa."
            print(f"[WARNING] Nije nađen referentni segment. Koristim prvih 15 sekundi audia kao fallback.")
            
    except Exception as e:
        return {"status": "error", "message": f"Greška pri pripremi referentnog audia: {e}"}

    # 2. Učitavamo originalni vokal da bismo znali ukupnu dužinu i izračunali maksimalna trajanja segmenata
    try:
        ref_audio = AudioSegment.from_wav(vocals_path)
        video_duration_ms = len(ref_audio)
    except Exception as e:
        return {"status": "error", "message": f"Greška pri učitavanju originalnog vokala: {e}"}

    # Priprema segmenata za slanje na Modal bez prinudnog ubrzanja (max_duration = 0.0)
    # jer ćemo vremensko rastezanje i usklađivanje raditi na nivou videa/audia u mergeru!
    modal_segments = []
    for idx, s in enumerate(translated_segments):
        modal_segments.append({
            "id": str(s["id"]),
            "text": s["text"],
            "max_duration": 0.0
        })
    
    payload = {
        "segments": modal_segments,
        "reference_audio_base64": ref_b64,
        "reference_text": ref_text,
        "voice_type": voice_type
    }

    print(f"[TTS V2] Pozivam Modal OpenVoice V2 (Paralelno) za {len(translated_segments)} segmenata sa dynamic duration limitiranjem...")
    
    try:
        output = call_modal_endpoint(
            url=settings.MODAL_TTS_URL, 
            payload=payload, 
            timeout_seconds=600,
            progress_callback=progress_callback
        )
        
        results = output.get("results")
        if not results:
            error_msg = output.get("error", "Modal nije vratio rezultate.")
            return {"status": "error", "message": f"Sinteza nije uspela: {error_msg}"}
            
        # Pravimo tihu audio traku iste duzine
        final_mix = AudioSegment.silent(duration=video_duration_ms)
        
        # Mapiramo rezultate sinteze po id-u
        audio_by_id = {}
        for r in results:
            if r.get("error"):
                print(f"[TTS WARNING] Segment {r.get('id')} ima gresku: {r['error']}")
                continue
            audio_by_id[str(r.get("id"))] = r.get("audio_base64")

        # 4. Čuvamo pojedinačne generisane segmente i pravimo final_mix za kompatibilnost
        print("[TTS V2] Čuvam generisane segmente i kreiram metapodatke...")
        stitched_count = 0
        tts_segments_info = []
        
        for idx, seg in enumerate(translated_segments):
            seg_id = str(seg["id"])
            b64_audio = audio_by_id.get(seg_id)
            if not b64_audio:
                continue
            
            try:
                # Učitavanje segmenta iz memorije
                seg_bytes = base64.b64decode(b64_audio)
                seg_audio = AudioSegment.from_file(io.BytesIO(seg_bytes), format="wav")
                
                # Snimamo pojedinačni segment u privremeni fajl za dinamičko rastezanje
                seg_filename = f"tts_seg_{uuid.uuid4().hex[:8]}_{seg_id}.wav"
                seg_path = os.path.join(settings.TEMP_WORKSPACE, seg_filename)
                seg_audio.export(seg_path, format="wav")
                
                duration = len(seg_audio) / 1000.0
                
                tts_segments_info.append({
                    "id": seg["id"],
                    "path": seg_path,
                    "duration": duration,
                    "start": seg["start"],
                    "end": seg["end"]
                })
                
                # Kompatibilnost: pravimo i statički final_mix (ako zatreba fallback)
                start_ms = int(seg["start"] * 1000)
                if idx < len(translated_segments) - 1:
                    next_start_ms = int(translated_segments[idx + 1]["start"] * 1000)
                    max_allowed_duration_ms = next_start_ms - start_ms
                else:
                    max_allowed_duration_ms = video_duration_ms - start_ms
                
                compat_seg_audio = seg_audio
                if len(compat_seg_audio) > max_allowed_duration_ms and max_allowed_duration_ms > 0:
                    overage = len(compat_seg_audio) - max_allowed_duration_ms
                    if overage > 100:
                        compat_seg_audio = compat_seg_audio[:max_allowed_duration_ms]
                
                final_mix = final_mix.overlay(compat_seg_audio, position=start_ms)
                stitched_count += 1
            except Exception as ex:
                print(f"[TTS ERROR] Greška pri obradi segmenta {seg_id}: {ex}")

        print(f"[TTS V2] Uspesno sačuvano {len(tts_segments_info)} segmenata.")

        # Cuvanje u lokalni fajl za kompatibilnost
        local_filename = f"dubbed_{uuid.uuid4().hex[:8]}.wav"
        local_path = os.path.join(settings.TEMP_WORKSPACE, local_filename)
        
        final_mix.export(local_path, format="wav")
                    
        return {
            "status": "success",
            "dubbed_audio_path": local_path,
            "tts_segments": tts_segments_info
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
