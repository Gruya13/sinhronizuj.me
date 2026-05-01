import os
import runpod
from huggingface_hub import snapshot_download
from faster_whisper import WhisperModel
from vllm import LLM, SamplingParams
import tempfile
import base64

VOLUME_PATH = "/runpod-volume/models"
WHISPER_MODEL = "Systran/faster-whisper-large-v3"
QWEN_MODEL = "Qwen/Qwen2-VL-7B-Instruct-AWQ"

def ensure_model_exists(repo_id, local_dir):
    full_path = os.path.join(VOLUME_PATH, local_dir)
    if not os.path.exists(full_path):
        print(f"[{repo_id}] Model nije pronadjen na volume-u. Zapocinjem preuzimanje...")
        snapshot_download(repo_id=repo_id, local_dir=full_path, max_workers=8)
        print(f"[{repo_id}] Preuzimanje zavrseno.")
    return full_path

whisper_path = ensure_model_exists(WHISPER_MODEL, "faster-whisper-v3")
qwen_path = ensure_model_exists(QWEN_MODEL, "qwen2-vl-7b-awq")

print("Inicijalizacija Faster-Whisper modela (zauzima ~15% VRAM)...")
whisper_model = WhisperModel(whisper_path, device="cuda", compute_type="float16")

print("Inicijalizacija vLLM Qwen modela (zauzima 85% VRAM)...")
llm = LLM(
    model=qwen_path,
    quantization="awq",
    gpu_memory_utilization=0.85, # Ostavljamo memoriju za Whisper
    max_model_len=4096,
    tensor_parallel_size=1
)

def handle_transcribe(audio_base64):
    audio_data = base64.b64decode(audio_base64)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
        tmp_audio.write(audio_data)
        tmp_audio_path = tmp_audio.name
    
    segments, info = whisper_model.transcribe(tmp_audio_path, language="sr", beam_size=5)
    result = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
    
    os.remove(tmp_audio_path)
    return {"language": info.language, "segments": result}

def handle_translate(prompt, frames_base64):
    # Qwen-VL format za slanje slika
    messages = [{"role": "user", "content": []}]
    
    for img_b64 in frames_base64:
        messages[0]["content"].append({
            "type": "image_url", 
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })
        
    messages[0]["content"].append({"type": "text", "text": prompt})
    
    sampling_params = SamplingParams(temperature=0.3, max_tokens=2048)
    outputs = llm.chat(messages, sampling_params=sampling_params)
    
    return {"translation": outputs[0].outputs[0].text}

def handler(job):
    job_input = job.get('input', {})
    task_type = job_input.get('task')
    
    try:
        if task_type == "transcribe":
            audio_b64 = job_input.get("audio_base64")
            if not audio_b64:
                return {"error": "Nedostaje audio_base64"}
            return handle_transcribe(audio_b64)
            
        elif task_type == "translate":
            prompt = job_input.get("prompt")
            frames_b64 = job_input.get("frames_base64", [])
            if not prompt:
                return {"error": "Nedostaje prompt"}
            return handle_translate(prompt, frames_b64)
            
        elif task_type == "both":
            audio_b64 = job_input.get("audio_base64")
            prompt_template = job_input.get("prompt_template", "Prevedi ovaj srpski transkript na engleski uzimajuci u obzir vizuelni kontekst: {transcript}")
            frames_b64 = job_input.get("frames_base64", [])
            
            stt_result = handle_transcribe(audio_b64)
            transcript = " ".join([s["text"] for s in stt_result["segments"]])
            
            prompt = prompt_template.replace("{transcript}", transcript)
            translation_result = handle_translate(prompt, frames_b64)
            
            return {
                "transcript": stt_result["segments"],
                "translation": translation_result["translation"]
            }
        else:
            return {"error": f"Nepoznat task_type: {task_type}"}
            
    except Exception as e:
        return {"error": str(e)}

runpod.serverless.start({"handler": handler})
