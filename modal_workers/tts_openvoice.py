import modal
import os
import base64
import tempfile
import shutil
import uuid
import glob
import numpy as np

app = modal.App("sm-tts-openvoice")

models_nfs = modal.NetworkFileSystem.from_name("sinhronizuj-models-nfs", create_if_missing=True)
VOLUME_PATH = "/models_nfs"

def download_models():
    from huggingface_hub import hf_hub_download, snapshot_download
    
    piper_model_path = f"{VOLUME_PATH}/piper"
    os.makedirs(piper_model_path, exist_ok=True)
    
    # Preuzimanje srpskog Piper modela (Marko)
    if not os.path.exists(f"{piper_model_path}/sr_Marko_medium.onnx") or \
       not os.path.exists(f"{piper_model_path}/sr_Marko_medium.onnx.json"):
        print("Preuzimam srpski Piper model (phantom9623/piper-serbian-tts)...")
        hf_hub_download(repo_id="phantom9623/piper-serbian-tts", filename="sr_Marko_medium.onnx", local_dir=piper_model_path)
        hf_hub_download(repo_id="phantom9623/piper-serbian-tts", filename="sr_Marko_medium.onnx.json", local_dir=piper_model_path)
        print("Srpski Piper model uspešno sačuvan.")
    
    # Preuzimanje OpenVoice V2 konvertera
    ov_path = f"{VOLUME_PATH}/openvoice_v2"
    if not os.path.exists(f"{ov_path}/converter/checkpoint.pth"):
        print("Preuzimam OpenVoice V2 checkpoint...")
        os.makedirs(ov_path, exist_ok=True)
        snapshot_download(repo_id="myshell-ai/OpenVoiceV2", local_dir=ov_path)
        print("OpenVoice V2 checkpoint uspešno sačuvan.")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "git-lfs", "ffmpeg", "portaudio19-dev", "build-essential", "espeak-ng")
    .run_commands(
        "git lfs install",
        "git clone https://github.com/myshell-ai/OpenVoice.git /opt/OpenVoice"
    )
    .pip_install(
        "torch", "torchaudio", "transformers", "soundfile", "scipy", "librosa", 
        "huggingface-hub", "speechbrain", "silero-vad", "eng-to-ipa", "pypinyin", "cn2an", "jieba", "fastapi", "piper-tts",
        "inflect", "unidecode", "wavmark", "pydub", "whisper-timestamped", "resemble-enhance"
    )
)

@app.cls(image=image, gpu="L4", network_file_systems={VOLUME_PATH: models_nfs}, scaledown_window=300, timeout=1200)
class OpenVoiceWorker:
    @modal.enter()
    def setup(self):
        import torch
        # Postavljanje keš direktorijuma na NFS
        os.environ["HF_HOME"] = f"{VOLUME_PATH}/hf_cache"
        os.environ["TORCH_HOME"] = f"{VOLUME_PATH}/torch_cache"
        os.environ["SPEECHBRAIN_CACHE"] = f"{VOLUME_PATH}/speechbrain_cache"
        
        os.makedirs(f"{VOLUME_PATH}/hf_cache", exist_ok=True)
        os.makedirs(f"{VOLUME_PATH}/torch_cache", exist_ok=True)
        os.makedirs(f"{VOLUME_PATH}/speechbrain_cache", exist_ok=True)
        
        self.piper_model_path = f"{VOLUME_PATH}/piper"
        self.ov_path = f"{VOLUME_PATH}/openvoice_v2"
        
        # Ako modeli ne postoje na NFS, preuzimamo ih
        if not os.path.exists(f"{self.piper_model_path}/sr_Marko_medium.onnx") or \
           not os.path.exists(f"{self.piper_model_path}/sr_Marko_medium.onnx.json") or \
           not os.path.exists(f"{self.ov_path}/converter/checkpoint.pth"):
            print("Modeli nisu nađeni na NFS. Pokrećem preuzimanje...")
            download_models()
            
        # Inicijalizacija Piper srpskog generatora (Marko)
        from piper.voice import PiperVoice
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print("Učitavam srpski Piper model (Marko)...")
        self.piper_voice = PiperVoice.load(
            f"{self.piper_model_path}/sr_Marko_medium.onnx",
            config_path=f"{self.piper_model_path}/sr_Marko_medium.onnx.json"
        )
        
        # Inicijalizacija OpenVoice V2 konvertera
        import sys
        sys.path.append("/opt/OpenVoice")
        from openvoice.api import ToneColorConverter
        
        print("Učitavam OpenVoice V2 ToneColorConverter...")
        self.tone_color_converter = ToneColorConverter(
            f"{self.ov_path}/converter/config.json",
            device=self.device
        )
        self.tone_color_converter.load_ckpt(
            f"{self.ov_path}/converter/checkpoint.pth"
        )
        
        # Inicijalizacija Resemble Enhance (preuzimanje modela ako ne postoji)
        print("Preuzimam/Inicijalizujem Resemble Enhance model...")
        from resemble_enhance.enhancer.inference import denoise as resemble_denoise_fn
        from resemble_enhance.enhancer.inference import enhance as resemble_enhance_fn
        try:
            dummy_wav = torch.zeros(22050, dtype=torch.float32)
            dummy_denoised, denoise_sr = resemble_denoise_fn(dummy_wav, 22050, self.device)
            _, _ = resemble_enhance_fn(dummy_denoised, denoise_sr, self.device, nfe=1, solver="midpoint", lambd=0.9, tau=0.5)
            print("Resemble Enhance model uspešno inicijalizovan i spreman.")
        except Exception as e:
            print(f"[Resemble Enhance Init WARNING] {e}")
            
        print("Svi modeli su uspešno inicijalizovani.")

    def _generate_segment(self, segment, ref_se_path, base_se_path, enhance_params=None, disable_openvoice=False, disable_enhance=False):
        """
        Sintetizuje tekst u govor pomoću Piper-a (bazni model Marko) i menja mu boju glasa
        prema referentnim speeker embedding-ovima pomoću OpenVoice-a.
        """
        import torch
        import wave
        from scipy.io import wavfile
        
        seg_id = segment.get("id", "0")
        text = segment.get("text", "")
        length_scale = segment.get("length_scale", 1.0)
        
        if not text.strip():
            return {"id": seg_id, "error": "Prazan tekst za sintezu."}
            
        try:
            tmp_base_wav = f"/tmp/base_{uuid.uuid4().hex}_{seg_id}.wav"
            tmp_final_wav = f"/tmp/final_{uuid.uuid4().hex}_{seg_id}.wav"
            
            # 1. Sinteza preko Piper-a (sr_Marko_medium)
            from piper.voice import SynthesisConfig
            syn_config = SynthesisConfig(length_scale=length_scale)
            
            with wave.open(tmp_base_wav, 'wb') as wav_file:
                chunks = list(self.piper_voice.synthesize(text, syn_config=syn_config))
                if not chunks:
                    return {"id": seg_id, "error": "Piper nije generisao audio čankove."}
                sample_rate = chunks[0].sample_rate
                sample_channels = chunks[0].sample_channels
                sample_width = chunks[0].sample_width
                audio_bytes = b''.join(chunk.audio_int16_bytes for chunk in chunks)
                
                wav_file.setnchannels(sample_channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)
                
            # 2. Promena boje glasa pomoću OpenVoice V2
            if not disable_openvoice:
                target_se = torch.load(ref_se_path)
                base_se = torch.load(base_se_path)
                
                self.tone_color_converter.convert(
                    audio_src_path=tmp_base_wav,
                    src_se=base_se,
                    tgt_se=target_se,
                    output_path=tmp_final_wav,
                    message="@MyShell"
                )
            else:
                shutil.copy2(tmp_base_wav, tmp_final_wav)
            
            # 3. Poboljšanje zvuka pomoću Resemble Enhance (Denoise & Bandwidth Extension)
            if not disable_enhance:
                if enhance_params is None:
                    enhance_params = {
                        "denoise": True,
                        "nfe": 64,
                        "solver": "midpoint",
                        "lambd": 0.9,
                        "tau": 0.3
                    }
                
                try:
                    import torchaudio
                    from resemble_enhance.enhancer.inference import denoise as resemble_denoise_fn
                    from resemble_enhance.enhancer.inference import enhance as resemble_enhance_fn
                    
                    dwav, sr = torchaudio.load(tmp_final_wav)
                    dwav = dwav.mean(dim=0)  # Konverzija u mono ako je stereo
                    
                    # 1. Korak: Denoise (ako je omogućeno)
                    if enhance_params.get("denoise", True):
                        dwav, sr = resemble_denoise_fn(dwav, sr, self.device)
                    
                    # 2. Korak: Enhance (CFM model)
                    wav_enhanced, new_sr = resemble_enhance_fn(
                        dwav, sr, self.device, 
                        nfe=enhance_params.get("nfe", 64), 
                        solver=enhance_params.get("solver", "midpoint"), 
                        lambd=enhance_params.get("lambd", 0.9), 
                        tau=enhance_params.get("tau", 0.5)
                    )
                    
                    # Čuvanje poboljšanog audia nazad na disk
                    torchaudio.save(tmp_final_wav, wav_enhanced.unsqueeze(0).cpu(), new_sr)
                    print(f"[Resemble Enhance] Uspešno poboljšan segment {seg_id} (sa {sr}Hz na {new_sr}Hz)")
                except Exception as enh_err:
                    print(f"[Resemble Enhance WARNING] Neuspešno poboljšanje segmenta {seg_id}: {enh_err}")
                
            # Čitanje finalnog fajla i konverzija u base64
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
            
            disable_openvoice = data.get("disable_openvoice", False)
            disable_enhance = data.get("disable_enhance", False)
            
            enhance_params = {
                "denoise": data.get("enhance_denoise", True),
                "nfe": data.get("enhance_nfe", 64),
                "solver": data.get("enhance_solver", "midpoint"),
                "lambd": data.get("enhance_lambd", 0.9),
                "tau": data.get("enhance_tau", 0.3)
            }
            
            req_uuid = str(uuid.uuid4())
            ref_se_path = None
            base_se_path = None
            
            if not disable_openvoice:
                if not ref_audio_b64:
                    return {"error": "Nedostaje parametar: reference_audio_base64"}
                    
                tmp_ref_path = f"/tmp/ref_{req_uuid}.wav"
                
                # Snimanje referentnog audia na disk
                with open(tmp_ref_path, "wb") as f:
                    f.write(base64.b64decode(ref_audio_b64))
                    
                # 1. Ekstrakcija Speaker Embedding-a (SE) za referentni target glas
                print("[OpenVoice] Ekstrakujem SE za referentni audio...")
                processed_dir = f"/tmp/processed_{req_uuid}"
                os.makedirs(processed_dir, exist_ok=True)
                
                target_se, _ = se_extractor.get_se(tmp_ref_path, self.tone_color_converter, target_dir=processed_dir, vad=True)
                
                # 2. Generisanje/Učitavanje baznog SE za Marko Piper model
                base_se_cache_path = f"{VOLUME_PATH}/openvoice_v2/base_se.pt"
                base_se = None
                if os.path.exists(base_se_cache_path):
                    print(f"[OpenVoice] Učitavam keširani bazni SE sa {base_se_cache_path}...")
                    try:
                        base_se = torch.load(base_se_cache_path)
                    except Exception as e:
                        print(f"[OpenVoice] Greška pri učitavanju keša: {e}, generišem ponovo...")
                
                if base_se is None:
                    print("[OpenVoice] Generišem uzorak za bazni SE preko Piper-a...")
                    sample_text = "Dobar dan. Ovo je test za dobijanje baznog glasa koji mora biti dovoljno dugačak kako bi glasovni ekstraktor uspešno prepoznao zvučne karakteristike. Zato ponavljamo rečenicu još nekoliko puta kako bismo prešli granicu od pet sekundi govora. Dobar dan. Ovo je test za dobijanje baznog glasa."
                    tmp_sample_wav = f"/tmp/sample_base_{req_uuid}.wav"
                    import wave
                    from piper.voice import SynthesisConfig
                    syn_config = SynthesisConfig(length_scale=1.0)
                    
                    with wave.open(tmp_sample_wav, 'wb') as wav_file:
                        chunks = list(self.piper_voice.synthesize(sample_text, syn_config=syn_config))
                        if not chunks:
                            return {"error": "Piper nije uspeo da generiše uzorak za bazni SE."}
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
                
                # Snimanje embedding-a na NFS
                nfs_temp_dir = f"{VOLUME_PATH}/temp"
                os.makedirs(nfs_temp_dir, exist_ok=True)
                
                ref_se_path = f"{nfs_temp_dir}/ref_{req_uuid}.pt"
                base_se_path = f"{nfs_temp_dir}/base_{req_uuid}.pt"
                
                torch.save(target_se, ref_se_path)
                torch.save(base_se, base_se_path)
                
                # Brisanje privremenih fajlova
                if os.path.exists(tmp_ref_path):
                    os.remove(tmp_ref_path)
                shutil.rmtree(processed_dir, ignore_errors=True)
            
            # 3. Paralelna obrada segmenata u ThreadPoolExecutor-u
            if segments:
                print(f"[OpenVoice] Pokrećem paralelnu konverziju za {len(segments)} segmenata sa Piper-Marko modelom...")
                from concurrent.futures import ThreadPoolExecutor
                
                def process_single(seg):
                    try:
                        return self._generate_segment(
                            seg,
                            ref_se_path=ref_se_path,
                            base_se_path=base_se_path,
                            enhance_params=enhance_params,
                            disable_openvoice=disable_openvoice,
                            disable_enhance=disable_enhance
                        )
                    except Exception as e:
                        return {"id": seg.get("id"), "error": str(e)}

                with ThreadPoolExecutor(max_workers=8) as executor:
                    results = list(executor.map(process_single, segments))
                
                # Brisanje embedding-a sa NFS-a
                for f in [ref_se_path, base_se_path]:
                    if f and os.path.exists(f): os.remove(f)
                    
                return {"status": "success", "results": results}
            else:
                text = data.get('text')
                if not text:
                    for f in [ref_se_path, base_se_path]:
                        if f and os.path.exists(f): os.remove(f)
                    return {"error": "Morate poslati 'text' ili 'segments'"}
                
                print("[OpenVoice] Pokrećem pojedinačnu konverziju...")
                single_segment = {"id": "0", "text": text}
                res = self._generate_segment(single_segment, ref_se_path, base_se_path, enhance_params, disable_openvoice, disable_enhance)
                
                for f in [ref_se_path, base_se_path]:
                    if f and os.path.exists(f): os.remove(f)
                return res
                
        except Exception as e:
            import traceback
            print(f"[OpenVoice PIPELINE ERROR] {e}\n{traceback.format_exc()}")
            return {"error": f"PIPELINE_ERROR: {str(e)}\n{traceback.format_exc()}"}

@app.local_entrypoint()
def main():
    print("OpenVoice Worker je konfigurisan.")
