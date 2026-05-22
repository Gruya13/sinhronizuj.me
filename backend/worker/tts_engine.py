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
        progress_callback(detail=f"Priprema referentnog audia (tip glasa: {voice_type})...")
    
    try:
        if voice_type == "dragana":
            # Koristimo predefinisani srpski zenski glas Dragana
            # Putanja na Celery radniku (u Dockeru se nalazi u /app/backend/assets/serbian_female.wav)
            ref_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "serbian_female.wav")
            if not os.path.exists(ref_path):
                # Fallback ako fajl ne postoji iz nekog razloga na VPS-u
                print(f"[WARNING] Predefinisani glas Dragana nije nadjen na putanji {ref_path}. Radim fallback na kloniranje.")
                voice_type = "clone"
            else:
                ref_audio_all = AudioSegment.from_wav(ref_path)
                buffer = io.BytesIO()
                ref_audio_all.export(buffer, format="wav")
                ref_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                ref_text = "Ovaj glas nije instaliran, vi slušate prethodno snimljen primer."
                print(f"[TTS V2] Uspešno učitan predefinisani srpski glas Dragana iz assets.")

        if voice_type != "dragana": # "clone" ili fallback
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
        "reference_text": ref_text
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
        from pydub.effects import speedup
        
        for idx, seg in enumerate(translated_segments):
            seg_id = str(seg["id"])
            b64_audio = audio_by_id.get(seg_id)
            if not b64_audio:
                continue
            
            try:
                # Ucitavanje segmenta iz memorije
                seg_bytes = base64.b64decode(b64_audio)
                seg_audio = AudioSegment.from_file(io.BytesIO(seg_bytes), format="wav")
                
                # 1. Računamo maksimalno dozvoljeno trajanje do početka sledećeg segmenta da bismo sprečili preklapanje (dupli audio)
                start_ms = int(seg["start"] * 1000)
                if idx < len(translated_segments) - 1:
                    next_start_ms = int(translated_segments[idx + 1]["start"] * 1000)
                    max_allowed_duration_ms = next_start_ms - start_ms
                else:
                    max_allowed_duration_ms = video_duration_ms - start_ms
                
                max_allowed_duration = max_allowed_duration_ms / 1000.0

                # 2. Osnovno lagano ubrzanje govora za 1.05x radi prirodnije dinamike
                try:
                    seg_audio = speedup(seg_audio, playback_speed=1.05)
                except Exception as ex_speed:
                    print(f"[TTS WARNING] Neuspešno osnovno ubrzanje segmenta {seg_id}: {ex_speed}")

                # 3. Dinamičko dodatno ubrzanje samo ako generisani audio prevazilazi maksimalno dozvoljeni prozor
                generated_duration = seg_audio.duration_seconds
                if generated_duration > max_allowed_duration and max_allowed_duration > 0:
                    additional_speed = generated_duration / max_allowed_duration
                    # Limitiramo dodatno ubrzanje na maksimalno 1.50x kako glas ne bi zvučao previše izobličeno
                    if additional_speed > 1.50:
                        additional_speed = 1.50
                    
                    try:
                        seg_audio = speedup(seg_audio, playback_speed=additional_speed)
                        print(f"[TTS SPEEDUP] Segment {seg_id} dinamički ubrzan za {additional_speed:.2f}x (max dozvoljeno: {max_allowed_duration:.2f}s, novo trajanje: {seg_audio.duration_seconds:.2f}s)")
                    except Exception as ex_speed2:
                        print(f"[TTS WARNING] Neuspešno dodatno ubrzanje segmenta {seg_id}: {ex_speed2}")

                # 4. Trimovanje segmenta samo kao krajnja mera ako i posle maksimalnog ubrzanja prelazi granicu
                if len(seg_audio) > max_allowed_duration_ms and max_allowed_duration_ms > 0:
                    print(f"[TTS TRIM] Skraćujem segment {seg_id} sa {len(seg_audio)}ms na {max_allowed_duration_ms}ms da sprečim preklapanje.")
                    seg_audio = seg_audio[:max_allowed_duration_ms]
                
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
