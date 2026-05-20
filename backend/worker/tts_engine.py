import os
import requests
import uuid
import base64
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint
from backend.worker.preprocessor import upload_to_minio

def synthesize_audio(vocals_path: str, translated_segments: list, progress_callback=None) -> dict:
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

    # 1. Konverzija vocals_path u Base64 za kloniranje glasa
    if progress_callback:
        progress_callback(detail="Priprema referentnog audia za kloniranje glasa...")
    
    try:
        with open(vocals_path, "rb") as f:
            ref_b64 = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        return {"status": "error", "message": f"Greška pri čitanju referentnog audia: {e}"}

    # 2. Priprema segmenata za slanje na Modal
    modal_segments = []
    for s in translated_segments:
        modal_segments.append({
            "id": str(s["id"]),
            "text": s["text"]
        })
    
    payload = {
        "segments": modal_segments,
        "reference_audio_base64": ref_b64,
        "reference_text": "Ovo je originalni glas iz videa."
    }

    print(f"[TTS V2] Pozivam Modal Fish Speech (Paralelno .map()) za {len(translated_segments)} segmenata...")
    
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
            
        # 3. Ucitavamo originalni vokal da bismo znali ukupnu duzinu i kreirali praznu traku
        ref_audio = AudioSegment.from_wav(vocals_path)
        video_duration_ms = len(ref_audio)
        
        # Pravimo tihu audio traku iste duzine
        final_mix = AudioSegment.silent(duration=video_duration_ms)
        
        # Mapiramo rezultate sinteze po id-u
        audio_by_id = {}
        for r in results:
            if r.get("error"):
                print(f"[TTS WARNING] Segment {r.get('id')} ima gresku: {r['error']}")
                continue
            audio_by_id[str(r.get("id"))] = r.get("audio_base64")

        # 4. Spajamo segmente na njihove tacne startne pozicije
        print("[TTS V2] Miksujem generisane segmente na vremensku osu...")
        stitched_count = 0
        for seg in translated_segments:
            seg_id = str(seg["id"])
            b64_audio = audio_by_id.get(seg_id)
            if not b64_audio:
                continue
            
            try:
                # Ucitavanje segmenta iz memorije
                seg_bytes = base64.b64decode(b64_audio)
                seg_audio = AudioSegment.from_file(io.BytesIO(seg_bytes), format="wav")
                
                # Izracunavanje startne pozicije u milisekundama
                start_ms = int(seg["start"] * 1000)
                
                # Nalepimo segment na tihu traku
                final_mix = final_mix.overlay(seg_audio, position=start_ms)
                stitched_count += 1
            except Exception as ex:
                print(f"[TTS ERROR] Greska pri spajanju segmenta {seg_id}: {ex}")

        print(f"[TTS V2] Uspesno spojeno {stitched_count}/{len(translated_segments)} segmenata.")

        # Cuvanje u lokalni fajl
        local_filename = f"dubbed_{uuid.uuid4().hex[:8]}.wav"
        local_path = os.path.join(settings.TEMP_WORKSPACE, local_filename)
        
        final_mix.export(local_path, format="wav")
                    
        return {
            "status": "success",
            "dubbed_audio_path": local_path
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
