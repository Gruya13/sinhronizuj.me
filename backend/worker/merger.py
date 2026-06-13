import os
import subprocess
import uuid
from pydub import AudioSegment
from backend.core.config import settings

def get_video_duration(path: str) -> float:
    """
    Vraća tačnu dužinu videa u sekundama koristeći ffprobe.
    """
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return float(res.stdout.decode().strip())
    except Exception as e:
        print(f"[DYNAMIC MERGER WARNING] Greška pri dobijanju dužine videa preko ffprobe: {e}")
        return 0.0

def speedup_audio_file(input_path: str, speedup: float) -> str:
    """
    Ubrzava audio fajl pomoću FFmpeg rubberband filtera bez promene visine tona.
    Daje znatno prirodniji glas u poređenju sa atempo.
    """
    output_path = input_path.replace(".wav", f"_speedup_{speedup:.2f}.wav")
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", f"rubberband=tempo={speedup}",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path

def merge_audio_and_video(video_path: str, background_path: str, dubbed_path: str, background_vol: float = -5.0, dubbed_vol: float = 0.0) -> dict:
    """
    Klasično spajanje (statički tajminzi):
    Spaja originalnu pozadinsku muziku/efekte sa nasim novim srpskim glasom koristeći
    FFmpeg sidechaincompress filter za dinamičko prigušivanje (ducking) pozadine.
    """
    if not all(os.path.exists(p) for p in [video_path, background_path, dubbed_path]):
        return {"status": "error", "message": "Neki od potrebnih fajlova za spajanje ne postoje."}

    try:
        print(f"[FAZA 6] Miksam pozadinu ({background_vol}dB) i srpski glas ({dubbed_vol}dB) sa sidechain-om...")
        
        # Primenjujemo audio post-processing lanac na sinhronizovani vokal pomoću FFmpeg pre miksanja
        processed_dubbed_path = dubbed_path.replace(".wav", "_processed.wav")
        postprocess_cmd = [
            "ffmpeg", "-y", "-i", dubbed_path,
            "-af", "aresample=44100,highpass=f=80,lowpass=f=12000,compand=attacks=0.01:decays=0.1:points=-90/-90|-20/-10|0/-3,aecho=1.0:0.8:15:0.2",
            processed_dubbed_path
        ]
        subprocess.run(postprocess_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        final_video_path = os.path.join(settings.TEMP_WORKSPACE, f"sinhronizuj_me_final_{uuid.uuid4().hex[:6]}.mp4")
        
        # Podešavanje glasnoće
        bg_vol_str = f"volume={background_vol}dB" if background_vol != 0.0 else "volume=1.0"
        dub_vol_str = f"volume={dubbed_vol}dB" if dubbed_vol != 0.0 else "volume=1.0"
        
        # FFmpeg filter kompleks sa sidechaincompress:
        # Ulaz 1 je pozadina (muzika), ulaz 2 je srpski glas. Glas stišava pozadinu.
        filter_complex = (
            f"[1:a]{bg_vol_str},aresample=44100[bg]; "
            f"[2:a]{dub_vol_str},aresample=44100,asplit=2[voc1][voc2]; "
            f"[bg][voc1]sidechaincompress=threshold=0.1:ratio=5:attack=15:release=250:makeup=1.0[compressed_bg]; "
            f"[compressed_bg][voc2]amix=inputs=2:duration=first:dropout_transition=0[outa]"
        )
        
        command = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", background_path,
            "-i", processed_dubbed_path,
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            final_video_path
        ]
        
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(processed_dubbed_path):
            os.remove(processed_dubbed_path)
            
        return {
            "status": "success",
            "final_video_path": final_video_path,
            "dubbed_audio_path": dubbed_path
        }
        
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"FFmpeg greska: {e.stderr.decode('utf-8', errors='ignore')}"}
    except Exception as e:
        return {"status": "error", "message": f"Greska pri spajanju videa: {str(e)}"}

def merge_audio_and_video_dynamic(
    video_path: str,
    background_path: str,
    tts_segments: list,
    background_vol: float = -5.0,
    dubbed_vol: float = 0.0,
    max_video_stretch: float = 1.05
) -> dict:
    """
    Dinamički video time stretching:
    Decomponuje video na govorničke segmente i pauze. Ukoliko je srpski TTS segment duži od originalnog
    vremenskog slota, usporava taj video segment (do max_video_stretch) i prilagođava brzinu audia,
    održavajući savršenu sinhronizaciju bez crtanog efekta prebrzog glasa.
    """
    if not all(os.path.exists(p) for p in [video_path, background_path]):
        return {"status": "error", "message": "Neki od potrebnih fajlova za spajanje ne postoje."}

    if not tts_segments:
        # Ako nema segmenata, radimo fallback na klasično spajanje
        print("[DYNAMIC MERGER WARNING] Nema segmenata za dinamičko spajanje. Radim fallback na statički mix.")
        return {"status": "error", "message": "Nema segmenata za dinamičko spajanje."}

    try:
        print(f"[DYNAMIC MERGER] Započinjem dinamički video time stretching za {len(tts_segments)} segmenata...")
        
        # Sortiramo segmente po vremenu početka
        tts_segments = sorted(tts_segments, key=lambda x: x["start"])
        
        video_duration = get_video_duration(video_path)
        if video_duration == 0.0:
            bg_audio = AudioSegment.from_wav(background_path)
            video_duration = len(bg_audio) / 1000.0
            
        blocks = []
        last_time = 0.0
        
        for seg in tts_segments:
            start = seg["start"]
            end = seg["end"]
            
            # Ako postoji značajna pauza, pravimo gap blok
            if start > last_time + 0.05:
                blocks.append({
                    "type": "gap",
                    "start": last_time,
                    "end": start,
                    "stretch_factor": 1.0,
                    "audio_speedup": 1.0
                })
            elif start < last_time:
                start = last_time
                
            orig_duration = max(0.05, end - start)
            tts_duration = seg["duration"]
            
            factor = tts_duration / orig_duration
            
            if factor > 1.0:
                video_stretch = min(max_video_stretch, factor)
                audio_speedup = factor / video_stretch
            else:
                video_stretch = 1.0
                audio_speedup = 1.0
                
            blocks.append({
                "type": "speech",
                "id": seg["id"],
                "start": start,
                "end": end,
                "stretch_factor": video_stretch,
                "audio_speedup": audio_speedup,
                "tts_path": seg["path"],
                "duration": tts_duration,
                "bg_volume": seg.get("bg_volume", 0.0)
            })
            
            last_time = end
            
        if video_duration > last_time + 0.05:
            blocks.append({
                "type": "gap",
                "start": last_time,
                "end": video_duration,
                "stretch_factor": 1.0,
                "audio_speedup": 1.0
            })
            
        print(f"[DYNAMIC MERGER] Podelio sam video na {len(blocks)} blokova.")
        
        cmd_inputs = ["-i", video_path, "-i", background_path]
        
        video_filters = []
        audio_mix_filters = []
        audio_voc_filters = []
        
        concat_video_labels = []
        concat_mix_labels = []
        concat_voc_labels = []
        
        temp_files_to_clean = []
        speech_speedups = {}
        
        for idx, block in enumerate(blocks):
            start = block["start"]
            end = block["end"]
            duration = end - start
            stretch = block["stretch_factor"]
            new_duration = duration * stretch
            
            # 1. Video filter
            v_out = f"v{idx}"
            video_filters.append(f"[0:v]trim=start={start}:end={end},setpts={stretch}*(PTS-STARTPTS)[{v_out}]")
            concat_video_labels.append(v_out)
            
            # 2. Background audio filter
            a_bg_out = f"abg{idx}"
            if stretch != 1.0:
                audio_mix_filters.append(f"[1:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,atempo={1.0 / stretch}[{a_bg_out}]")
            else:
                audio_mix_filters.append(f"[1:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[{a_bg_out}]")
                
            if block["type"] == "speech":
                speech_speedups[block["id"]] = block["audio_speedup"]
                tts_path = block["tts_path"]
                # Ako je potrebno blago ubrzanje glasa
                if block["audio_speedup"] > 1.01:
                    print(f"[DYNAMIC MERGER] Segment {idx} (original={duration:.2f}s, tts={block['duration']:.2f}s) -> video_stretch={stretch:.2f}x, audio_speedup={block['audio_speedup']:.2f}x")
                    try:
                        tts_path = speedup_audio_file(tts_path, block["audio_speedup"])
                        temp_files_to_clean.append(tts_path)
                    except Exception as e:
                        print(f"[DYNAMIC MERGER ERROR] Neuspešno ubrzanje audia: {e}, koristim originalni tts")
                else:
                    print(f"[DYNAMIC MERGER] Segment {idx} (original={duration:.2f}s, tts={block['duration']:.2f}s) -> video_stretch={stretch:.2f}x (audio_speedup=1.0x)")
                
                tts_input_idx = len(cmd_inputs) // 2
                cmd_inputs.extend(["-i", tts_path])
                
                combined_bg_vol = background_vol + block.get("bg_volume", 0.0)
                bg_vol_str = f"{combined_bg_vol}dB" if combined_bg_vol != 0.0 else "0dB"
                dub_vol_str = f"{dubbed_vol}dB" if dubbed_vol != 0.0 else "0dB"
                
                a_bg_res = f"abgres{idx}"
                audio_mix_filters.append(f"[{a_bg_out}]volume={bg_vol_str},aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[{a_bg_res}]")
                
                a_tts_res_side = f"attsres_side{idx}"
                a_tts_res_mix = f"attsres_mix{idx}"
                # Primenjujemo resampling, EQ (highpass/lowpass), kompresor (compand) i room reverb (aecho) za bolju integraciju vokala
                audio_mix_filters.append(
                    f"[{tts_input_idx}:a]aresample=44100,"
                    f"highpass=f=80,"
                    f"lowpass=f=12000,"
                    f"compand=attacks=0.01:decays=0.1:points=-90/-90|-20/-10|0/-3,"
                    f"aecho=1.0:0.8:15:0.2,"
                    f"volume={dub_vol_str},"
                    f"aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[{a_tts_res_side}][{a_tts_res_mix}]"
                )
                
                a_comp_bg = f"acompbg{idx}"
                # Primenjujemo sidechaincompress: vokal dinamički stišava pozadinsku muziku
                audio_mix_filters.append(f"[{a_bg_res}][{a_tts_res_side}]sidechaincompress=threshold=0.1:ratio=5:attack=15:release=250:makeup=1.0[{a_comp_bg}]")
                
                a_mix_out = f"amix{idx}"
                audio_mix_filters.append(f"[{a_comp_bg}][{a_tts_res_mix}]amix=inputs=2:duration=first:dropout_transition=0[{a_mix_out}]")
                concat_mix_labels.append(a_mix_out)
                
                # Vocals-only stream za LipSync
                a_voc_out = f"avoc{idx}"
                audio_voc_filters.append(f"[{tts_input_idx}:a]volume={dub_vol_str},aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[{a_voc_out}]")
                concat_voc_labels.append(a_voc_out)
            else:
                a_bg_res = f"abgres{idx}"
                bg_vol_str = f"{background_vol}dB" if background_vol != 0.0 else "0dB"
                audio_mix_filters.append(f"[{a_bg_out}]volume={bg_vol_str},aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[{a_bg_res}]")
                concat_mix_labels.append(a_bg_res)
                
                a_voc_out = f"avoc{idx}"
                audio_voc_filters.append(f"aevalsrc=0:d={new_duration},aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[{a_voc_out}]")
                concat_voc_labels.append(a_voc_out)
                
        concat_video_str = "".join([f"[{lbl}]" for lbl in concat_video_labels]) + f"concat=n={len(blocks)}:v=1:a=0[outv]"
        concat_mix_str = "".join([f"[{lbl}]" for lbl in concat_mix_labels]) + f"concat=n={len(blocks)}:v=0:a=1[outa]"
        concat_voc_str = "".join([f"[{lbl}]" for lbl in concat_voc_labels]) + f"concat=n={len(blocks)}:v=0:a=1[outa_voc]"
        
        filter_complex = "; ".join(video_filters + audio_mix_filters + audio_voc_filters + [concat_video_str, concat_mix_str, concat_voc_str])
        
        final_video_path = os.path.join(settings.TEMP_WORKSPACE, f"sinhronizuj_me_final_stretched_{uuid.uuid4().hex[:6]}.mp4")
        final_vocals_path = os.path.join(settings.TEMP_WORKSPACE, f"sinhronizuj_me_vocals_stretched_{uuid.uuid4().hex[:6]}.wav")
        
        command = ["ffmpeg", "-y"]
        command.extend(cmd_inputs)
        command.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", "192k",
            final_video_path,
            "-map", "[outa_voc]",
            "-c:a", "pcm_s16le",
            final_vocals_path
        ])
        
        print("[DYNAMIC MERGER] Pokrećem FFmpeg za generisanje rastegnutog videa i vokala...")
        res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if res.returncode != 0:
            print(f"[DYNAMIC MERGER ERROR] FFmpeg je pukao sa kodom {res.returncode}")
            print(f"Error log: {res.stderr.decode('utf-8', errors='ignore')}")
            return {"status": "error", "message": f"FFmpeg dynamic stretching nije uspeo: {res.stderr.decode('utf-8')}"}
            
        for f in temp_files_to_clean:
            if os.path.exists(f):
                os.remove(f)
                
        print(f"[DYNAMIC MERGER] Uspešno kreiran rastegnuti video: {final_video_path}")
        return {
            "status": "success",
            "final_video_path": final_video_path,
            "dubbed_audio_path": final_vocals_path,
            "speech_speedups": speech_speedups
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Greška pri dinamičkom spajanju: {str(e)}"}
