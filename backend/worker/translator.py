import json
import requests
from google import genai
from google.genai import types
from backend.core.config import settings

def translate_segments(segments: list, original_language: str = "en", progress_callback=None) -> dict:
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
            
            # Obaveštavamo o završenom celom bloku (Gemini ne podržava rečenicu-po-rečenicu lako u ovom formatu)
            if progress_callback:
                for i, seg in enumerate(translated_segments):
                    progress_callback(i, len(translated_segments), "gemini", seg["text"])
                    
            return {"status": "success", "translated_segments": translated_segments, "engine": "gemini"}
        except Exception as e:
            print(f"[UPOZORENJE] Gemini greška: {str(e)}. Prelazim na lokalnu Gemma 4...")

    # 2. Fallback na lokalni Ollama (Gemma 4)
    print("[FAZA 4] Prevođenje: Lokalna Gemma 4 (Rečenicu po rečenicu)...")
    url = "http://localhost:11434/api/generate"
    
    all_translated_segments = []
    
    sentence_instruction = """
    TI SI PROFESIONALNI PREVODILAC.
    TVOJ ZADATAK JE DA PREVEDEŠ ZADATU REČENICU NA SRPSKI JEZIK.
    STRIKTNA PRAVILA:
    1. VRATI SAMO I ISKLJUČIVO PREVEDENI TEKST.
    2. BEZ UVODA, BEZ OBJAŠNJENJA, BEZ NAVODNIKA OKO TEKSTA.
    3. AKO NEMA ŠTA DA SE PREVEDE (NPR. SAMO ZNAKOVI), VRATI ORIGINAL.
    """
    
    for i, segment in enumerate(segments):
        original_text = segment.get("text", "").strip()
        
        if not original_text:
            all_translated_segments.append(segment)
            continue
            
        full_prompt = f"{sentence_instruction}\n\nTekst za prevod:\n{original_text}"
        
        data = {
            "model": "gemma4",
            "prompt": full_prompt,
            "stream": False
        }
        
        try:
            print(f"   -> Prevodim segment {i + 1} od {len(segments)}...")
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            
            result_text = response.json().get('response', '').strip()
            
            if not result_text:
                result_text = original_text
                
            translated_segment = {
                "start": segment["start"],
                "end": segment["end"],
                "text": result_text
            }
            all_translated_segments.append(translated_segment)
            
            # Šaljemo progres za svaku rečenicu
            if progress_callback:
                progress_callback(i, len(segments), "ollama", result_text)
                
        except Exception as e:
            print(f"[GREŠKA] Problem sa Gemma 4 za segment {i + 1}: {str(e)}")
            all_translated_segments.append(segment)

    return {
        "status": "success",
        "translated_segments": all_translated_segments,
        "engine": "ollama_gemma4_sentence_by_sentence"
    }

