import os
import json
import re
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint
from .dialect import clean_thought_tags

GLOSSARY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "glossaries.json")

def load_glossaries() -> dict:
    if os.path.exists(GLOSSARY_FILE):
        try:
            with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[GLOSSARY] Greška pri čitanju {GLOSSARY_FILE}: {e}")
    return {}

def detect_topic_and_terms(transcript_text: str) -> dict:
    """
    Poziva Modal Lektor da detektuje temu, izvuče 5-10 ključnih stručnih termina
    i prepozna specifične entitete (imena, brendove, lokacije, skraćenice) koji zahtevaju transkripciju.
    Vraća rečnik sa ključevima 'topic', 'terms' i 'entities'.
    """
    if not settings.MODAL_LEKTOR_URL:
        return {"topic": "other", "terms": [], "entities": []}
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "Analyze the following English transcript from a video. "
        "1. Identify the main topic of the video (choose one of: 'welding_and_crafts', 'biology_and_nature', 'technology_and_it', or 'other').\n"
        "2. Extract 5-10 key technical nouns or noun phrases (jargon) that are central to this video. DO NOT extract common verbs, common adjectives, or general verbal phrases (e.g. do NOT extract 'laughs at everything', 'disappears without explanation', or 'feels the deepest').\n"
        "3. Extract any specific proper nouns like person names, brand names, software, tools, locations, or acronyms (e.g. 'Claude', 'vLLM', 'AI', 'San Francisco', 'Docker') that will need phonetic transcription in Serbian.\n\n"
        "Respond strictly in JSON format with the following keys:\n"
        "{\n"
        "  \"topic\": \"topic_name\",\n"
        "  \"terms\": [\"term1\", \"term2\", ...],\n"
        "  \"entities\": [\"entity1\", \"entity2\", ...]\n"
        "}\n\n"
        f"TRANSCRIPT:\n{transcript_text}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    try:
        from backend.worker.translator import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        content = clean_thought_tags(content)
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        data = json.loads(content)
        return {
            "topic": data.get("topic", "other"),
            "terms": data.get("terms", []),
            "entities": data.get("entities", [])
        }
    except Exception as e:
        print(f"[GLOSSARY DETECT ERROR] Greška pri detekciji teme i entiteta: {e}")
        return {"topic": "other", "terms": [], "entities": []}

def translate_terms_to_serbian(terms: list) -> dict:
    """
    Prevedi listu engleskih stručnih pojmova i entiteta na srpski jezik (ekavica, latinica).
    """
    if not terms or not settings.MODAL_LEKTOR_URL:
        return {}
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "You are an expert English-to-Serbian translator. Translate or transcribe the following list of English terms, "
        "proper nouns, and acronyms into standard Serbian as spoken in Serbia (ekavica, latinica). "
        "Keep translations short, accurate, and natural.\n\n"
        "IMPORTANT RULES FOR TRANSLATION AND TRANSCRIPTION:\n"
        "- TECHNICAL TERMS: Translate them to standard Serbian ekavica (e.g. 'welding' -> 'zavarivanje', 'pipes' -> 'cevi'). Avoid dialectal or Croatian words.\n"
        "- BRAND NAMES, SOFTWARE, AND NAMES: Transcribe them PHONETICALLY as they are pronounced (e.g. 'Claude' -> 'Klod', 'Docker' -> 'Doker', 'San Francisco' -> 'San Francisko', 'Luna' -> 'Luna'). Never leave them in English spelling.\n"
        "- ACRONYMS: Write them phonetically as they are pronounced in Serbian, without dashes (e.g. 'AI' -> 'Ej Aj', 'IT' -> 'Aj Ti', 'TTS' -> 'Ti Ti Es').\n"
        "- GRAMMAR AND VERBS: Only translate noun terms, proper names, and acronyms. If a term is a verb or common phrase, translate it using standard grammatically correct Serbian ekavica (e.g. 'laughs' -> 'smeje se', NOT 'smehuje se'). Ensure proper Serbian grammar at all times.\n\n"
        "Respond strictly in JSON format (a single dictionary where keys are English terms and values are Serbian translations/transcriptions):\n"
        "{\n"
        "  \"english term\": \"serbian translation\"\n"
        "}\n\n"
        f"TERMS: {json.dumps(terms)}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    try:
        from backend.worker.translator import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        content = clean_thought_tags(content)
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        return json.loads(content)
    except Exception as e:
        print(f"[GLOSSARY TRANSLATE ERROR] Greška pri prevođenju termina/entiteta: {e}")
        return {}

def get_dynamic_glossary(transcript_text: str) -> str:
    """
    Glavna funkcija koja orkestrira detekciju teme, proveru u bazi i automatski prevod nepoznatih reči i entiteta.
    Vraća formatirani tekstualni glosar za prompt lektora i prevodioca.
    """
    print("[GLOSSARY] Pokrećem analizu teme i prepoznavanje termina i entiteta...", flush=True)
    detect_res = detect_topic_and_terms(transcript_text)
    topic = detect_res.get("topic", "other")
    terms = detect_res.get("terms", [])
    entities = detect_res.get("entities", [])
    
    all_items_to_translate = list(set(terms + entities))
    print(f"[GLOSSARY] Detektovana tema: {topic}. Izvučeni termini i entiteti: {all_items_to_translate}", flush=True)
    
    glossaries = load_glossaries()
    predefined = glossaries.get(topic, {})
    
    final_glossary = {}
    missing_terms = []
    
    for term in all_items_to_translate:
        term_clean = term.strip().lower()
        found = False
        for category, cat_dict in glossaries.items():
            if term_clean in cat_dict:
                final_glossary[term] = cat_dict[term_clean]
                found = True
                break
        
        if not found:
            missing_terms.append(term)
            
    if missing_terms:
        print(f"[GLOSSARY] Prevodim {len(missing_terms)} nepoznatih termina/entiteta preko LLM...", flush=True)
        llm_translations = translate_terms_to_serbian(missing_terms)
        for eng, srb in llm_translations.items():
            if srb:
                final_glossary[eng] = srb
                
    for eng, srb in predefined.items():
        if eng not in final_glossary:
            final_glossary[eng] = srb
            
    if not final_glossary:
        return "Nema specifičnih termina za ovaj video."
        
    glossary_lines = []
    for eng, srb in final_glossary.items():
        glossary_lines.append(f'- "{eng}" -> "{srb}"')
        
    glossary_str = "\n".join(glossary_lines)
    print(f"[GLOSSARY] Formiran dinamički glosar sa {len(final_glossary)} stavki.", flush=True)
    return glossary_str

def generate_video_summary(transcript_text: str) -> str:
    """
    Poziva Modal Lektor (Qwen 32B) da generiše kratak sažetak videa na engleskom (do 100 reči)
    na osnovu celog transkripta, kako bi se pružio globalni kontekst.
    """
    if not transcript_text or not settings.MODAL_LEKTOR_URL:
        return "No context available."
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        "You are an AI assistant helping a translator. Analyze the following English transcript from a video. "
        "Write a very brief summary (maximum 100 words) of what the video is about. "
        "Focus on the main topic, context, and key goal of the video. Keep it concise.\n\n"
        f"TRANSCRIPT:\n{transcript_text}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 800
    }
    
    try:
        from backend.worker.translator import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        content = clean_thought_tags(content)
        return content
    except Exception as e:
        print(f"[SUMMARY ERROR] Greška pri generisanju sažetka: {e}", flush=True)
        return "Failed to generate video summary."

def parse_glossary_to_dict(glossary_str: str) -> dict:
    """
    Parsira tekstualni glosar (dobijen iz get_dynamic_glossary) u Python rečnik.
    """
    glossary_dict = {}
    if not glossary_str:
        return glossary_dict
    for line in glossary_str.split("\n"):
        line = line.strip()
        if not line or not line.startswith("-"):
            continue
        # Tražimo format: - "eng" -> "srb"
        match = re.search(r'-\s*"([^"]+)"\s*->\s*"([^"]+)"', line)
        if match:
            glossary_dict[match.group(1).strip()] = match.group(2).strip()
        else:
            # Fallback za slučaj da nema navodnika: - eng -> srb
            parts = line[1:].split("->")
            if len(parts) == 2:
                eng = parts[0].strip().strip('"')
                srb = parts[1].strip().strip('"')
                if eng and srb:
                    glossary_dict[eng] = srb
    return glossary_dict
