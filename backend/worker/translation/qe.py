import re

NEGATION_PATTERNS_ENG = [
    r'\bnot\b', r'\bnever\b', r'\bno\b', r'\bnobody\b', r'\bnothing\b', r'\bnowhere\b',
    r"\bdon't\b", r"\bcan't\b", r"\bwon't\b", r"\bisn't\b",
    r"\bwouldn't\b", r"\bcouldn't\b", r"\bshouldn't\b",
    r"\bdidn't\b", r"\bhasn't\b", r"\bhaven't\b"
]

def check_negation_preservation(original: str, translated: str) -> bool:
    if not original:
        return True
    
    has_original_negation = any(
        re.search(p, original, re.IGNORECASE) for p in NEGATION_PATTERNS_ENG
    )
    
    has_serbian_negation = bool(re.search(
        r'\bne\b|\bne(ću|ćeš|će|ćemo|ćete|ću)\b|\bni(sam|si|je|smo|ste|su)\b|\bne(mam|maš|ma|mamo|mate|maju)\b|\bni(ko|šta|kad|kada|gde|kako|jedan|kakav|ti|ti)\b|\bni\b',
        translated, re.IGNORECASE
    ))
    
    if has_original_negation and not has_serbian_negation:
        return False
    return True

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("[EMBEDDING] Inicijalizujem paraphrase-multilingual-MiniLM-L12-v2 model...", flush=True)
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    return _embedding_model

def semantic_similarity(english_text: str, serbian_text: str) -> float:
    if not english_text or not serbian_text:
        return 1.0
    try:
        model = get_embedding_model()
        embeddings = model.encode([english_text, serbian_text], convert_to_numpy=True)
        
        import numpy as np
        norm_a = np.linalg.norm(embeddings[0])
        norm_b = np.linalg.norm(embeddings[1])
        if norm_a == 0 or norm_b == 0:
            return 0.0
        similarity = np.dot(embeddings[0], embeddings[1]) / (norm_a * norm_b)
        return float(similarity)
    except Exception as e:
        print(f"[EMBEDDING ERROR] Greška pri računanju semantičke sličnosti: {e}", flush=True)
        return 0.8  # Fallback

def get_comet_kiwi_score(english_text: str, serbian_text: str) -> float:
    """
    Quality Estimation (QE) skor koji zamenjuje stari kosinusni gejting.
    Kombinuje semantičku sličnost (Sentence-Transformers) sa morfološkim,
    sintaksičkim i pravopisnim kaznenim poenima prilagođenim srpskim pravilima projekta.
    """
    if not english_text or not serbian_text:
        return 1.0
        
    # 1. Bazična semantička sličnost
    base_similarity = semantic_similarity(english_text, serbian_text)
    
    # 2. Pravopisni/morfološki kazneni poeni
    penalties = 0.0
    
    # a) Curenje dijalekta (ijekavica / hrvatski regionalizmi)
    LEAK_PATTERN = re.compile(
        r'\b(dio|dijel\w*|dvjesto|spriječi\w*|tijekom|sustav\w*|tjedan|tjedn\w*|'
        r'tisuć\w*|uvjet\w*|utjecaj\w*|sučelj\w*|zaslon\w*|tipkovnic\w*|poveznic\w*|'
        r'vidjeti|djeluj\w*|riješi\w*|uvijek|gdje)\b', re.IGNORECASE)
    
    leaks = LEAK_PATTERN.findall(serbian_text)
    if leaks:
        # Kazna: 0.1 po uočenoj reči
        penalties += 0.1 * len(leaks)
        
    # b) Brojevi napisani ciframa umesto rečima
    if re.search(r'\b\d+\b', serbian_text):
        if re.search(r'\b\d+\b', english_text):
            penalties += 0.08
            
    # c) Padež meseca
    if "listopada" in serbian_text.lower() or ("oktobru" in serbian_text.lower() and "u oktobru" not in serbian_text.lower()):
        penalties += 0.1
        
    # d) Strana imena napisana u originalu (npr. Claude, OpenAI, a ne Klod, Ej Aj)
    # Ignorišemo Wi-Fi, GPS, Bluetooth koji ostaju u originalu
    english_words = re.findall(r'\b[A-Za-z]+\b', serbian_text)
    allowed_entities = {"Wi-Fi", "WiFi", "GPS", "Bluetooth", "wifi", "gps", "bluetooth", "ENTITY", "CODE", "URL", "EMAIL"}
    unallowed_english = [w for w in english_words if w not in allowed_entities]
    if unallowed_english:
        penalties += 0.05 * len(unallowed_english)
        
    # e) Negacija
    if not check_negation_preservation(english_text, serbian_text):
        penalties += 0.2
        
    # f) Predugačak prevod (veliko odstupanje u dužini)
    if len(serbian_text) > len(english_text) * 1.5:
        penalties += 0.05
        
    # Izračunavanje finalnog QE skora
    qe_score = base_similarity - penalties
    return max(0.0, min(1.0, qe_score))
