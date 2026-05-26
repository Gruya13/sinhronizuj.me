import modal
import os
import base64
import tempfile
import shutil
import uuid
import glob

app = modal.App("sm-tts-openvoice")

models_nfs = modal.NetworkFileSystem.from_name("sinhronizuj-models-nfs", create_if_missing=True)
VOLUME_PATH = "/models_nfs"

def download_models():
    from huggingface_hub import hf_hub_download, snapshot_download
    
    piper_model_path = f"{VOLUME_PATH}/piper"
    os.makedirs(piper_model_path, exist_ok=True)
    
    # 1. Preuzimanje srpskog Piper modela (Marko)
    if not os.path.exists(f"{piper_model_path}/sr_Marko_medium.onnx") or \
       not os.path.exists(f"{piper_model_path}/sr_Marko_medium.onnx.json"):
        print("Preuzimam srpski Piper model (phantom9623/piper-serbian-tts)...")
        hf_hub_download(repo_id="phantom9623/piper-serbian-tts", filename="sr_Marko_medium.onnx", local_dir=piper_model_path)
        hf_hub_download(repo_id="phantom9623/piper-serbian-tts", filename="sr_Marko_medium.onnx.json", local_dir=piper_model_path)
        print("Srpski Piper model uspešno sačuvan.")
    
    # 1b. Preuzimanje srpskog Piper modela (serbski_institut)
    if not os.path.exists(f"{piper_model_path}/sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx") or \
       not os.path.exists(f"{piper_model_path}/sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx.json"):
        print("Preuzimam srpski Piper model (serbski_institut)...")
        hf_hub_download(repo_id="rhasspy/piper-voices", filename="sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx", local_dir=piper_model_path)
        hf_hub_download(repo_id="rhasspy/piper-voices", filename="sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx.json", local_dir=piper_model_path)
        print("Serbski institut model uspešno sačuvan.")
    
    # 2. Preuzimanje OpenVoice V2 konvertera
    ov_path = f"{VOLUME_PATH}/openvoice_v2"
    if not os.path.exists(f"{ov_path}/converter/checkpoint.pth"):
        print("Preuzimam OpenVoice V2 checkpoint...")
        os.makedirs(ov_path, exist_ok=True)
        snapshot_download(repo_id="myshell-ai/OpenVoiceV2", local_dir=ov_path)
        print("OpenVoice V2 checkpoint uspešno sačuvan.")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "portaudio19-dev", "build-essential", "espeak-ng")
    .run_commands(
        "git clone https://github.com/myshell-ai/OpenVoice.git /opt/OpenVoice"
    )
    .pip_install(
        "torch", "torchaudio", "transformers", "soundfile", "scipy", "librosa", 
        "huggingface-hub", "speechbrain", "silero-vad", "eng-to-ipa", "pypinyin", "cn2an", "jieba", "fastapi", "piper-tts",
        "inflect", "unidecode", "wavmark", "pydub", "whisper-timestamped", "edge-tts"
    )
)

@app.cls(image=image, gpu="L4", network_file_systems={VOLUME_PATH: models_nfs}, scaledown_window=300, timeout=1200)
class OpenVoiceWorker:
    @modal.enter()
    def setup(self):
        import torch
        # Podesavamo keš direktorijume na NFS da se modeli ne bi skidali svaki put iznova
        os.environ["HF_HOME"] = f"{VOLUME_PATH}/hf_cache"
        os.environ["TORCH_HOME"] = f"{VOLUME_PATH}/torch_cache"
        os.environ["SPEECHBRAIN_CACHE"] = f"{VOLUME_PATH}/speechbrain_cache"
        
        os.makedirs(f"{VOLUME_PATH}/hf_cache", exist_ok=True)
        os.makedirs(f"{VOLUME_PATH}/torch_cache", exist_ok=True)
        os.makedirs(f"{VOLUME_PATH}/speechbrain_cache", exist_ok=True)
        
        self.piper_model_path = f"{VOLUME_PATH}/piper"
        self.ov_path = f"{VOLUME_PATH}/openvoice_v2"
        
        # Ako modeli ne postoje, preuzimamo ih
        if not os.path.exists(f"{self.piper_model_path}/sr_Marko_medium.onnx") or \
           not os.path.exists(f"{self.piper_model_path}/sr_Marko_medium.onnx.json") or \
           not os.path.exists(f"{self.piper_model_path}/sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx") or \
           not os.path.exists(f"{self.piper_model_path}/sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx.json") or \
           not os.path.exists(f"{self.ov_path}/converter/checkpoint.pth"):
            print("Modeli nisu nađeni na NFS. Pokrećem preuzimanje...")
            download_models()
            
        # Inicijalizacija Piper srpskog generatora
        from piper.voice import PiperVoice
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Učitavam srpski Piper model...")
        self.piper_voice = PiperVoice.load(
            f"{self.piper_model_path}/sr_Marko_medium.onnx",
            config_path=f"{self.piper_model_path}/sr_Marko_medium.onnx.json"
        )
        print(f"Učitavam serbski_institut Piper model...")
        self.piper_voice_institut = PiperVoice.load(
            f"{self.piper_model_path}/sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx",
            config_path=f"{self.piper_model_path}/sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx.json"
        )
        
        import inspect
        print("POTPIS SYNTHESIZE:", inspect.signature(self.piper_voice.synthesize))
        
        # Inicijalizacija OpenVoice V2 konvertera
        import sys
        sys.path.append("/opt/OpenVoice")
        from openvoice.api import ToneColorConverter
        
        print("Učitavam OpenVoice V2 ToneColorConverter...")
        converter_dir = f"{self.ov_path}/converter"
        self.tone_color_converter = ToneColorConverter(f"{converter_dir}/config.json", device=self.device)
        self.tone_color_converter.load_ckpt(f"{converter_dir}/checkpoint.pth")
        print("Inicijalizacija uspešna.")

    def _generate_segment(self, segment: dict, ref_se_path: str, base_se_path: str, base_voice: str, should_clone: bool) -> dict:
        import sys
        sys.path.append("/opt/OpenVoice")
        import torch
        import base64
        import uuid
        import os
        import shutil
        from pydub import AudioSegment
        
        seg_id = segment["id"]
        text = segment["text"]
        max_duration = segment.get("max_duration")
        
        # Ograničenje za Piper/Edge model (ako je tekst prazan)
        if not text.strip():
            return {"id": seg_id, "audio_base64": ""}
            
        # Određivanje optimalne brzine govora (length_scale)
        length_scale = 0.90  # Malo brže od podrazumevanog za prirodniji Marko glas
        if max_duration is not None and max_duration > 0:
            # Procenjeno trajanje za normalan govor (ako koristimo Edge, takođe je slično)
            estimated_dur = len(text) / 12.5
            if estimated_dur > max_duration:
                # Izračunamo potreban odnos
                ratio = max_duration / estimated_dur
                # Limitiramo length_scale između 0.70 i 0.90 kako ne bismo previše izobličili izgovor
                length_scale = max(0.70, min(0.90, ratio))
                print(f"[OpenVoice Speed] Segment {seg_id} (max_dur={max_duration:.2f}s, est_dur={estimated_dur:.2f}s) -> postavljen length_scale={length_scale:.2f}")
        
        try:
            tmp_base_wav = f"/tmp/base_{uuid.uuid4().hex}_{seg_id}.wav"
            
            # 1. Generisanje čistog srpskog govora
            if base_voice.startswith("sr-RS-"):
                import asyncio
                import edge_tts
                tmp_base_mp3 = f"/tmp/base_{uuid.uuid4().hex}_{seg_id}.mp3"
                
                # Izračunavanje brzine u formatu edge_tts (+X% ili -X%)
                rate_percent = int((1.0 / length_scale - 1.0) * 100)
                rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
                
                async def run_edge():
                    communicate = edge_tts.Communicate(text, base_voice, rate=rate_str)
                    await communicate.save(tmp_base_mp3)
                
                asyncio.run(run_edge())
                
                # Konvertujemo u WAV za OpenVoice/librosa
                audio = AudioSegment.from_file(tmp_base_mp3)
                audio.export(tmp_base_wav, format="wav")
                if os.path.exists(tmp_base_mp3):
                    os.remove(tmp_base_mp3)
            else:
                import wave
                from piper.voice import SynthesisConfig
                
                syn_config = SynthesisConfig(length_scale=length_scale)
                voice_model = self.piper_voice
                if base_voice == "serbski_institut":
                    voice_model = self.piper_voice_institut
                
                with wave.open(tmp_base_wav, 'wb') as wav_file:
                    chunks = list(voice_model.synthesize(text, syn_config=syn_config))
                    if not chunks:
                        return {"id": seg_id, "error": f"Piper ({base_voice}) nije generisao audio čankove."}
                    sample_rate = chunks[0].sample_rate
                    sample_channels = chunks[0].sample_channels
                    sample_width = chunks[0].sample_width
                    audio_bytes = b''.join(chunk.audio_int16_bytes for chunk in chunks)
                    
                    wav_file.setnchannels(sample_channels)
                    wav_file.setsampwidth(sample_width)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_bytes)
            
            tmp_final_wav = f"/tmp/final_{uuid.uuid4().hex}_{seg_id}.wav"
            
            # 2. Primena OpenVoice Tone Color Converter-a (samo ako je kloniranje uključeno)
            if should_clone and ref_se_path and base_se_path:
                # Učitavamo speaker embedding-e sa NFS-a
                target_se = torch.load(ref_se_path, map_location=self.device)
                base_se = torch.load(base_se_path, map_location=self.device)
                
                print(f"[OpenVoice] Konvertujem boju glasa za segment {seg_id}...")
                self.tone_color_converter.convert(
                    audio_src_path=tmp_base_wav,
                    src_se=base_se,
                    tgt_se=target_se,
                    output_path=tmp_final_wav,
                    message="@MyShell"
                )
            else:
                # Ako ne kloniramo, samo kopiramo izvorni audio
                shutil.copy(tmp_base_wav, tmp_final_wav)
            
            # 3. Visokokvalitetno dodatno ubrzavanje sa librosa ukoliko i dalje prelazi max_duration
            if max_duration is not None and max_duration > 0:
                import librosa
                import numpy as np
                from scipy.io import wavfile
                
                sr, y = wavfile.read(tmp_final_wav)
                # Konverzija u float32 za librosa time stretch
                if y.dtype == np.int16:
                    y = y.astype(np.float32) / 32768.0
                elif y.dtype == np.int32:
                    y = y.astype(np.float32) / 2147483648.0
                
                generated_dur = len(y) / sr
                if generated_dur > max_duration:
                    stretch_ratio = generated_dur / max_duration
                    # Ako je prekoračenje veće od 1.01x
                    if stretch_ratio > 1.01:
                        # Limitiramo time stretch na max 1.35x
                        stretch_ratio = min(1.35, stretch_ratio)
                        print(f"[OpenVoice Librosa Stretch] Segment {seg_id} (generated={generated_dur:.2f}s, max={max_duration:.2f}s) -> ubrzavam za {stretch_ratio:.2f}x")
                        y_stretched = librosa.effects.time_stretch(y, rate=stretch_ratio)
                        
                        # Konverzija float32 [-1, 1] nazad u 16-bitni PCM
                        y_int16 = np.int16(y_stretched * 32767)
                        wavfile.write(tmp_final_wav, sr, y_int16)
            
            # Citanje finalnog fajla i konverzija u base64
            with open(tmp_final_wav, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode('utf-8')
                
            # Brisanje privremenih fajlova
            for f in [tmp_base_wav, tmp_final_wav]:
                if os.path.exists(f): os.remove(f)
                
            return {"id": seg_id, "audio_base64": audio_b64}
            
        except Exception as ex:
            import traceback
            print(f"[OpenVoice ERROR] Greška u segmentu {seg_id}: {ex}\n{traceback.format_exc()}")
            return {"id": seg_id, "error": str(ex)}

    @modal.fastapi_endpoint(method="POST")
    def task(self, data: dict):
        import sys
        from unittest.mock import MagicMock
        sys.modules['faster_whisper'] = MagicMock()
        
        sys.path.append("/opt/OpenVoice")
        import torch
        import torch.hub
        torch.hub._check_repo_is_trusted = lambda *args, **kwargs: True
        
        from openvoice import se_extractor
        import traceback
        import shutil
        
        try:
            ref_audio_b64 = data.get('reference_audio_base64')
            ref_text = data.get('reference_text')
            segments = data.get('segments')
            voice_type = data.get('voice_type', 'clone')
            
            print(f"[OpenVoice] Primljen zahtev sa voice_type: {voice_type}")
            
            # Mapiramo voice_type na base_voice i should_clone
            # Podržane opcije:
            # - clone / clone_male: muški base (Nicholas) + kloniranje
            # - clone_female: ženski base (Sophie) + kloniranje
            # - clone_marko: Marko (Piper) + kloniranje
            # - clone_institut: Institut (Piper) + kloniranje
            # - nicholas: čist Nicholas (Edge) bez kloniranja
            # - sophie: čista Sophie (Edge) bez kloniranja
            # - institut: čist Institut (Piper) bez kloniranja
            # - dragana: Dragana (referentni glas) + kloniranje
            
            if voice_type in ["clone", "clone_male"]:
                base_voice = "sr-RS-NicholasNeural"
                should_clone = True
            elif voice_type == "clone_female":
                base_voice = "sr-RS-SophieNeural"
                should_clone = True
            elif voice_type == "clone_marko":
                base_voice = "sr_Marko_medium"
                should_clone = True
            elif voice_type == "clone_institut":
                base_voice = "serbski_institut"
                should_clone = True
            elif voice_type == "nicholas":
                base_voice = "sr-RS-NicholasNeural"
                should_clone = False
            elif voice_type == "sophie":
                base_voice = "sr-RS-SophieNeural"
                should_clone = False
            elif voice_type == "institut":
                base_voice = "serbski_institut"
                should_clone = False
            elif voice_type == "dragana":
                base_voice = "sr-RS-SophieNeural" # Koristimo ženski bazni glas za Dragana referentni
                should_clone = True
            else:
                base_voice = "sr-RS-NicholasNeural"
                should_clone = True
            
            req_uuid = str(uuid.uuid4())
            ref_se_path = None
            base_se_path = None
            
            if should_clone:
                if not ref_audio_b64:
                    return {"error": "Nedostaje parametar: reference_audio_base64 za kloniranje"}
                    
                tmp_ref_path = f"/tmp/ref_{req_uuid}.wav"
                with open(tmp_ref_path, "wb") as f:
                    f.write(base64.b64decode(ref_audio_b64))
                    
                # 1. Ekstrakcija target SE (Speaker Embedding) za referentni glas
                print(f"[OpenVoice] Ekstrakujem SE za referentni audio...")
                processed_dir = f"/tmp/processed_{req_uuid}"
                os.makedirs(processed_dir, exist_ok=True)
                target_se, _ = se_extractor.get_se(tmp_ref_path, self.tone_color_converter, target_dir=processed_dir, vad=True)
                
                # 2. Ekstrakcija base SE za odabrani bazni glas (Nicholas, Sophie ili Marko)
                base_se_cache_path = f"{VOLUME_PATH}/openvoice_v2/base_se_{base_voice}.pt"
                base_se = None
                if os.path.exists(base_se_cache_path):
                    print(f"[OpenVoice] Učitavam keširani bazni SE sa {base_se_cache_path}...")
                    try:
                        base_se = torch.load(base_se_cache_path)
                    except Exception as e:
                        print(f"[OpenVoice] Greška pri učitavanju keša: {e}, generišem ponovo...")
                
                if base_se is None:
                    print(f"[OpenVoice] Generišem uzorak za bazni SE ({base_voice})...")
                    sample_text = "Dobar dan. Ovo je test za dobijanje baznog glasa koji mora biti dovoljno dugačak kako bi glasovni ekstraktor uspešno prepoznao zvučne karakteristike. Zato ponavljamo rečenicu još nekoliko puta kako bismo prešli granicu od pet sekundi govora. Dobar dan. Ovo je test za dobijanje baznog glasa."
                    tmp_sample_wav = f"/tmp/sample_base_{req_uuid}.wav"
                    
                    if base_voice.startswith("sr-RS-"):
                        import asyncio
                        import edge_tts
                        from pydub import AudioSegment
                        tmp_sample_mp3 = f"/tmp/sample_base_{req_uuid}.mp3"
                        async def run_edge():
                            communicate = edge_tts.Communicate(sample_text, base_voice)
                            await communicate.save(tmp_sample_mp3)
                        asyncio.run(run_edge())
                        
                        audio = AudioSegment.from_file(tmp_sample_mp3)
                        audio.export(tmp_sample_wav, format="wav")
                        if os.path.exists(tmp_sample_mp3):
                            os.remove(tmp_sample_mp3)
                    else:
                        import wave
                        from piper.voice import SynthesisConfig
                        syn_config = SynthesisConfig(length_scale=1.0)
                        voice_model = self.piper_voice
                        if base_voice == "serbski_institut":
                            voice_model = self.piper_voice_institut
                            
                        with wave.open(tmp_sample_wav, 'wb') as wav_file:
                            chunks = list(voice_model.synthesize(sample_text, syn_config=syn_config))
                            if not chunks:
                                return {"error": f"Piper nije uspeo da generiše uzorak za bazni SE ({base_voice})."}
                            sample_rate = chunks[0].sample_rate
                            sample_channels = chunks[0].sample_channels
                            sample_width = chunks[0].sample_width
                            audio_bytes = b''.join(chunk.audio_int16_bytes for chunk in chunks)
                            
                            wav_file.setnchannels(sample_channels)
                            wav_file.setsampwidth(sample_width)
                            wav_file.setframerate(sample_rate)
                            wav_file.writeframes(audio_bytes)
                    
                    base_se, _ = se_extractor.get_se(tmp_sample_wav, self.tone_color_converter, target_dir=processed_dir, vad=True)
                    
                    try:
                        torch.save(base_se, base_se_cache_path)
                        print(f"[OpenVoice] Bazni SE uspešno keširan na {base_se_cache_path}.")
                    except Exception as e:
                        print(f"[OpenVoice] Upozorenje: Neuspešno keširanje baznog SE: {e}")
                    
                    if os.path.exists(tmp_sample_wav):
                        os.remove(tmp_sample_wav)
                
                # Snimamo embedding-e na NFS da bi im paralelni radnici mogli pristupiti
                nfs_temp_dir = f"{VOLUME_PATH}/temp"
                os.makedirs(nfs_temp_dir, exist_ok=True)
                
                ref_se_path = f"{nfs_temp_dir}/ref_{req_uuid}.pt"
                base_se_path = f"{nfs_temp_dir}/base_{req_uuid}.pt"
                
                torch.save(target_se, ref_se_path)
                torch.save(base_se, base_se_path)
                
                # Brisanje lokalnih privremenih fajlova za ekstrakciju
                if os.path.exists(tmp_ref_path):
                    os.remove(tmp_ref_path)
                shutil.rmtree(processed_dir, ignore_errors=True)
            
            # 3. Pokretanje paralelne obrade segmenata
            if segments:
                print(f"[OpenVoice] Pokrećem paralelnu konverziju za {len(segments)} segmenata sa {base_voice} (should_clone={should_clone})...")
                from concurrent.futures import ThreadPoolExecutor
                
                def process_single(seg):
                    try:
                        return self._generate_segment(
                            seg,
                            ref_se_path=ref_se_path,
                            base_se_path=base_se_path,
                            base_voice=base_voice,
                            should_clone=should_clone
                        )
                    except Exception as e:
                        return {"id": seg.get("id"), "error": str(e)}

                # Koristimo 8 niti
                with ThreadPoolExecutor(max_workers=8) as executor:
                    results = list(executor.map(process_single, segments))
                
                # Brisanje embedding-a sa NFS-a
                if should_clone:
                    for f in [ref_se_path, base_se_path]:
                        if os.path.exists(f): os.remove(f)
                    
                return {"status": "success", "results": results}
            else:
                text = data.get('text')
                if not text:
                    if should_clone:
                        for f in [ref_se_path, base_se_path]:
                            if os.path.exists(f): os.remove(f)
                    return {"error": "Morate poslati 'text' or 'segments'"}
                
                print(f"[OpenVoice] Pokrećem pojedinačnu konverziju...")
                single_segment = {"id": "0", "text": text}
                res = self._generate_segment(single_segment, ref_se_path, base_se_path, base_voice, should_clone)
                
                if should_clone:
                    for f in [ref_se_path, base_se_path]:
                        if os.path.exists(f): os.remove(f)
                return res
                
        except Exception as e:
            import traceback
            print(f"[OpenVoice PIPELINE ERROR] {e}\n{traceback.format_exc()}")
            return {"error": f"PIPELINE_ERROR: {str(e)}\n{traceback.format_exc()}"}

@app.local_entrypoint()
def main():
    print("OpenVoice Worker je konfigurisan. Pokrenite ga preko deploy komande.")
