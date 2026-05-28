import os
import requests
import uuid
import base64
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint
from backend.worker.preprocessor import upload_to_minio

def synthesize_audio(vocals_path: str, translated_segments: list, voice_type: str = "clone", 
                     disable_openvoice: bool = False, disable_enhance: bool = False,
                     progress_callback=None) -> dict:
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
        # Sakupi više segmenata za bolji referentni glas (ciljamo 5-10 sekundi ukupno)
        good_segments = []
        total_duration = 0.0
        
        for seg in translated_segments:
            if seg.get("original_text") and seg.get("start") is not None and seg.get("end") is not None:
                duration = seg["end"] - seg["start"]
                if duration >= 1.5: # Samo segmenti koji imaju dovoljno govora
                    good_segments.append(seg)
                    total_duration += duration
                    if total_duration >= 8.0: # Dovoljno nam je 8 sekundi
                        break
                        
        # Ako nismo nakupili dovoljno od dužih, probajmo da dodamo i kraće od 1.5s (ali > 0.5s)
        if total_duration < 5.0:
            for seg in translated_segments:
                if seg not in good_segments:
                    if seg.get("original_text") and seg.get("start") is not None and seg.get("end") is not None:
                        duration = seg["end"] - seg["start"]
                        if duration >= 0.5:
                            good_segments.append(seg)
                            total_duration += duration
                            if total_duration >= 8.0:
                                break
                                
        ref_audio_all = AudioSegment.from_wav(vocals_path)
        
        if good_segments:
            # Sortiramo ih po vremenu početka kako bi se spojili prirodnim redosledom
            good_segments = sorted(good_segments, key=lambda x: x["start"])
            
            # Spajamo audio delove i tekst
            ref_sub_audio = None
            ref_text_parts = []
            
            for seg in good_segments:
                start_ms = int(seg["start"] * 1000)
                end_ms = int(seg["end"] * 1000)
                # Isecanje i spajanje
                chunk = ref_audio_all[start_ms:end_ms]
                
                # Dodajemo blagi fade_in i fade_out da eliminišemo pucketanje na krajevima segmenata
                chunk = chunk.fade_in(50).fade_out(50)
                
                if ref_sub_audio is None:
                    ref_sub_audio = chunk
                else:
                    ref_sub_audio = ref_sub_audio.append(chunk, crossfade=100)
                ref_text_parts.append(seg["original_text"])
                
            # Izvoz u buffer
            buffer = io.BytesIO()
            ref_sub_audio.export(buffer, format="wav")
            ref_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            ref_text = " ".join(ref_text_parts)
            print(f"[TTS V2] Uspešno spojeno {len(good_segments)} referentnih segmenata (ukupno trajanje: {total_duration:.2f}s) za kloniranje glasa.")
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

    # Priprema segmenata za slanje na Modal sa dinamičkim length_scale faktorom
    # kako bi Piper generisao audio direktno u optimalnom tempu za dužinu segmenta.
    modal_segments = []
    for idx, s in enumerate(translated_segments):
        orig_duration = max(0.05, s["end"] - s["start"])
        char_count = len(s["text"])
        
        # Procena prirodnog trajanja na srpskom (Piper-Marko model)
        # Prosečno 16 karaktera u sekundi + 0.2s fiksna pauza
        estimated_duration = (char_count / 16.0) + 0.2
        target_scale = orig_duration / estimated_duration
        
        # Ograničavamo length_scale između 0.75 (brži izgovor) i 1.25 (sporiji izgovor)
        # kako bi glas zvučao prirodno bez preteranog ubrzanja/usporavanja
        length_scale = min(max(target_scale, 0.75), 1.25)
        
        print(f"[TTS V2] Segment {s['id']} (video_dur={orig_duration:.2f}s, chars={char_count}) -> proračunat length_scale: {length_scale:.2f}", flush=True)
        
        modal_segments.append({
            "id": str(s["id"]),
            "text": s["text"],
            "max_duration": 0.0,
            "length_scale": float(round(length_scale, 2))
        })
    
    payload = {
        "segments": modal_segments,
        "reference_audio_base64": ref_b64,
        "reference_text": ref_text,
        "voice_type": voice_type,
        "disable_openvoice": disable_openvoice,
        "disable_enhance": disable_enhance,
        "enhance_tau": settings.ENHANCE_TAU,
        "enhance_lambd": settings.ENHANCE_LAMBD
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
