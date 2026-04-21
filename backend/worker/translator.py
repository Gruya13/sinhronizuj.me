import json
import requests
from google import genai
from google.genai import types
from backend.core.config import settings

def translate_segments(segments: list, original_language: str = "en") -> dict:
    """
    Prevodi segmente koristeći Gemini API, sa automatskim fallback-om na lokalni
    Gemma 4 model (preko Ollama).
    """
    # Priprema payload-a i instrukcija
    payload = json.dumps(segments, ensure_ascii=False)
    system_instruction = """
    TI SI PROFESIONALNI PREVODILAC I JSON PARSER.
    TVOJ ZADATAK JE DA PREVEDEŠ POLJE 'text' NA SRPSKI JEZIK.
    
    STRIKTNA PRAVILA:
    1. IZLAZ MORA BITI ISKLJUČIVO VALIDAN JSON NIZ (ARRAY).
    2. NEMOJ DODAVATI NIKAKAV UVOD, OBJAŠNJENJA ILI ZAKLJUČAK.
    3. POLJA 'start' I 'end' SU SVETINJA - NE SMEŠ IH MENJATI NI ZA JEDNU MILISEKUNDU.
    4. BROJ SEGMENATA U IZLAZU MORA BITI IDENTIČAN BROJU SEGMENATA U ULAZU.
    5. PREVEDI SAMO SADRŽAJ POLJA 'text'.
    6. STRUČNE TERMINE IZ IT SEKTORA (API, Frontend, Backend, Pod, itd.) OSTAVI U ORIGINALU.
    7. KORISTI PRIRODAN SRPSKI JEZIK.
    
    FORMAT IZLAZA:
    [
      {"start": 0.0, "end": 2.0, "text": "Prevedeni tekst"},
      ...
    ]
    """

    # 1. Pokušaj sa Gemini API-jem (ako postoji ključ)
    if settings.GEMINI_API_KEY:
        try:
            print("[FAZA 4] Prevođenje: Gemini API (Gemma 4 logika)...")
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=payload,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )
            translated_segments = json.loads(response.text)
            return {"status": "success", "translated_segments": translated_segments, "engine": "gemini"}
        except Exception as e:
            print(f"[UPOZORENJE] Gemini greška: {str(e)}. Prelazim na lokalnu Gemma 4...")

    # 2. Fallback na lokalni Ollama (Gemma 4)
    print("[FAZA 4] Prevođenje: Lokalna Gemma 4 (Ollama) sa deljenjem u pakete...")
    url = "http://localhost:11434/api/generate"
    
    # Delimo segmente u pakete od 20 da model ne bi pukao zbog token limita
    chunk_size = 20
    all_translated_segments = []
    
    for i in range(0, len(segments), chunk_size):
        chunk = segments[i:i+chunk_size]
        payload = json.dumps(chunk, ensure_ascii=False)
        full_prompt = f"{system_instruction}\n\nEvo JSON-a za prevod:\n{payload}"
        
        data = {
            "model": "gemma4",
            "prompt": full_prompt,
            "stream": False,
            "format": "json",
            "options": {"num_predict": 4096} # Osiguravamo dovoljno "mastila" za dugacke odgovore
        }
        
        try:
            print(f"   -> Prevodim paket {i//chunk_size + 1} od {(len(segments)-1)//chunk_size + 1}...")
            response = requests.post(url, json=data, timeout=300)
            response.raise_for_status()
            
            result_text = response.json().get('response', '[]')
            
            try:
                translated_chunk = json.loads(result_text)
                if isinstance(translated_chunk, dict):
                    translated_chunk = [translated_chunk]
                all_translated_segments.extend(translated_chunk)
            except json.JSONDecodeError as e:
                print(f"[UPOZORENJE] Gemma nije vratila validan JSON za paket {i//chunk_size + 1}. Preskacem... Greska: {str(e)}")
                # Ako nece da ga lepo prevede, zadrzavamo original da ne puca
                all_translated_segments.extend(chunk)
                
        except Exception as e:
            print(f"[GREŠKA] Problem sa Gemma 4 zahtevom: {str(e)}")
            # Fallback na originalni tekst
            all_translated_segments.extend(chunk)

    if not all_translated_segments:
        return {
            "status": "error",
            "message": "Prevod nije uspeo. Gemma je vratila potpuno prazan rezultat."
        }
        
    return {
        "status": "success",
        "translated_segments": all_translated_segments,
        "engine": "ollama_gemma4_chunked"
    }
