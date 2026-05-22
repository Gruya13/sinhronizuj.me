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
    from huggingface_hub import snapshot_download, HfApi
    from transformers import VitsModel, AutoTokenizer
    import torch
    
    # 1. Preuzimanje srpskog VITS modela
    print("Preuzimam srpski VITS model (facebook/mms-tts-srp)...")
    srp_model_path = f"{VOLUME_PATH}/mms-tts-srp"
    os.makedirs(srp_model_path, exist_ok=True)
    VitsModel.from_pretrained("facebook/mms-tts-srp")
    AutoTokenizer.from_pretrained("facebook/mms-tts-srp")
    # Snimamo ih na NFS
    model = VitsModel.from_pretrained("facebook/mms-tts-srp")
    tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-srp")
    model.save_pretrained(srp_model_path)
    tokenizer.save_pretrained(srp_model_path)
    print("Srpski VITS model uspešno sačuvan.")
    
    # 2. Preuzimanje OpenVoice V2 konvertera
    print("Preuzimam OpenVoice V2 checkpoint...")
    ov_path = f"{VOLUME_PATH}/openvoice_v2"
    os.makedirs(ov_path, exist_ok=True)
    snapshot_download(repo_id="myshell-ai/OpenVoiceV2", local_dir=ov_path)
    print("OpenVoice V2 checkpoint uspešno sačuvan.")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "portaudio19-dev", "build-essential")
    .run_commands(
        "git clone https://github.com/myshell-ai/OpenVoice.git /opt/OpenVoice"
    )
    .pip_install(
        "torch", "torchaudio", "transformers", "soundfile", "scipy", "librosa", 
        "huggingface-hub", "speechbrain", "silero-vad", "eng-to-ipa", "pypinyin", "cn2an", "jieba", "fastapi"
    )
)

@app.cls(image=image, gpu="L4", network_file_systems={VOLUME_PATH: models_nfs}, scaledown_window=300, timeout=1200)
class OpenVoiceWorker:
    @modal.enter()
    def setup(self):
        # Podesavamo keš direktorijume na NFS da se modeli ne bi skidali svaki put iznova
        os.environ["HF_HOME"] = f"{VOLUME_PATH}/hf_cache"
        os.environ["TORCH_HOME"] = f"{VOLUME_PATH}/torch_cache"
        os.environ["SPEECHBRAIN_CACHE"] = f"{VOLUME_PATH}/speechbrain_cache"
        
        os.makedirs(f"{VOLUME_PATH}/hf_cache", exist_ok=True)
        os.makedirs(f"{VOLUME_PATH}/torch_cache", exist_ok=True)
        os.makedirs(f"{VOLUME_PATH}/speechbrain_cache", exist_ok=True)
        
        self.srp_model_path = f"{VOLUME_PATH}/mms-tts-srp"
        self.ov_path = f"{VOLUME_PATH}/openvoice_v2"
        
        # Ako modeli ne postoje, preuzimamo ih
        if not os.path.exists(f"{self.srp_model_path}/config.json") or not os.path.exists(f"{self.ov_path}/converter/checkpoint.pth"):
            print("Modeli nisu nađeni na NFS. Pokrećem preuzimanje...")
            download_models()
            
        # Inicijalizacija VITS srpskog generatora na GPU
        import torch
        from transformers import VitsModel, AutoTokenizer
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Učitavam srpski VITS model na uređaj: {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.srp_model_path)
        self.vits_model = VitsModel.from_pretrained(self.srp_model_path).to(self.device)
        
        # Inicijalizacija OpenVoice V2 konvertera
        # OpenVoice kod zahteva da budemo u /opt/OpenVoice direktorijumu ili da ga dodamo u sys.path
        import sys
        sys.path.append("/opt/OpenVoice")
        from openvoice.api import ToneColorConverter
        
        print("Učitavam OpenVoice V2 ToneColorConverter...")
        converter_dir = f"{self.ov_path}/converter"
        self.tone_color_converter = ToneColorConverter(f"{converter_dir}/config.json", device=self.device)
        self.tone_color_converter.load_ckpt(f"{converter_dir}/checkpoint.pth")
        print("Inicijalizacija uspešna.")

    @modal.method()
    def generate_segment(self, segment: dict, ref_se_path: str, base_se_path: str) -> dict:
        import sys
        sys.path.append("/opt/OpenVoice")
        import torch
        import soundfile as sf
        import numpy as np
        
        seg_id = segment["id"]
        text = segment["text"]
        
        # Ograničenje za VITS model (ako je tekst prazan)
        if not text.strip():
            return {"id": seg_id, "audio_base64": ""}
            
        try:
            # 1. Generisanje čistog srpskog govora preko Meta VITS modela
            inputs = self.tokenizer(text=text, return_tensors="pt").to(self.device)
            with torch.no_grad():
                output = self.vits_model(**inputs)
            
            # Dobijamo sirovi audio signal
            vits_audio = output.audio[0].cpu().numpy()
            sampling_rate = self.vits_model.config.sampling_rate
            
            # Snimamo u privremeni fajl u kontejneru
            tmp_base_wav = f"/tmp/base_{uuid.uuid4().hex}_{seg_id}.wav"
            sf.write(tmp_base_wav, vits_audio, sampling_rate)
            
            # Učitavamo speaker embedding-e sa NFS-a
            target_se = torch.load(ref_se_path, map_location=self.device)
            base_se = torch.load(base_se_path, map_location=self.device)
            
            # 2. Primena OpenVoice Tone Color Converter-a
            tmp_final_wav = f"/tmp/final_{uuid.uuid4().hex}_{seg_id}.wav"
            
            print(f"[OpenVoice] Konvertujem boju glasa za segment {seg_id}...")
            self.tone_color_converter.convert(
                audio_src_path=tmp_base_wav,
                src_se=base_se,
                tgt_se=target_se,
                output_path=tmp_final_wav,
                message="@MyShell"
            )
            
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
        sys.path.append("/opt/OpenVoice")
        import torch
        from openvoice import se_extractor
        import traceback
        import shutil
        
        try:
            ref_audio_b64 = data.get('reference_audio_base64')
            ref_text = data.get('reference_text') # nije striktno neophodan za OpenVoice ali ga dobijamo
            segments = data.get('segments')
            
            if not ref_audio_b64:
                return {"error": "Nedostaje parametar: reference_audio_base64"}
                
            req_uuid = str(uuid.uuid4())
            tmp_ref_path = f"/tmp/ref_{req_uuid}.wav"
            
            # Snimamo referentni audio na disk
            with open(tmp_ref_path, "wb") as f:
                f.write(base64.b64decode(ref_audio_b64))
                
            # 1. Ekstrakcija Speaker Embedding-a (SE) za referentni glas
            print(f"[OpenVoice] Ekstrakujem SE za referentni audio...")
            processed_dir = f"/tmp/processed_{req_uuid}"
            os.makedirs(processed_dir, exist_ok=True)
            
            # Ekstrakcija target SE
            target_se, _ = se_extractor.get_se(tmp_ref_path, self.tone_color_converter, target_dir=processed_dir, vad=True)
            
            # 2. Generisanje i ekstrakcija Speaker Embedding-a za bazni srpski glas
            # Pošto je bazni glas uvek isti (naš Meta VITS srpski model), možemo generisati kratak uzorak teksta 
            # da bismo izvukli base_se. Još bolje: možemo izvući base_se jednom i keširati ga, ali izvlačenje je brzo.
            print(f"[OpenVoice] Generišem uzorak za bazni SE...")
            sample_text = "Dobar dan, ovo je test za dobijanje baznog glasa."
            inputs = self.tokenizer(text=sample_text, return_tensors="pt").to(self.device)
            with torch.no_grad():
                output = self.vits_model(**inputs)
            vits_audio = output.audio[0].cpu().numpy()
            tmp_sample_wav = f"/tmp/sample_base_{req_uuid}.wav"
            import soundfile as sf
            sf.write(tmp_sample_wav, vits_audio, self.vits_model.config.sampling_rate)
            
            base_se, _ = se_extractor.get_se(tmp_sample_wav, self.tone_color_converter, target_dir=processed_dir, vad=True)
            
            # Snimamo embedding-e na NFS da bi im paralelni radnici mogli pristupiti
            nfs_temp_dir = f"{VOLUME_PATH}/temp"
            os.makedirs(nfs_temp_dir, exist_ok=True)
            
            ref_se_path = f"{nfs_temp_dir}/ref_{req_uuid}.pt"
            base_se_path = f"{nfs_temp_dir}/base_{req_uuid}.pt"
            
            torch.save(target_se, ref_se_path)
            torch.save(base_se, base_se_path)
            
            # Brisanje lokalnih privremenih fajlova za ekstrakciju
            for f in [tmp_ref_path, tmp_sample_wav]:
                if os.path.exists(f): os.remove(f)
            shutil.rmtree(processed_dir, ignore_errors=True)
            
            # 3. Pokretanje paralelne obrade segmenata u lokalnom ThreadPool-u radi maksimalne brzine i izbegavanja hladnog starta
            if segments:
                print(f"[OpenVoice] Pokrećem paralelnu konverziju za {len(segments)} segmenata preko lokalnog ThreadPoolExecutor-a...")
                from concurrent.futures import ThreadPoolExecutor
                
                def process_single(seg):
                    try:
                        return self.generate_segment(
                            seg,
                            ref_se_path=ref_se_path,
                            base_se_path=base_se_path
                        )
                    except Exception as e:
                        return {"id": seg.get("id"), "error": str(e)}

                # Koristimo 8 niti za paralelnu obradu na istom GPU-u
                with ThreadPoolExecutor(max_workers=8) as executor:
                    results = list(executor.map(process_single, segments))
                
                # Brisanje embedding-a sa NFS-a
                for f in [ref_se_path, base_se_path]:
                    if os.path.exists(f): os.remove(f)
                    
                return {"status": "success", "results": results}
            else:
                text = data.get('text')
                if not text:
                    for f in [ref_se_path, base_se_path]:
                        if os.path.exists(f): os.remove(f)
                    return {"error": "Morate poslati 'text' ili 'segments'"}
                
                print(f"[OpenVoice] Pokrećem pojedinačnu konverziju...")
                single_segment = {"id": "0", "text": text}
                res = self.generate_segment.local(single_segment, ref_se_path, base_se_path)
                
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
