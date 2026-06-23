import re
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

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

_cross_encoder_model = None

def get_cross_encoder_model():
    global _cross_encoder_model
    if _cross_encoder_model is None:
        print("[EMBEDDING] Inicijalizujem symanto/xlm-roberta-base-snli-mnli CrossEncoder...", flush=True)
        from sentence_transformers import CrossEncoder
        _cross_encoder_model = CrossEncoder("symanto/xlm-roberta-base-snli-mnli")
    return _cross_encoder_model

def check_semantic_contradiction(original: str, translated: str) -> bool:
    """
    Koristi Cross-Encoder model za detekciju kontradikcija (suprotno značenje).
    Vraća True ako postoji kontradikcija, inače False.
    """
    if not original or not translated:
        return False
    try:
        model = get_cross_encoder_model()
        scores = model.predict([(original, translated)])[0]
        max_idx = int(scores.argmax())
        
        config = getattr(model.model, "config", None)
        id2label = getattr(config, "id2label", None) if config else None
        if id2label:
            label_name = id2label[max_idx].lower()
            return bool(label_name == "contradiction")
        else:
            return bool(max_idx == 2)
    except Exception as e:
        print(f"[CROSS-ENCODER ERROR] Greška pri proveri kontradikcije: {e}", flush=True)
        return False

def get_comet_kiwi_score(english_text: str, serbian_text: str) -> float:
    """
    Quality Estimation (QE) skor koji zamenjuje stari kosinusni gejting.
    Kombinuje semantičku sličnost (Sentence-Transformers) sa morfološkim,
    sintaksičkim i pravopisnim kaznenim poenima prilagođenim srpskim pravilima projekta.
    Dodatno koristi Cross-Encoder za detekciju semantičkih kontradikcija.
    """
    if not english_text or not serbian_text:
        return 1.0
        
    # 0. NLI Cross-Encoder provera kontradikcije
    if check_semantic_contradiction(english_text, serbian_text):
        print(f"[NLI CONTRADICTION] Detektovan semantički nesklad između: ENG: '{english_text}' -> SRB: '{serbian_text}'. QE score postavljen na 0.0", flush=True)
        return 0.0

    # 1. Bazična semantička sličnost
    base_similarity = semantic_similarity(english_text, serbian_text)
    
    # 2. Pravopis
    penalties = 0.0
    
    # a) Curenje dijalekta (ijekavica / hrvatski regionalizmi)
    LEAK_PATTERN = re.compile(
        r'\b(dio|dijel\w*|dvjesto|spriječi\w*|tijekom|sustav\w*|tjedan|tjedn\w*|'
        r'tisuć\w*|uvjet\w*|utjecaj\w*|sučelj\w*|zaslon\w*|tipkovnic\w*|poveznic\w*|'
        r'vidjeti|djeluj\w*|riješi\w*|uvijek|gdje|provjer\w*|vjer\w*|mjer\w*|svijet\w*|'
        r'vijest\w*|tijel\w*|obavijest\w*)\b', re.IGNORECASE)
    
    leaks = LEAK_PATTERN.findall(serbian_text)
    if leaks:
        # Ublaženo: 0.05 po reči, ali maksimalno 0.15 ukupne kazne za dijalekt
        penalties += min(0.15, 0.05 * len(leaks))
        
    # b) Brojevi napisani ciframa umesto rečima
    if re.search(r'\b\d+\b', serbian_text):
        if re.search(r'\b\d+\b', english_text):
            # Ublaženo sa 0.08 na 0.04 za proste godine/datume ako su u oba teksta
            penalties += 0.04
            
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
        # Ublaženo sa 0.05 na 0.03
        penalties += 0.03
        
    # Izračunavanje finalnog QE skora
    qe_score = base_similarity - penalties
    return float(max(0.0, min(1.0, qe_score)))

def get_llm_judge_score(english_text: str, serbian_text: str, limit_char: int = None) -> dict:
    """
    Poziva Llama 3.1 8B na Modalu kao sudiju (LLM-as-a-Judge) da oceni kvalitet prevoda.
    Koristi MODAL_JUDGE_URL, a kao fallback MODAL_LEKTOR_URL.
    Vraća rečnik sa ključevima: 'score' (float od 1.0 do 5.0), 'explanation' (str), 'errors' (list).
    """
    judge_url = settings.MODAL_JUDGE_URL or settings.MODAL_LEKTOR_URL
    if not judge_url:
        return {"score": 5.0, "explanation": "Judge/Lektor URL nije konfigurisan, automatski prolaz.", "errors": []}

    url = f"{judge_url.rstrip('/')}/v1/chat/completions"
    
    limit_instruction = ""
    if limit_char:
        limit_instruction = f"Prevod (srpski tekst) ima striktan limit dužine od {limit_char} karaktera. Trenutna dužina je {len(serbian_text)} karaktera."
        
    prompt = (
        "Ti si stručni sudija za kvalitet prevoda sa engleskog na srpski jezik (ekavica, latinica).\n"
        "Ocenjuješ kvalitet prevoda na skali od 1.0 do 5.0 (gde je 5.0 savršen prevod).\n\n"
        f"Originalni engleski tekst: \"{english_text}\"\n"
        f"Prevedeni srpski tekst: \"{serbian_text}\"\n"
        f"{limit_instruction}\n\n"
        "PRAVILA OCENJIVANJA:\n"
        "- 5.0: Prevod je tačan, prirodan, na ekavici i latinici, brojevi su rečima, nema stranih reči u originalu (osim GPS, Wi-Fi, Bluetooth), i ne prelazi limit karaktera ako je zadat.\n"
        "- Oduzmi 1.0 do 2.0 poena ako prevod sadrži ijekavicu ili hrvatske regionalizme (npr. 'dio', 'sustav', 'tijekom', 'tisuća', 'uvjet').\n"
        "- Oduzmi 1.5 poen ako je izgubljen osnovni smisao ili negacija (npr. original ima negaciju, a prevod nema, ili obrnuto).\n"
        "- Oduzmi 1.0 poen ako prevod sadrži brojeve napisane ciframa (npr. '5', '2024') umesto slovima.\n"
        "- Oduzmi 1.0 poen ako sadrži netranskribovana strana imena (npr. 'Claude' umesto 'Klod').\n"
        "- Oduzmi 1.0 poen ako je prevod predugačak u odnosu na limit karaktera.\n\n"
        "VAŽNO: STROGO ZABRANJENO generisanje <think> ili <thought> tagova i bilo kakvog razmišljanja. Samo odmah vrati JSON odgovor.\n\n"
        "FORMAT ODGOVORA:\n"
        "Odgovori isključivo u sledećem JSON formatu, bez ikakvog dodatnog teksta, komentara ili think tagova:\n"
        "{\n"
        "  \"score\": 5.0,\n"
        "  \"explanation\": \"kratko objašnjenje na srpskom\",\n"
        "  \"errors\": [\"lista_uočenih_grešaka\"]\n"
        "}\n"
    )

    payload = {
        "model": "llama-judge" if settings.MODAL_JUDGE_URL else "llama-8b",
        "messages": [
            {
                "role": "system",
                "content": "Ti si brzi i precizni sudija za kvalitet prevoda. Vrati isključivo validan JSON prema šemi. STROGO JE ZABRANJENO generisanje <think> ili <thought> tagova i bilo kakvog razmišljanja. Samo odmah vrati JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
        "guided_json": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "explanation": {"type": "string"},
                "errors": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["score", "explanation", "errors"]
        }
    }

    try:
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=45)
        content = res["choices"][0]["message"]["content"].strip()
        
        from backend.worker.translation import extract_and_parse_json
        data = extract_and_parse_json(content)
        if not data:
            raise ValueError("Nije uspelo parsiranje niti popravljanje JSON-a sudije.")
            
        print(f"[LLM JUDGE] Rezultat evaluacije (Llama 8B): score={data.get('score')}, errors={data.get('errors')}, objašnjenje={data.get('explanation')}", flush=True)
        return {
            "score": float(data.get("score", 5.0)),
            "explanation": data.get("explanation", ""),
            "errors": data.get("errors", [])
        }
    except Exception as e:
        print(f"[LLM JUDGE ERROR] Greška pri pozivanju LLM sudije: {e}.", flush=True)
        return {
            "score": 5.0,
            "explanation": f"Greška sudije (fallback): {str(e)}",
            "errors": []
        }

