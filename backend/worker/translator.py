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
    Ti si profesionalni prevodilac i asistent za sinhronizaciju videa na srpski jezik.
    Dobićeš JSON niz segmenata gde svaki segment ima 'start', 'end' i 'text' (koji je na originalnom jeziku).
    Tvoj zadatak je sledeći:
    1. Brzo proceni temu videa iz tekstova (npr. IT, mehanika, gaming).
    2. Identifikuj stručne termine (npr. frontend, framework, engine, API) i NEMOJ IH PREVODITI na srpski.
    3. Prevedi vrednost polja 'text' na srpski jezik na prirodan i razgovoran način, deklinirajući engleske termine po padežima gde je to prikladno (npr. 'poveži se na API').
    4. Zadrži istu dužinu rečenice kako bi se uklopila u tajming sinhronizacije. 
    5. Ne menjaj apsolutno 'start' i 'end' vrednosti.
    6. Vrati isključivo validan JSON niz (Array) objekata u istom formatu kao ulaz, spreman za parsiranje u Python-u.
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
            "model": "gemma2:9b",
            "prompt": full_prompt,
            "stream": False,
            "format": "json"
        }
        
        response = requests.post(url, json=data, timeout=600)
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
