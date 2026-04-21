import json
from google import genai
from google.genai import types
from backend.core.config import settings

def translate_segments(segments: list, original_language: str = "en") -> dict:
    """
    Koristi Google Gemini API za pametan prevod segmenata.
    Analizira kontekst, stiti strucne termine i vraca JSON objekat
    sa istim tajminzima ali tekstom na srpskom jeziku.
    """
    if not settings.GEMINI_API_KEY:
        return {"status": "error", "message": "Nije pronadjen GEMINI_API_KEY u okruzenju (.env). Dodajte kljuc da biste nastavili."}

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    # Konvertujemo Python listu recnika u JSON string kako bi je LLM razumeo
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
    
    try:
        print("[FAZA 4] Šaljem transkript Gemini LLM-u na pametni prevod i analizu konteksta...")
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=payload,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2, # Nizak temperature parametar za preciznost bez previse kreativnosti
                response_mime_type="application/json" # Tera Gemini da vrati samo cist JSON, bez markdowna
            )
        )
        
        translated_segments = json.loads(response.text)
        
        return {
            "status": "success",
            "translated_segments": translated_segments
        }
    except Exception as e:
        return {"status": "error", "message": f"Greska pri Gemini prevodu: {str(e)}"}
