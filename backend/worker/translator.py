import json
import requests
from google import genai
from google.genai import types
from backend.core.config import settings

def translate_segments(segments: list, original_language: str = "en") -> dict:
    """
    Prevodi segmente koristeći Gemini API, sa automatskim fallback-om na lokalni
    Gemma 2 model (preko Ollama) ako Gemini nije dostupan ili je preopterećen.
    """
    # Priprema payload-a i instrukcija
    payload = json.dumps(segments, ensure_ascii=False)
    system_instruction = """
    Ti si profesionalni prevodilac. Dobićeš JSON niz segmenata.
    KRITIČNO VAŽNO:
    1. Vrati isključivo JSON niz (Array) sa istim brojem elemenata.
    2. NEMOJ MENJATI ključeve 'start' i 'end'.
    3. NEMOJ MENJATI vrednosti (brojeve) u 'start' i 'end' poljima. 
    4. Prevedi samo 'text' na srpski jezik.
    5. Stručne termine (API, Frontend, itd.) ne prevodi.
    6. Izlaz mora biti čist JSON, bez dodatnog teksta.
    """

    # 1. Pokušaj sa Gemini API-jem (ako postoji ključ)
    if settings.GEMINI_API_KEY:
        try:
            print("[FAZA 4] Pokušavam prevod preko Gemini API-ja...")
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=payload,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            translated_segments = json.loads(response.text)
            return {"status": "success", "translated_segments": translated_segments, "engine": "gemini"}
        except Exception as e:
            print(f"[UPOZORENJE] Gemini API greška: {str(e)}. Prelazim na lokalni fallback (Ollama)...")

    # 2. Fallback na lokalni Ollama (Gemma 2)
    try:
        print("[FAZA 4] Pokušavam lokalni prevod (Ollama + Gemma 2 9B)...")
        url = "http://localhost:11434/api/generate"
        full_prompt = f"{system_instruction}\n\nEvo JSON-a za prevod:\n{payload}"
        
        data = {
            "model": "gemma4",
            "prompt": full_prompt,
            "stream": False,
            "format": "json"
        }
        
        response = requests.post(url, json=data, timeout=300)
        response.raise_for_status()
        
        result_text = response.json().get('response', '[]')
        translated_segments = json.loads(result_text)
        
        return {
            "status": "success",
            "translated_segments": translated_segments,
            "engine": "ollama_gemma2"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Prevod nije uspeo ni na jednom servisu. Poslednja greška: {str(e)}"
        }
