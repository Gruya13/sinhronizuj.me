import modal

# Definišemo sliku sa instaliranim ffmpeg-om i demucs-om
image_demucs = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install("demucs", "fastapi", "uvicorn", "torchcodec==0.11.1")
)

app = modal.App("sm-demucs")

@app.cls(
    gpu="T4", # T4 GPU za brzu separaciju zvuka
    image=image_demucs,
    timeout=600,
    scaledown_window=300,
    secrets=[modal.Secret.from_dotenv()]
)
class DemucsWorker:
    @modal.asgi_app()
    def task(self):
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        import base64
        import tempfile
        import os
        import subprocess
        import shutil

        web_app = FastAPI()

        @web_app.post("/")
        async def handle_request(request: Request):
            # Provera API ključa
            expected_key = os.environ.get("MODAL_API_KEY")
            if expected_key:
                api_key = request.headers.get("X-API-Key")
                if api_key != expected_key:
                    return JSONResponse(status_code=403, content={"error": "Neovlašćen pristup. API ključ je neispravan."})

            data = await request.json()
            audio_b64 = data.get("audio_base64")
            if not audio_b64:
                return {"error": "audio_base64 is required"}

            print("[DEMUCS-WORKER] Primljen audio zahtev za separaciju.")
            try:
                audio_data = base64.b64decode(audio_b64)
            except Exception as e:
                return {"error": f"Neispravan base64 audio: {str(e)}"}

            # Kreiramo privremene fajlove unutar kontejnera
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                tmp_audio.write(audio_data)
                tmp_audio_path = tmp_audio.name

            output_dir = tempfile.mkdtemp()

            callback_url = data.get("callback_url")
            audio_duration = data.get("audio_duration", 0.0)

            def send_progress(url, pct, dt):
                if not url: return
                import urllib.request
                import json
                try:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps({"percent": pct, "detail": dt}).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    api_key = os.environ.get("MODAL_API_KEY")
                    if api_key:
                        req.add_header("X-API-Key", api_key)
                    with urllib.request.urlopen(req, timeout=5) as response:
                        response.read()
                except Exception as err:
                    print(f"[DEMUCS PROGRESS ERROR] {err}", flush=True)

            import threading
            import time
            stop_progress = threading.Event()

            def progress_loop(url, dur):
                est_total = max(5.0, dur / 10.0)
                interval = est_total / 10.0
                current_pct = 5
                send_progress(url, current_pct, "Izolacija vokala (Demucs) započeta...")
                while not stop_progress.is_set() and current_pct < 95:
                    time.sleep(interval)
                    if stop_progress.is_set():
                        break
                    current_pct += 10
                    send_progress(url, current_pct, f"Odvajanje vokala i muzike: {current_pct}%")

            t_progress = None
            if callback_url:
                t_progress = threading.Thread(target=progress_loop, args=(callback_url, audio_duration))
                t_progress.start()

            try:
                # Pokrecemo demucs preko komandne linije
                command = [
                    "demucs",
                    "-n", "htdemucs",
                    "--two-stems", "vocals",
                    "-o", output_dir,
                    tmp_audio_path
                ]
                
                print(f"[DEMUCS-WORKER] Komanda: {' '.join(command)}")
                result = subprocess.run(command, capture_output=True, text=True)
                
                stop_progress.set()
                if t_progress:
                    t_progress.join()
                
                if result.returncode != 0:
                    print(f"[DEMUCS-WORKER] Greška pri izvršavanju demucs-a: {result.stderr}")
                    send_progress(callback_url, 0, f"Greška pri separaciji vokala: {result.stderr}")
                    return {"error": f"Demucs error: {result.stderr}"}

                send_progress(callback_url, 100, "Separacija vokala uspešno završena.")

                # Demucs kreira fajlove na lokaciji: output_dir/htdemucs/{base_filename}/vocals.wav i no_vocals.wav
                base_filename = os.path.splitext(os.path.basename(tmp_audio_path))[0]
                model_output_dir = os.path.join(output_dir, "htdemucs", base_filename)
                
                vocals_path = os.path.join(model_output_dir, "vocals.wav")
                no_vocals_path = os.path.join(model_output_dir, "no_vocals.wav")
                
                if not (os.path.exists(vocals_path) and os.path.exists(no_vocals_path)):
                    print("[DEMUCS-WORKER] Izlazni fajlovi nisu pronađeni!")
                    return {"error": "Demucs output files (vocals.wav/no_vocals.wav) not found"}

                print("[DEMUCS-WORKER] Uspešno generisani vokali i pozadinska muzika. Kodiram u base64...")
                with open(vocals_path, "rb") as f_vocals:
                    vocals_b64 = base64.b64encode(f_vocals.read()).decode('utf-8')
                with open(no_vocals_path, "rb") as f_no_vocals:
                    no_vocals_b64 = base64.b64encode(f_no_vocals.read()).decode('utf-8')

                return {
                    "status": "success",
                    "vocals_base64": vocals_b64,
                    "no_vocals_base64": no_vocals_b64
                }

            except Exception as e:
                print(f"[DEMUCS-WORKER] Neočekivana greška: {e}")
                return {"error": str(e)}
            finally:
                # Čišćenje
                if os.path.exists(tmp_audio_path):
                    os.remove(tmp_audio_path)
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir, ignore_errors=True)

        return web_app
