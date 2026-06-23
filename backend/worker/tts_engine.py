import os
import uuid
import base64
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

def synthesize_audio(vocals_path: str, translated_segments: list, voice_type: str = "clone", 
                     disable_openvoice: bool = False, disable_enhance: bool = False,
                     progress_callback=None, all_segments: list = None, workspace_path: str = None,
                     project_id: str = None) -> dict:
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

    # 1. Priprema i isecanje referentnih audia za sve klonirane glasove
    if progress_callback:
        progress_callback(detail="Priprema referentnih audia za kloniranje glasova...")
    
    reference_audios = {}
    default_ref_b64 = None
    default_ref_text = "Ovo je originalni glas iz videa."
    
    # Pronađemo sve jedinstvene klonirane glasove iz segmenata
    clone_voices = set()
    ref_source_segments = all_segments if all_segments else translated_segments
    for seg in ref_source_segments:
        v_type = seg.get("voice_type")
        if v_type and v_type.startswith("clone"):
            clone_voices.add(v_type)
            
    # Ako nema nijednog specifičnog clone_X glasa, koristimo podrazumevani "clone"
    if not clone_voices:
        clone_voices.add(voice_type)
        
    try:
        ref_audio_all = AudioSegment.from_wav(vocals_path)
        
        for c_voice in clone_voices:
            try:
                good_segments = []
                total_duration = 0.0
                
                # Sakupi više segmenata za bolji referentni glas za ovaj konkretan voice_type
                for seg in ref_source_segments:
                    seg_v_type = seg.get("voice_type") or voice_type
                    if seg_v_type == c_voice:
                        orig_txt = seg.get("original_text") or seg.get("original")
                        if orig_txt and seg.get("start") is not None and seg.get("end") is not None:
                            duration = seg["end"] - seg["start"]
                            if duration >= 1.5:
                                good_segments.append(seg)
                                total_duration += duration
                                if total_duration >= 10.0:
                                    break
                                    
                # Fallback na kraće segmente
                if total_duration < 6.0:
                    for seg in ref_source_segments:
                        seg_v_type = seg.get("voice_type") or voice_type
                        if seg_v_type == c_voice and seg not in good_segments:
                            orig_txt = seg.get("original_text") or seg.get("original")
                            if orig_txt and seg.get("start") is not None and seg.get("end") is not None:
                                duration = seg["end"] - seg["start"]
                                if duration >= 0.5:
                                    good_segments.append(seg)
                                    total_duration += duration
                                    if total_duration >= 10.0:
                                        break
                
                if good_segments:
                    good_segments = sorted(good_segments, key=lambda x: x["start"])
                    ref_sub_audio = None
                    ref_text_parts = []
                    
                    for seg in good_segments:
                        start_ms = int(seg["start"] * 1000)
                        end_ms = int(seg["end"] * 1000)
                        chunk = ref_audio_all[start_ms:end_ms]
                        chunk = chunk.fade_in(50).fade_out(50)
                        
                        if ref_sub_audio is None:
                            ref_sub_audio = chunk
                        else:
                            ref_sub_audio = ref_sub_audio.append(chunk, crossfade=100)
                        ref_text_parts.append(seg.get("original_text") or seg.get("original"))
                        
                    buffer = io.BytesIO()
                    ref_sub_audio.export(buffer, format="wav")
                    ref_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    ref_text = " ".join(ref_text_parts)
                    
                    reference_audios[c_voice] = ref_b64
                    if default_ref_b64 is None:
                        default_ref_b64 = ref_b64
                        default_ref_text = ref_text
                        
                    print(f"[TTS V2] Uspešno pripremljen referentni glas za {c_voice} sa {len(good_segments)} segmenata ({total_duration:.2f}s).")
            except Exception as e:
                print(f"[TTS V2 WARNING] Greška pri pripremi referentnog glasa za {c_voice}: {e}")
                
        # Ako nismo napravili nijedan referentni audio, uradimo fallback na prvih 15s celog vokala
        if not reference_audios:
            duration_ms = len(ref_audio_all)
            limit_ms = min(duration_ms, 15000)
            ref_sub_audio = ref_audio_all[:limit_ms]
            
            buffer = io.BytesIO()
            ref_sub_audio.export(buffer, format="wav")
            default_ref_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            reference_audios[voice_type] = default_ref_b64
            print("[WARNING] Nije nađen referentni segment. Koristim prvih 15 sekundi audia kao fallback.")
            
    except Exception as e:
        return {"status": "error", "message": f"Greška pri pripremi referentnog audia: {e}"}
 
    # 2. Učitavamo originalni vokal da bismo znali ukupnu dužinu i izračunali maksimalna trajanja segmenata
    try:
        ref_audio = AudioSegment.from_wav(vocals_path)
        video_duration_ms = len(ref_audio)
    except Exception as e:
        return {"status": "error", "message": f"Greška pri učitavanju originalnog vokala: {e}"}
 
    # Priprema segmenata za slanje na Modal sa dinamičkim length_scale faktorom
    modal_segments = []
    for idx, s in enumerate(translated_segments):
        orig_duration = max(0.05, s["end"] - s["start"])
        char_count = len(s["text"])
        
        # Procena prirodnog trajanja na srpskom (Piper-Marko model)
        estimated_duration = (char_count / 16.0) + 0.2
        target_scale = orig_duration / estimated_duration
        
        # Ograničavamo length_scale između 0.75 i 1.25
        length_scale = min(max(target_scale, 0.75), 1.25)
        
        seg_voice = s.get("voice_type") or voice_type
        print(f"[TTS V2] Segment {s['id']} (voice_type={seg_voice}, video_dur={orig_duration:.2f}s, chars={char_count}) -> proračunat length_scale: {length_scale:.2f}", flush=True)
        
        modal_segments.append({
            "id": str(s["id"]),
            "text": s["text"],
            "max_duration": 0.0,
            "length_scale": float(round(length_scale, 2)),
            "voice_type": seg_voice
        })
    
    payload = {
        "segments": modal_segments,
        "reference_audios": reference_audios,
        "reference_audio_base64": default_ref_b64,
        "reference_text": default_ref_text,
        "voice_type": voice_type,
        "disable_openvoice": disable_openvoice,
        "disable_enhance": disable_enhance,
        "enhance_tau": settings.ENHANCE_TAU,
        "enhance_lambd": settings.ENHANCE_LAMBD,
        "project_id": project_id,
        "callback_url": f"{settings.BACKEND_URL}/api/v1/project/{project_id}/progress" if project_id and settings.BACKEND_URL else None
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
                workspace = workspace_path or settings.TEMP_WORKSPACE
                seg_path = os.path.join(workspace, seg_filename)
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
        workspace = workspace_path or settings.TEMP_WORKSPACE
        local_path = os.path.join(workspace, local_filename)
        
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
