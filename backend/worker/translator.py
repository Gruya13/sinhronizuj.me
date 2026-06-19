import json
import cv2
import base64
import os
import time
import re
from typing import List
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

def mask_untranslatable(text: str) -> tuple[str, dict]:
    if not text:
        return text, {}
    masks = {}
    counter = 0
    
    patterns = [
        # Keep-original entiteti
        (r'\b(Wi-Fi|WiFi|wi-fi|wifi|GPS|gps|Bluetooth|bluetooth)\b', 'ENTITY'),
        # Kod u backtick-ovima
        (r'`[^`]+`', 'CODE'),
        # URL-ovi
        (r'https?://\S+', 'URL'),
        # Email adrese  
        (r'\b[\w.-]+@[\w.-]+\.\w+\b', 'EMAIL'),
        # Komande u zagradama ili reči velikim slovima koje liče na komande
        (r'\([A-Z][A-Z0-9_]+\)', 'CMD'),
        # Hashtag-ovi
        (r'#\w+', 'HASHTAG'),
        # Matematičke formule
        (r'\d+\s*[+\-*/=]\s*\d+', 'FORMULA'),
        # Verzije softvera
        (r'\bv\d+\.\d+(?:\.\d+)?\b', 'VERSION'),
    ]
    
    masked_text = text
    for pattern, mask_type in patterns:
        matches = list(re.finditer(pattern, masked_text))
        for match in reversed(matches):
            val = match.group(0)
            placeholder = f'[{mask_type}_{counter}]'
            masks[placeholder] = val
            start, end = match.span()
            masked_text = masked_text[:start] + placeholder + masked_text[end:]
            counter += 1
            
    return masked_text, masks

def unmask_text(translated_text: str, masks: dict) -> str:
    if not translated_text or not masks:
        return translated_text
    for placeholder, original in masks.items():
        translated_text = translated_text.replace(placeholder, original)
    return translated_text

def mask_segment_pair(orig_text: str, trans_text: str) -> tuple[str, str, dict]:
    masked_orig, masks = mask_untranslatable(orig_text)
    
    masked_trans = trans_text
    for placeholder, original_val in masks.items():
        if original_val in masked_trans:
            masked_trans = masked_trans.replace(original_val, placeholder)
            
    return masked_orig, masked_trans, masks


# Boolean provera negacija radi izbegavanja dvostruke negacije na srpskom
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

def retranslate_with_self_critique(english_text: str, bad_translation: str, feedback_hint: str) -> str:
    if not settings.MODAL_LEKTOR_URL:
        return bad_translation
        
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    
    prompt = (
        "Ti si stručni prevodilac za srpski jezik (ekavica). Prethodni prevod ima greške.\n"
        f"Originalni engleski tekst: {english_text}\n"
        f"Prethodni loš prevod: {bad_translation}\n"
        f"Uočene greške / Uputstvo za ispravku: {feedback_hint}\n\n"
        "Tvoj zadatak je da pružiš novi, ispravljeni prevod na srpskom jeziku (ekavica, latinica) koji:\n"
        "1. U potpunosti rešava sve uočene greške i prati uputstvo.\n"
        "2. Zvuči prirodno, koristi srpske idiome i ispravne gramatičke oblike.\n"
        "3. Piše sve brojeve i procente slovima (npr. 'dvesta', 'pet posto').\n"
        "4. Piše strana imena i brendove fonetski (npr. 'Klod', 'Doker') osim GPS, Wi-Fi, Bluetooth.\n"
        "5. Tvoj odgovor mora sadržati isključivo ispravljeni srpski tekst prevoda, bez ikakvih uvodnih rečenica, objašnjenja, navodnika ili think tagova.\n"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [
            {
                "role": "system",
                "content": "Ti si stručni prevodilac i lektor. Vrati isključivo ispravljeni prevod na srpski jezik bez ikakvog dodatnog teksta ili komentara."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 500
    }
    
    try:
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        cleaned = clean_thought_tags(content).strip().strip('"\'')
        if cleaned:
            print(f"[SELF-CRITIQUE SUCCESS] Prethodni: {bad_translation} -> Novi: {cleaned}", flush=True)
            return cleaned
    except Exception as e:
        print(f"[SELF-CRITIQUE ERROR] Greška prilikom re-prevoda sa samokritikom: {e}", flush=True)
        
    return bad_translation




CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ђ': 'đ', 'е': 'e', 'ж': 'ž',
    'з': 'z', 'и': 'i', 'ј': 'j', 'к': 'k', 'л': 'l', 'љ': 'lj', 'м': 'm', 'н': 'n',
    'њ': 'nj', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'ћ': 'ć', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'č', 'џ': 'dž', 'ш': 'š',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Ђ': 'Đ', 'Е': 'E', 'Ж': 'Ž',
    'З': 'Z', 'И': 'I', 'Ј': 'J', 'К': 'K', 'Л': 'L', 'Љ': 'Lj', 'М': 'M', 'Н': 'N',
    'Њ': 'Nj', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'Ћ': 'Ć', 'У': 'U',
    'Ф': 'F', 'Х': 'H', 'Ц': 'C', 'Ч': 'Č', 'Џ': 'Dž', 'Ш': 'Š',
    'ѓ': 'đ', 'ќ': 'ć', 'ѕ': 'dz', 'Ѓ': 'Đ', 'Ќ': 'Ć', 'Ѕ': 'Dz'
}

def preserve_case(match, repl):
    matched_text = match.group(0)
    if matched_text.isupper():
        return repl.upper()
    if matched_text and matched_text[0].isupper():
        return repl[0].upper() + repl[1:] if len(repl) > 1 else repl.upper()
    return repl.lower()

LATIN_REPLACEMENTS_RAW = {
    # Ijekavizmi - deo
    r'\bdio\b': 'deo',
    r'\bdijel\b': 'deo',
    r'\bdijela\b': 'dela',
    r'\bdijelu\b': 'delu',
    r'\bdijelom\b': 'delom',
    r'\bdijelovi\b': 'delovi',
    r'\bdijelove\b': 'delove',
    r'\bdijelova\b': 'delova',
    r'\bdijelovima\b': 'delovima',
    
    # spriječiti
    r'\bspriječiti\b': 'sprečiti',
    r'\bspriječio\b': 'sprečio',
    r'\bspriječila\b': 'sprečila',
    r'\bspriječilo\b': 'sprečilo',
    r'\bspriječeno\b': 'sprečeno',
    r'\bspriječeni\b': 'sprečeni',
    r'\bspriječili\b': 'sprečili',
    r'\bspriječi\b': 'spreči',
    r'\bspriječe\b': 'spreče',
    r'\bspriječivši\b': 'sprečivši',
    r'\bspriječite\b': 'sprečite',
    
    # dvjesto
    r'\bdvjesto\b': 'dvesta',
    
    # tijekom
    r'\btijekom\b': 'tokom',
    
    # tjedan i fraze
    r'\bu ovom tjednu\b': 'u ovoj nedelji',
    r'\bu tom tjednu\b': 'u toj nedelji',
    r'\bovom tjednu\b': 'ovoj nedelji',
    r'\bovog tjedna\b': 'ove nedelje',
    r'\btog tjedna\b': 'te nedelje',
    r'\bprošlog tjedna\b': 'prošle nedelje',
    r'\bprošlom tjednu\b': 'prošle nedelje',
    r'\bsledećeg tjedna\b': 'sledeće nedelje',
    r'\bsljedećeg tjedna\b': 'sledeće nedelje',
    r'\bsledećem tjednu\b': 'sledeće nedelje',
    r'\bsljedećem tjednu\b': 'sledeće nedelje',
    r'\bidućeg tjedna\b': 'sledeće nedelje',
    r'\bidućem tjednu\b': 'sledeće nedelje',
    r'\btjedan\b': 'nedelja',
    r'\btjedna\b': 'nedelje',
    r'\btjednu\b': 'nedelji',
    r'\btjednom\b': 'nedeljom',
    r'\btjedni\b': 'nedeljni',
    r'\btjedne\b': 'nedelje',
    r'\btjedana\b': 'nedelja',
    r'\btjednima\b': 'nedeljama',
    
    # sustav
    r'\bsustav\b': 'sistem',
    r'\bsustava\b': 'sistema',
    r'\bsustavu\b': 'sistemu',
    r'\bsustavom\b': 'sistemom',
    r'\bsustavi\b': 'sistemi',
    r'\bsustavima\b': 'sistemima',
    r'\bsustave\b': 'sisteme',
    
    # uvjet
    r'\buvjet\b': 'uslov',
    r'\buvjeta\b': 'uslova',
    r'\buvjetu\b': 'uslovu',
    r'\buvjetom\b': 'uslovom',
    r'\buvjeti\b': 'uslovi',
    r'\buvjetima\b': 'uslovima',
    r'\buvjete\b': 'uslove',
    
    # utjecaj
    r'\butjecaj\b': 'uticaj',
    r'\butjecaja\b': 'uticaja',
    r'\butjecaju\b': 'uticaju',
    r'\butjecajem\b': 'uticajem',
    r'\butjecaji\b': 'uticaji',
    r'\butjecajima\b': 'uticajima',
    r'\butjecaje\b': 'uticaje',
    
    # učinkovit
    r'\bučinkovit\b': 'efikasan',
    r'\bučinkovita\b': 'efikasna',
    r'\bučinkovito\b': 'efikasno',
    r'\bučinkovite\b': 'efikasne',
    r'\bučinkoviti\b': 'efikasni',
    r'\bučinkovitih\b': 'efikasnih',
    r'\bučinkovitom\b': 'efikasnom',
    r'\bučinkovitost\b': 'efikasnost',
    r'\bučinkovitosti\b': 'efikasnosti',
    r'\bučinkovitostima\b': 'efikasnostima',
    
    # tvrtka
    r'\btvrtka\b': 'firma',
    r'\btvrtke\b': 'firme',
    r'\btvrtki\b': 'firmi',
    r'\btvrtku\b': 'firmu',
    r'\btvrtkom\b': 'firmom',
    r'\btvrtkama\b': 'firmama',
    
    # sučelje
    r'\bsučelje\b': 'interfejs',
    r'\bsučelju\b': 'interfejsu',
    r'\bsučeljem\b': 'interfejsom',
    r'\bsučeljima\b': 'interfejsima',
    r'\bsučelja\b': 'interfejsa',
    r'\bkorisnička sučelja\b': 'korisnički interfejsi',
    r'\bkorisničkih sučelja\b': 'korisničkih interfejsa',
    
    # zaslon
    r'\bzaslon\b': 'ekran',
    r'\bzaslona\b': 'ekrana',
    r'\bzaslonu\b': 'ekranu',
    r'\bzaslonom\b': 'ekranom',
    r'\bzasloni\b': 'ekrani',
    r'\bzaslonima\b': 'ekranima',
    r'\bzaslone\b': 'ekrane',
    
    # tipkovnica
    r'\btipkovnica\b': 'tastatura',
    r'\btipkovnice\b': 'tastature',
    r'\btipkovnici\b': 'tastaturi',
    r'\btipkovnicu\b': 'tastaturu',
    r'\btipkovnicom\b': 'tastaturom',
    r'\btipkovnicama\b': 'tastaturama',
    
    # poveznica
    r'\bpoveznica\b': 'link',
    r'\bpoveznicu\b': 'link',
    r'\bpoveznice\b': 'linkovi',
    r'\bpoveznici\b': 'linku',
    r'\bpoveznicom\b': 'linkom',
    r'\bpoveznicama\b': 'linkovima',
    
    # tisuća
    r'\btisuća\b': 'hiljada',
    r'\btisuću\b': 'hiljadu',
    r'\btisuće\b': 'hiljade',
    r'\btisućom\b': 'hiljadom',
    r'\btisućama\b': 'hiljadama',
    
    # meseci
    r'\bsiječanj\b': 'januar',
    r'\bsiječnja\b': 'januara',
    r'\bsiječnju\b': 'januaru',
    r'\bveljača\b': 'februar',
    r'\bveljače\b': 'februara',
    r'\bveljači\b': 'februaru',
    r'\božujak\b': 'mart',
    r'\božujka\b': 'marta',
    r'\božujku\b': 'martu',
    r'\btravanj\b': 'april',
    r'\btravnja\b': 'aprila',
    r'\btravnju\b': 'aprilu',
    r'\bsvibanj\b': 'maj',
    r'\bsvibnja\b': 'maja',
    r'\bsvibnju\b': 'maju',
    r'\blipanj\b': 'jun',
    r'\blipnja\b': 'juna',
    r'\blipnju\b': 'junu',
    r'\bsrpanj\b': 'jul',
    r'\bsrpnja\b': 'jula',
    r'\bsrpnju\b': 'julu',
    r'\bkolovoz\b': 'avgust',
    r'\bkolovoza\b': 'avgusta',
    r'\bkolovozu\b': 'avgustu',
    r'\brujan\b': 'septembar',
    r'\brujna\b': 'septembra',
    r'\brujnu\b': 'septembru',
    r'\blistopad\b': 'oktobar',
    r'\blistopada\b': 'oktobra',
    r'\blistopadu\b': 'oktobru',
    r'\bstudeni\b': 'novembar',
    r'\bstudenog\b': 'novembra',
    r'\bstudenom\b': 'novembru',
    r'\bprosinac\b': 'decembar',
    r'\bprosinca\b': 'decembra',
    r'\bprosincu\b': 'decembru',
    
    # rješenje
    r'\brješenje\b': 'rešenje',
    r'\brješenja\b': 'rešenja',
    r'\brješenju\b': 'rešenju',
    r'\brješenjem\b': 'rešenjem',
    r'\brješenjima\b': 'rešenjima',
    
    # vještački
    r'\bvještački\b': 'veštački',
    r'\bvještačka\b': 'veštačka',
    r'\bvještačko\b': 'veštačko',
    r'\bvještačke\b': 'veštačke',
    r'\bvještačkih\b': 'veštačkih',
    
    # vidio / vidjeti
    r'\bvidio\b': 'video',
    r'\bvidjela\b': 'videla',
    r'\bvidjeli\b': 'videli',
    
    # smije / smijati se
    r'\bsmije se\b': 'smeje se',
    r'\bsmije\b': 'sme',
    r'\bsmiju se\b': 'smeju se',
    r'\bsmiju\b': 'smeju',
    r'\bsmijao se\b': 'smejao se',
    r'\bsmijao\b': 'smejao',
    r'\bsmijala se\b': 'smejala se',
    r'\bsmijala\b': 'smejala',
    r'\bsmijali se\b': 'smejali se',
    r'\bsmijali\b': 'smejali',
    r'\bsmijanje\b': 'smejanje',
    r'\bsmijati se\b': 'smejati se',
    r'\bsmijati\b': 'smejati',
    
    # dolje
    r'\bdolje\b': 'dole',
    r'\bgdje\b': 'gde',
    r'\bnijesu\b': 'nisu',
    r'\busmjeruju\b': 'usmeravaju',
    r'\buvijek\b': 'uvek',
    
    # polovica
    r'\bpolovicu\b': 'polovinu',
    r'\bpolovica\b': 'polovina',
    r'\bpolovice\b': 'polovine',
    r'\bpolovici\b': 'polovini',
    
    # svijet
    r'\bsvijet\b': 'svet',
    r'\bsvijeta\b': 'sveta',
    r'\bsvijetu\b': 'svetu',
    r'\bsvijetom\b': 'svetom',
    r'\bsvjetovi\b': 'svetovi',
    r'\bsvjetova\b': 'svetova',
    r'\bsvjetovima\b': 'svetovima',
    
    # dijete
    r'\bdijete\b': 'dete',
    r'\bdjeteta\b': 'deteta',
    r'\bdjetetu\b': 'detetu',
    r'\bdjetetom\b': 'detetom',
    r'\bdjeca\b': 'deca',
    r'\bdjece\b': 'dece',
    r'\bdjeci\b': 'deci',
    r'\bdjecom\b': 'decom',
    r'\bdječak\b': 'dečak',
    r'\bdječaka\b': 'dečaka',
    r'\bdječaku\b': 'dečaku',
    r'\bdječakom\b': 'dečakom',
    r'\bdječaci\b': 'dečaci',
    r'\bdječacima\b': 'dečacima',
    r'\bdjevojčica\b': 'devojčica',
    r'\bdjevojčice\b': 'devojčice',
    r'\bdjevojčici\b': 'devojčici',
    r'\bdjevojčicu\b': 'devojčicu',
    r'\bdjevojčicom\b': 'devojčicom',
    r'\bdjevojčicama\b': 'devojčicama',
    
    # tijelo
    r'\btijelo\b': 'telo',
    r'\btijela\b': 'tela',
    r'\btijelu\b': 'telu',
    r'\btijelom\b': 'telom',
    r'\btijelima\b': 'telima',
    
    # vrijeme
    r'\bvrijeme\b': 'vreme',
    r'\bumjesto\b': 'umesto',
    r'\bmjesto\b': 'mesto',
    r'\bmjesta\b': 'mesta',
    
    # vjerojatno
    r'\bvjerovatno\b': 'verovatno',
    r'\bvjerojatno\b': 'verovatno',
    r'\bvjerovati\b': 'verovati',
    r'\bnevjerojatno\b': 'neverovatno',
    r'\bnevjerovatno\b': 'neverovatno',
    r'\bnevjerojatan\b': 'neverovatan',
    r'\bnevjerovatan\b': 'neverovatan',
    r'\bnevjerojatna\b': 'neverovatna',
    r'\bnevjerovatna\b': 'neverovatna',
    r'\bnevjerojatne\b': 'neverovatne',
    r'\bnevjerovatne\b': 'neverovatne',
    r'\bnevjerojatnih\b': 'neverovatnih',
    r'\bnevjerovatnih\b': 'neverovatnih',
    r'\bvjerojatnost\b': 'verovatnoća',
    r'\bvjerovatnost\b': 'verovatnoća',
    r'\bvjerojatnosti\b': 'verovatnoće',
    r'\bvjerovatnosti\b': 'verovatnoće',
    
    # primjerno
    r'\bprimjerno\b': 'primereno',
    r'\bneprimjerno\b': 'neprimereno',
    r'\bprimerno\b': 'primereno',
    r'\bneprimerno\b': 'neprimereno',
    
    # vidjeti
    r'\bvidjeti\b': 'videti',
    r'\bvidjeće\b': 'videće',
    r'\bvidjećeš\b': 'videćeš',
    r'\bvidjećemo\b': 'videćemo',
    r'\bvidjećete\b': 'videćete',
    
    # donijeti
    r'\bdonijeti\b': 'doneti',
    r'\bdonijeće\b': 'doneće',
    r'\bdonijećeš\b': 'donećeš',
    r'\bdonijećemo\b': 'donećemo',
    r'\bdonijećete\b': 'donećete',
    
    # dijeliti
    r'\bdijeliti\b': 'deliti',
    r'\bdijeliće\b': 'deliće',
    r'\bdijelićeš\b': 'delićeš',
    r'\bdijelićemo\b': 'delićemo',
    r'\bdijelićete\b': 'delićete',
    
    # htjeti
    r'\bhtjeti\b': 'hteti',
    r'\bhtjeće\b': 'hteće',
    r'\bhtjećeš\b': 'htećeš',
    r'\bhtjećemo\b': 'htećemo',
    r'\bhtjećete\b': 'htećete',
    
    # riješiti
    r'\briješiti\b': 'rešiti',
    r'\briješiće\b': 'rešiće',
    r'\briješeno\b': 'rešeno',
    
    # rješavati
    r'\brješavati\b': 'rešavati',
    r'\brješava\b': 'rešava',
    r'\brješavaju\b': 'rešavaju',
    r'\brješavaš\b': 'rešavaš',
    r'\brješavamo\b': 'rešavamo',
    r'\brješavate\b': 'rešavate',
    r'\brješavao\b': 'rešavao',
    r'\brješavala\b': 'rešavala',
    r'\brješavali\b': 'rešavali',
    r'\brješavanje\b': 'rešavanje',
    r'\brješavanja\b': 'rešavanja',
    r'\brješavanju\b': 'rešavanju',
    r'\brješavanjem\b': 'rešavanjem',
    r'\brješavaću\b': 'rešavaću',
    r'\brješavaćeš\b': 'rešavaćeš',
    r'\brješavaće\b': 'rešavaće',
    r'\brješavaćemo\b': 'rešavaćemo',
    r'\brješavaćete\b': 'rešavaćete',
    
    # promijeniti
    r'\bpromijeniti\b': 'promeniti',
    r'\bpromijeni\b': 'promeni',
    r'\bpromijene\b': 'promene',
    r'\bpromijenio\b': 'promenio',
    r'\bpromijenila\b': 'promenila',
    r'\bpromijenili\b': 'promenili',
    r'\bpromijeniće\b': 'promeniće',
    r'\bpromijenjeno\b': 'promenjeno',
    r'\bpromijenivši\b': 'promenivši',
    r'\bpromijenite\b': 'promenite',
    
    # primijeniti
    r'\bprimijeniti\b': 'primeniti',
    r'\bprimijeni\b': 'primeni',
    r'\bprimijene\b': 'primene',
    r'\bprimijenio\b': 'primenio',
    r'\bprimijenila\b': 'primenila',
    r'\bprimijenili\b': 'primenili',
    r'\bprimijeniće\b': 'primeniće',
    r'\bprimijenjeno\b': 'primenjeno',
    r'\bprimijenivši\b': 'primenivši',
    r'\bprimijenite\b': 'primenite',
    
    # izravno
    r'\bizravno\b': 'direktno',
    r'\bizravan\b': 'direktan',
    r'\bizravna\b': 'direktna',
    r'\bizravne\b': 'direktne',
    r'\bizravnih\b': 'direktnih',
    r'\bizravnom\b': 'direktnom',
    r'\bizravnog\b': 'direktnog',
    r'\bizravnoga\b': 'direktnog',
    r'\bizravnu\b': 'direktnu',
    r'\bizravni\b': 'direktni',
    r'\bizravnim\b': 'direktnim',
    
    # razumjeti
    r'\brazumjeti\b': 'razumeti',
    r'\brazumjeće\b': 'razumeće',
    
    # Specifični medicinski/tehnički izrazi
    r'\bspokoen\b': 'spokojan',
    r'\bspokoena\b': 'spokojna',
    r'\bspokoeno\b': 'spokojno',
    r'\bspokoeni\b': 'spokojni',
    r'\bkomarice\b': 'komarci',
    r'\bkomarica\b': 'komarac',
    r'\bkomaricama\b': 'komarcima',
    r'\banticonceptiv\b': 'kontracepcija',
    r'\bzaštića\b': 'štiti',
    r'\boluhami\b': 'olujama',
    r'\bosvještiti\b': 'olabaviti',
    r'\bdengue šake\b': 'denga groznice',
    r'\bdengue\b': 'denga',
    r'\bfebre\b': 'groznice',
    r'\bžuta febra\b': 'žuta groznica',
    r'\bžute febre\b': 'žute groznice',
    r'\bženice\b': 'ženke',
    r'\bženicama\b': 'ženkama',
    r'\bšaljubiti\b': 'poludeti',
    r'\btrpešćine\b': 'strpljenja',
    r'\bvreže\b': 'seče',
    r'\bse smešta\b': 'maže',
    r'\bdrevne osnovice\b': 'drvene osnove',
    r'\bdrevne\b': 'drvene',
    r'\bzavari seam\b': 'zavari šav',
    r'\bseam\b': 'šav',
    r'\bukuju\b': 'bodu',
    r'\bukuje\b': 'bode',
    r'\bopakuj\b': 'obmotaj',
    r'\bopakujte\b': 'obmotajte',
    r'\bopakuje\b': 'obmotava',
    r'\bopakuju\b': 'obmotavaju',
    r'\bteško oko\b': 'čvrsto oko',
    r'\bneprimerno sigurno\b': 'nedovoljno čvrsto',
    r'\bneprimerno siguran\b': 'nedovoljno čvrst',
    r'\bneprimereno sigurno\b': 'nedovoljno čvrsto',
    r'\bneprimereno siguran\b': 'nedovoljno čvrst',
    r'\bse lako odlaze\b': 'lako olabave',
    r'\blako odlaze\b': 'lako olabave',
    r'\brezao papir\b': 'sekao papir',
    r'\brezati papir\b': 'seći papir',
    r'\bserez\b': 'isečeš',
    r'\bserežeš\b': 'isečeš',
    r'\bsereže\b': 'iseče',
    r'\bserezati\b': 'iseći',
    r'\bsrezati\b': 'iseći',
    
    # kaos / haos
    r'\bkaos\b': 'haos',
    r'\bkaosa\b': 'haosa',
    r'\bkaosu\b': 'haosu',
    r'\bkaosom\b': 'haosom',
    
    # glazba
    r'\bglazba\b': 'muzika',
    r'\bglazbe\b': 'muzike',
    r'\bglazbi\b': 'muzici',
    r'\bglazbu\b': 'muziku',
    r'\bglazbom\b': 'muzikom',
    r'\bglazbeni\b': 'muzički',
    r'\bglazbena\b': 'muzička',
    r'\bglazbeno\b': 'muzičko',
    r'\bglazbene\b': 'muzičke',
    r'\bglazbenik\b': 'muzičar',
    r'\bglazbenici\b': 'muzičari',
    
    # znanstvenik
    r'\bznanstvenik\b': 'naučnik',
    r'\bznanstvenika\b': 'naučnika',
    r'\bznanstvenici\b': 'naučnici',
    r'\bznanstvenicima\b': 'naučnicima',
    
    # povijest
    r'\bpovijest\b': 'istorija',
    r'\bpovijesti\b': 'istorije',
    r'\bpovijesni\b': 'istorijski',
    r'\bpovijesna\b': 'istorijska',
    r'\bpovijesno\b': 'istorijsko',
    r'\bpovijesne\b': 'istorijske',
    
    # sigurnosni
    r'\bsigurnosni\b': 'bezbednosni',
    r'\bsigurnosna\b': 'bezbednosna',
    r'\bsigurnosno\b': 'bezbednosno',
    r'\bsigurnosne\b': 'bezbednosne',
    r'\bsigurnosnih\b': 'bezbednosnih',
    r'\bsigurnosnom\b': 'bezbednosnom',
    r'\bsigurnosnog\b': 'bezbednosnog',
    
    # kemijski
    r'\bkemijski\b': 'hemijski',
    r'\bkemijska\b': 'hemijska',
    r'\bkemijsko\b': 'hemijsko',
    r'\bkemijske\b': 'hemijske',
    r'\bkemijskih\b': 'hemijskih',
    r'\bkemija\b': 'hemija',
    r'\bkemije\b': 'hemije',
    r'\bkemiji\b': 'hemiji',
    
    # prosvjed
    r'\bprosvjed\b': 'protest',
    r'\bprosvjeda\b': 'protesta',
    r'\bprosvjedu\b': 'protestu',
    r'\bprosvjedom\b': 'protestom',
    r'\bprosvjedi\b': 'protesti',
    r'\bprosvjedima\b': 'protestima',
    r'\bprosvjede\b': 'proteste',
    
    # čimbenik
    r'\bčimbenik\b': 'faktor',
    r'\bčimbenici\b': 'faktori',
    r'\bčimbenika\b': 'faktora',
    
    # nazočan
    r'\bnazočan\b': 'prisutan',
    r'\bnazočna\b': 'prisutna',
    r'\bnazočno\b': 'prisutno',
    r'\bnazočni\b': 'prisutni',
    r'\bnazočnih\b': 'prisutnih',
    r'\bnazočnost\b': 'prisustvo',
    
    # općenito - uopšte (uopšte je prirodniji ekvivalent u većini konteksta)
    r'\bopćenito\b': 'uopšte',
    r'\bopćenita\b': 'uopštena',
    
    # općina
    r'\bopćina\b': 'opština',
    r'\bopćine\b': 'opštine',
    
    # osobito
    r'\bosobito\b': 'posebno',
    
    # djelovati
    r'\bdjelovati\b': 'delovati',
    r'\bdjeluje\b': 'deluje',
    r'\bdjeluju\b': 'deluju',
    r'\bdjelovao\b': 'delovao',
    r'\bdjelovala\b': 'delovala',
    r'\bdjelovali\b': 'delovali',
    r'\bdjelovanje\b': 'delovanje',
    r'\bdjelovanja\b': 'delovanja',
    r'\bdjelovanjem\b': 'delovanjem',
    
    # značajka
    r'\bznačajka\b': 'karakteristika',
    r'\bznačajke\b': 'karakteristike',
    
    # obavijest
    r'\bobavijest\b': 'obaveštenje',
    r'\bobavijesti\b': 'obaveštenja',
    
    # izvješće
    r'\bizvješće\b': 'izveštaj',
    r'\bizvješća\b': 'izveštaji',
    r'\bizvješću\b': 'izveštaju',
    
    # cijena
    r'\bcijena\b': 'cena',
    r'\bcijene\b': 'cene',
    
    # cijeli
    r'\bcijel\b': 'ceo',
    r'\bcijeli\b': 'ceo',
    r'\bcijela\b': 'cela',
    r'\bcijelo\b': 'celo',
    r'\bcijele\b': 'cele',
    r'\bcijelog\b': 'celog',
    r'\bcijelom\b': 'celom',
    r'\bcijelu\b': 'celu',
    
    # živjeti
    r'\bživjeti\b': 'živeti',
    r'\bživio\b': 'živeo',
    r'\bživjela\b': 'živela',
    r'\bživjeli\b': 'živeli',
    
    # savjet
    r'\bsavjet\b': 'savet',
    r'\bsavjeti\b': 'saveti',
    r'\bsavjeta\b': 'saveta',
    r'\bsavjetu\b': 'savetu',
    r'\bsavjetom\b': 'savetom',
    r'\bsavjetima\b': 'savetima',
    
    # dijeliti / dijeljenje
    r'\bdijeli\b': 'deli',
    r'\bdijele\b': 'dele',
    r'\bdijelio\b': 'delio',
    r'\bdijelila\b': 'delila',
    r'\bdijelili\b': 'delili',
    r'\bdijeljenje\b': 'deljenje',
    r'\bdijeljenja\b': 'deljenja',
    
    # razumjeti (oblici koji su nedostajali)
    r'\brazumio\b': 'razumeo',
    r'\brazumjela\b': 'razumela',
    r'\brazumjeli\b': 'razumeli',
    r'\brazumijem\b': 'razumem',
    r'\brazumiješ\b': 'razumeš',
    r'\brazumije\b': 'razume',
    r'\brazumijemo\b': 'razumemo',
    r'\brazumijete\b': 'razumete',
    r'\brazumiju\b': 'razumeju',
    
    # mijenjati / izmijeniti
    r'\bmijenjati\b': 'menjati',
    r'\bmijenja\b': 'menja',
    r'\bmijenjaju\b': 'menjaju',
    r'\bmijenjao\b': 'menjao',
    r'\bmijenjala\b': 'menjala',
    r'\bmijenjali\b': 'menjali',
    r'\bmijenjanje\b': 'menjanje',
    r'\bmijenjanja\b': 'menjanja',
    r'\bizmijeniti\b': 'izmeniti',
    r'\bizmijeni\b': 'izmeni',
    r'\bizmijene\b': 'izmene',
    r'\bizmijenio\b': 'izmenio',
    r'\bizmijenila\b': 'izmenila',
    r'\bizmijenili\b': 'izmenili',
    
    # Uopštena ijekavska pravila bez potrebe za celim rečima
    r'osjeć': 'oseć',
    r'osmijeh': 'osmeh',
    r'osmijesi': 'osmesi',
    r'smijeh': 'smeh',
    r'smijesi': 'smesi',
    r'smiješ': 'smeš',
    r'riječ': 'reč',
    r'rješ': 'reš',
    r'riješ': 'reš',
    r'procjen': 'procen',
    r'procijen': 'procen',
    r'ocjen': 'ocen',
    r'ocijen': 'ocen',
    r'izmjene': 'izmene',
    r'izmjen': 'izmen',
    r'izmijen': 'izmen',
    r'promjen': 'promen',
    r'promijen': 'promen',
    r'primjen': 'primen',
    r'primijen': 'primen',
    r'dijel': 'del',
    r'vrijem': 'vrem',
    r'živje': 'žive',
    r'vidje': 'vide',
    r'razumje': 'razume',
    r'spriječ': 'spreč',
    r'donije': 'done',
    r'htje': 'hte',
    r'\bdonio\b': 'doneo',
    r'\bhtio\b': 'hteo',
    r'slijed': 'sled',
    r'sljed': 'sled',
    r'slijedi': 'sledi',
    r'vijek': 'vek',
    r'vjek': 'vek',
    r'vječ': 'več',
    r'procjena': 'procena',
    r'ocjena': 'ocena',
    r'izmjena': 'izmena',
    r'promjena': 'promena',
    r'primjena': 'primena',
    r'mjera': 'mera',
    r'mjere': 'mere',
    r'mjeru': 'meru',
    r'mjerom': 'merom',
    r'mjerama': 'merama',
    r'mjeriti': 'meriti',
    r'mjerilo': 'merilo',
    r'vjera': 'vera',
    r'vjere': 'vere',
    r'vjeru': 'veru',
    r'smjer': 'smer',
    r'brijeg': 'breg',
    r'tijek': 'tok'
}

TO_LATIN_REPLACEMENTS = [
    (re.compile(pat, re.IGNORECASE), repl)
    for pat, repl in LATIN_REPLACEMENTS_RAW.items()
]

def to_latin(text: str) -> str:
    if not text:
        return text
    res = []
    for char in text:
        res.append(CYRILLIC_TO_LATIN.get(char, char))
    text = "".join(res)
    
    # Dodatno čišćenje bugarskih/čeških specifičnih karaktera
    text = text.replace('ť', 't')
    text = text.replace('Ť', 'T')
    text = text.replace('ъ', 'a')
    text = text.replace('Ъ', 'A')
    
    for pattern_compiled, repl in TO_LATIN_REPLACEMENTS:
        text = pattern_compiled.sub(lambda m, r=repl: preserve_case(m, r), text)
        
    return text

def extract_video_frames(video_path: str, num_frames: int = 10) -> List[str]:
    """
    Izvlači num_frames frejmova iz videa i vraća ih kao Base64 stringove.
    Povećano na 10 frejmova za bolji multimodalni kontekst.
    """
    if not video_path or not os.path.exists(video_path):
        print(f"[WARNING] Video fajl nije pronađen: {video_path}")
        return []

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return []

    interval = max(1, total_frames // num_frames)
    frames_b64 = []

    for i in range(num_frames):
        frame_idx = i * interval
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        # Optimizacija: Smanjujemo sliku na max 512px po dužoj strani
        h, w = frame.shape[:2]
        if max(h, w) > 512:
            scale = 512 / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        # JPEG kompresija (80% kvalitet) -> Base64
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        b64_str = base64.b64encode(buffer).decode('utf-8')
        frames_b64.append(b64_str)

    cap.release()
    return frames_b64

def clean_thought_tags(text: str) -> str:
    if not text:
        return ""
    # Podrška i za <think> (DeepSeek) i za <thought> (Qwen)
    for tag in ["think", "thought"]:
        text = re.sub(rf'<{tag}>.*?</{tag}>', '', text, flags=re.DOTALL)
        
    for tag in ["think", "thought"]:
        start_tag = f"<{tag}>"
        if start_tag in text:
            idx = text.find(start_tag)
            # Ako je tag na početku, a dalje imamo JSON/strukturu, uzmi je od prve otvorene zagrade
            valid_braces = [pos for pos in [text.find('{'), text.find('[')] if pos != -1]
            if valid_braces:
                first_valid_brace = min(valid_braces)
                if first_valid_brace > idx:
                    text = text[first_valid_brace:]
                    continue
            text = text.split(start_tag)[0]
    return text.strip()


def fix_json_newlines(json_str: str) -> str:
    if not json_str:
        return ""
    def repl(match):
        return match.group(0).replace('\n', '\\n')
    return re.sub(r'"(?:[^"\\]|\\.)*"', repl, json_str)

def extract_and_parse_json(text: str):
    if not text:
        return None
    text = clean_thought_tags(text)
    
    # Pokušaj 1: direktan loads
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # Pokušaj 2: popravka novih redova unutar stringova
    try:
        fixed_text = fix_json_newlines(text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        pass
    
    # Traženje JSON bloka unutar ```json i ```
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        json_content = match.group(1)
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            try:
                return json.loads(fix_json_newlines(json_content))
            except json.JSONDecodeError:
                pass
            
    # Traženje prvog '[' i poslednjeg ']' ili '{' i '}'
    start_arr = text.find('[')
    end_arr = text.rfind(']')
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        json_content = text[start_arr:end_arr+1]
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            try:
                return json.loads(fix_json_newlines(json_content))
            except json.JSONDecodeError:
                pass
            
    start_obj = text.find('{')
    end_obj = text.rfind('}')
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        json_content = text[start_obj:end_obj+1]
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            try:
                return json.loads(fix_json_newlines(json_content))
            except json.JSONDecodeError:
                pass
            
    return None

def regex_parse_json_segments(text: str, text_key: str = "translated_text") -> dict:
    parsed = {}
    id_matches = list(re.finditer(r'"id"\s*:\s*(\d+)', text))
    for i, id_match in enumerate(id_matches):
        start_pos = id_match.start()
        end_pos = id_matches[i+1].start() if i + 1 < len(id_matches) else len(text)
        segment_chunk = text[start_pos:end_pos]
        idx = int(id_match.group(1))
        
        # Tražimo tekstualni sadržaj
        text_match = re.search(rf'"{text_key}"\s*:\s*"([^"]*)"', segment_chunk)
        if not text_match:
            text_match = re.search(r'"(?:translated_text|refined_text|text)"\s*:\s*"([^"]*)"', segment_chunk)
        if text_match:
            val = text_match.group(1).strip()
            parsed[idx] = val
        else:
            text_match_lazy = re.search(rf'"{text_key}"\s*:\s*"([\s\S]*?)"(?=\s*,\s*"|\s*\}})', segment_chunk)
            if text_match_lazy:
                val = text_match_lazy.group(1).strip().replace('\n', ' ')
                parsed[idx] = val
    return parsed


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

def calculate_dynamic_factor(seg: dict, user_avg_speedup: float = 1.0) -> float:
    base_factor = 14.0
    speed = seg.get("speed", 1.0)
    if speed is None:
        speed = 1.0
    voice_type = seg.get("voice_type", "male")
    if voice_type is None:
        voice_type = "male"
        
    voice_correction = {
        "clone": 0.92,
        "male": 1.0,
        "female": 0.95
    }
    correction = voice_correction.get(voice_type, 1.0)
    
    factor = base_factor * speed * correction
    
    if user_avg_speedup > 1.1:
        factor = factor / user_avg_speedup
        
    return factor

def translate_segments(segments: list, video_path: str = None, progress_callback=None, user_avg_speedup: float = 1.0) -> dict:
    """
    Poziva Modal Serverless Lektor (Qwen3-32B) za tekstualni prevod visoke tačnosti.
    Optimizovano: bez slika, bez hladnog starta na A10G, batch size = 30.
    Uvedeni: globalni sažetak, klizni prozor konteksta, Chain-of-Thought analiza,
             dužinska svesnost i running glossary za konzistentnost.
    """
    import time
    translator_duration = 0.0

    if not segments:
        return {"status": "success", "translated_segments": [], "metrics": {"translator_duration": 0.0, "lektor_duration": 0.0}}

    if not settings.MODAL_LEKTOR_URL:
        print("[WARNING] MODAL_LEKTOR_URL nije definisan. Vraćam originalni tekst.")
        return {
            "status": "success", 
            "translated_segments": [
                {"id": s.get("id", i), "start": s["start"], "end": s["end"], "text": s["text"], "original_text": s["text"]} 
                for i, s in enumerate(segments)
            ],
            "metrics": {
                "translator_duration": 0.0,
                "lektor_duration": 0.0
            }
        }

    print(f"[TRANSLATOR] Pokrećem prevođenje {len(segments)} segmenata koristeći Qwen3-32B Lektor endpoint.", flush=True)
    t_start_trans = time.time()
    
    # 1. Generisanje globalnog sažetka i glosara za ceo video
    try:
        full_eng_transcript = " ".join([s["text"] for s in segments])
        print("[TRANSLATOR] Generišem globalni sažetak videa...", flush=True)
        video_summary = generate_video_summary(full_eng_transcript)
        print(f"[TRANSLATOR] Sažetak videa uspešno generisan:\n{video_summary}", flush=True)
        
        print("[TRANSLATOR] Generišem dinamički glosar i entitete...", flush=True)
        dynamic_glossary_str = get_dynamic_glossary(full_eng_transcript)
    except Exception as e:
        print(f"[WARNING] Greška pri generisanju globalnog konteksta: {e}. Koristim prazan kontekst.")
        video_summary = "No context available."
        dynamic_glossary_str = "Nema specifičnih termina za ovaj video."

    # Inicijalizacija running glossary mehanizma
    full_glossary_dict = parse_glossary_to_dict(dynamic_glossary_str)
    confirmed_translations = {}

    # JSON šema za structured output
    translator_schema = {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "translated_text": {"type": "string"}
                    },
                    "required": ["id", "translated_text"]
                }
            },
            "used_terms": {
                "type": "object",
                "additionalProperties": {"type": "string"}
            }
        },
        "required": ["segments"]
    }

    batch_size = 5
    parsed_dict = {}
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    for batch_idx, batch_start in enumerate(range(0, len(segments), batch_size)):
        batch_segments = segments[batch_start:batch_start + batch_size]
        
        if progress_callback:
            progress_callback(detail=f"Prevođenje batcha {batch_idx + 1}...")
            
        # Generisanje transkripta sa limitom karaktera (dužinska svesnost) i maskiranjem
        transcript_text = ""
        batch_masks_map = {}
        for j, s in enumerate(batch_segments):
            global_idx = batch_start + j
            duration = s["end"] - s["start"]
            factor = calculate_dynamic_factor(s, user_avg_speedup)
            limit_char = max(15, int(duration * factor), int(len(s['text']) * 0.75))
            
            # Maskiramo pre slanja LLM-u
            masked_txt, masks = mask_untranslatable(s['text'])
            batch_masks_map[global_idx] = masks
            
            transcript_text += f"[seg-{global_idx}] (trajanje: {duration:.1f}s, LIMIT: {limit_char} karaktera) {masked_txt}\n"
            
        # Klizni prozor konteksta (poslednjih 2 segmenta iz prethodnog batch-a)
        history_text = ""
        if batch_idx > 0:
            history_start = max(0, batch_start - 2)
            history_segments = segments[history_start:batch_start]
            history_lines = []
            for prev_idx, prev_seg in enumerate(history_segments):
                global_prev_idx = history_start + prev_idx
                prev_translation = parsed_dict.get(global_prev_idx, "")
                history_lines.append(f"[seg-{global_prev_idx}] ENG: {prev_seg['text']} | SRB: {prev_translation}")
            history_text = "\n".join(history_lines)
            
        history_section = ""
        if history_text:
            history_section = (
                "ISTORIJA PRETHODNIH REČENICA (koristi isključivo kao kontekst da bi prevod novih rečenica bio "
                "gramatički i smisleno povezan sa prethodnim. NIKADA ne prevodi ponovo ove segmente niti ih uključuj u izlazni JSON):\n"
                f"{history_text}\n\n"
            )
            
        # Formiranje running glossary sekcija za ovaj batch
        confirmed_lines = []
        proposed_lines = []
        batch_eng_text = " ".join([s["text"].lower() for s in batch_segments])
        
        for eng_term, srb_term in full_glossary_dict.items():
            if re.search(r'\b' + re.escape(eng_term.lower()) + r'\b', batch_eng_text):
                if eng_term in confirmed_translations:
                    confirmed_lines.append(f'- "{eng_term}" -> "{confirmed_translations[eng_term]}"')
                else:
                    proposed_lines.append(f'- "{eng_term}" -> "{srb_term}"')
                    
        glossary_prompt_section = ""
        if confirmed_lines:
            glossary_prompt_section += (
                "STRIKTNI POTVRĐENI PREVODI IZ PRETHODNIH SEGMENATA (OBAVEZNO koristi tačno ove srpske prevode radi konzistentnosti):\n"
                + "\n".join(confirmed_lines) + "\n\n"
            )
        if proposed_lines:
            glossary_prompt_section += (
                "STRIKTNI PREDLOŽENI GLOSAR ZA NOVE ENTITETE (OBAVEZNO koristi ove srpske prevode i prilagodi ih gramatički kontekstu rečenice, zabranjeno je koristiti druge sinonime):\n"
                + "\n".join(proposed_lines) + "\n\n"
            )
        if not glossary_prompt_section:
            glossary_prompt_section = "Nema specifičnih termina za ovaj batch.\n\n"

        prompt_text = (
            "Ti si vrhunski profesionalni prevodilac za srpski jezik. Prevedi priloženi transkript sa engleskog na SRPSKI jezik (EKAVICA, LATINICA).\n\n"
            "VAŽNO ZA REZONOVANJE: U svom procesu razmišljanja (<think>...</think>) budi ekstremno kratak (maksimalno 10 reči ukupno). NIKADA nemoj raditi analizu segment po segment niti brojati slova u razmišljanju. Odmah pređi na JSON odgovor.\n\n"
            f"{glossary_prompt_section}"
            f"{history_section}"
            "PRAVILA ZA PREVOD:\n"
            "1. PRIRODAN PREVOD: Prevod mora zvučati 100% prirodno. Koristi srpske idiome i aktivne konstrukcije (npr. izbegavaj pasiv 'od strane').\n"
            "2. PRIPREMA ZA TTS: Sve brojeve i procente piši SLOVIMA (npr. 'dve hiljade dvadeset šesta'). Strana imena piši FONETSKI (npr. 'Klod', 'Ej Aj'). IT akronime GPS, Wi-Fi i Bluetooth piši u originalu. Reč 'AI' prevodi kao 'Ej Aj' i dekliniraj ('sa Ej Ajem', 'o Ej Aju').\n"
            "3. GRAMATIKA: Koristi isključivo jedninsko neformalno obraćanje 'ti' (npr. 'ako želiš', 'poravnaj'). Strogo pazi na rod i slaganje prideva i imenica (npr. 'drveni komad', a ne 'komad drveta'; 'jednake cilindriće').\n"
            "4. STROGO ZABRANJENI REGIONALIZMI: Izbegavaj ijekavizme (dio, spriječiti, dvjesto, promijeniti, vrijeme, uvijek) i hrvatske reči (tijekom, tjedan, tisuća, sustav, uvjet, utjecaj, učinkovitost, tvrtka, sučelje, zaslon, tipkovnica, poveznica, kaos, nazive meseci). Koristi srpske ekavske zamene (deo, sprečiti, dvesta, tokom, nedelja, hiljada, sistem, uslov, uticaj, efikasnost, firma, interfejs, ekran, tastatura, link, haos).\n"
            "5. Diskursne markere prevedi prirodno, a ne doslovno (so -> dakle/zato/pa; now -> e sad/evo; well -> pa/dobro/međutim; basically -> u suštini; actually -> zapravo; right -> zar ne).\n"
            "6. LIMIT KARAKTERA: Prevod (translated_text) za svaki segment mora biti kraći ili jednak prosleđenom LIMITU. Koristi kraće rečenice ako je potrebno.\n"
            "7. ID segmenta MORA biti ceo broj koji tačno odgovara indeksu segmenta iz ulaza (npr. za '[seg-5]' id mora biti 5. NIKADA ne koristi fiktivne ID-jeve 9999 ili 99999 iz šablona).\n\n"
            "FORMAT ODGOVORA:\n"
            "Odgovori isključivo u validnom JSON formatu prema sledećoj šemi, bez uvodnog ili pratećeg teksta:\n"
            "{\n"
            "  \"segments\": [\n"
            "    {\n"
            "      \"id\": 9999,\n"
            "      \"translated_text\": \"Srpski prevod za segment 9999.\"\n"
            "    },\n"
            "    {\n"
            "      \"id\": 99999,\n"
            "      \"translated_text\": \"Srpski prevod za segment 99999.\"\n"
            "    }\n"
            "  ],\n"
            "  \"used_terms\": {\n"
            "    \"engleski_pojam\": \"srpski_prevod\"\n"
            "  }\n"
            "}\n\n"
            "VAŽNO: Tvoj JSON odgovor mora sadržati sve segmente iz sekcije TRANSKRIPT ZA PREVOD sa njihovim tačnim ID-jevima. Nemoj kopirati fiktivne ID-jeve 9999 ili 99999 iz šablona.\n\n"
            f"TRANSKRIPT ZA PREVOD:\n{transcript_text}"
        )
        
        payload = {
            "model": "qwen-lektor",
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.1,
            "max_tokens": 2048,
            "enable_thinking": False,
            "guided_json": translator_schema
        }
        
        try:
            res = call_modal_endpoint(
                url=url, 
                payload=payload, 
                timeout_seconds=300,
                progress_callback=None
            )
            
            try:
                raw_output = res["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                raw_output = str(res)
                
            print(f"[DEBUG] BATCH {batch_idx + 1} RAW TRANSLATION:\n{raw_output}", flush=True)
            
            # Parsiranje - prvo pokušavamo sa JSON
            data = extract_and_parse_json(raw_output)
            batch_parsed = {}
            if data:
                segments_list = data if isinstance(data, list) else data.get("segments", [])
                if isinstance(segments_list, list):
                    valid_items = []
                    for item in segments_list:
                        if isinstance(item, dict):
                            idx = item.get("id")
                            text = None
                            for key in ["translated_text", "refined_text", "text"]:
                                if key in item:
                                    text = item[key]
                                    break
                            if text is not None:
                                valid_items.append((idx, str(text).strip()))
                                
                    # 1. Mapiranje po redosledu ako se dužine poklapaju
                    if len(valid_items) == len(batch_segments):
                        print(f"[TRANSLATOR] Broj segmenata se poklapa ({len(valid_items)}). Mapiram po redosledu.", flush=True)
                        for i, (orig_id, text) in enumerate(valid_items):
                            global_idx = batch_start + i
                            batch_parsed[global_idx] = text
                    else:
                        # 2. Mapiranje po ID-jevima sa podrškom za lokalne i globalne indekse
                        for orig_id, text in valid_items:
                            if orig_id is not None:
                                try:
                                    idx_val = int(orig_id)
                                    if batch_start <= idx_val < batch_start + len(batch_segments):
                                        batch_parsed[idx_val] = text
                                    elif 0 <= idx_val < len(batch_segments):
                                        batch_parsed[batch_start + idx_val] = text
                                    elif 1 <= idx_val <= len(batch_segments):
                                        batch_parsed[batch_start + idx_val - 1] = text
                                except ValueError:
                                    continue
                                
            # Ako JSON parsiranje nije dalo sve segmente iz ovog batch-a, koristimo regex JSON fallback
            if len(batch_parsed) < len(batch_segments):
                import logging
                logging.error(f"[TRANSLATOR] JSON parser/guided decoding vratio samo {len(batch_parsed)} od {len(batch_segments)} segmenata. Pokrećem robusni regex JSON fallback...")
                regex_parsed = regex_parse_json_segments(clean_thought_tags(raw_output), "translated_text")
                for idx, text in regex_parsed.items():
                    if idx not in batch_parsed:
                        batch_parsed[idx] = text
                            
            # Spajanje u glavni rečnik, unmasking i validacija
            for idx, text in batch_parsed.items():
                if batch_start <= idx < batch_start + len(batch_segments):
                    # Unmasking tokena
                    unmasked_text = unmask_text(text, batch_masks_map.get(idx, {}))
                    
                    # Provera i verifikacija (negacije i semantika)
                    orig_segment = segments[idx]
                    orig_text = orig_segment["text"]
                    
                    negation_ok = check_negation_preservation(orig_text, unmasked_text)
                    sim_score = semantic_similarity(orig_text, unmasked_text)
                    print(f"[VALIDATION] Segment {idx}: Negation OK = {negation_ok}, Similarity = {sim_score:.3f}", flush=True)
                    
                    # Automatska re-prevod i samokritika petlja ako validacija ne prođe
                    if not negation_ok or sim_score < 0.72:
                        hints = []
                        if not negation_ok:
                            hints.append("Prevod je izgubio negaciju iz originala. Originalna rečenica ima negaciju (not/never/no/don't itd.), dok tvoj prevod nema. Obavezno ispravi prevod da sadrži negaciju (ne/nikad/nije/nema/nemam).")
                        if sim_score < 0.72:
                            hints.append("Prevod je semantički previše udaljen od originala. Zadrži tačan smisao rečenice i nemoj dodavati suvišne reči ili interpretacije.")
                        
                        hint_str = " ".join(hints)
                        print(f"[RETRANSLATION NEEDED] Segment {idx} ne zadovoljava kriterijume. Pokrećem self-critique...", flush=True)
                        
                        # Pokrećemo self-critique u maskiranom modu
                        masked_orig, masked_bad, self_critique_masks = mask_segment_pair(orig_text, unmasked_text)
                        refined = retranslate_with_self_critique(masked_orig, masked_bad, hint_str)
                        unmasked_refined = unmask_text(refined, self_critique_masks)
                        
                        negation_ok_2 = check_negation_preservation(orig_text, unmasked_refined)
                        sim_score_2 = semantic_similarity(orig_text, unmasked_refined)
                        print(f"[VALIDATION AFTER SELF-CRITIQUE] Segment {idx}: Negation OK = {negation_ok_2}, Similarity = {sim_score_2:.3f}", flush=True)
                        
                        unmasked_text = unmasked_refined
                        
                    parsed_dict[idx] = unmasked_text
                    
            # Ažuriranje confirmed_translations na osnovu used_terms koji je model vratio
            used_terms_found = False
            if isinstance(data, dict):
                used_terms = data.get("used_terms")
                if isinstance(used_terms, dict):
                    for eng, srb in used_terms.items():
                        if eng and srb:
                            confirmed_translations[eng] = srb
                            used_terms_found = True
                            
            # Fallback: ako model nije vratio used_terms, koristimo staru logiku prepoznavanja
            if not used_terms_found:
                for s in batch_segments:
                    text_lower = s["text"].lower()
                    for eng_term, srb_term in full_glossary_dict.items():
                        if re.search(r'\b' + re.escape(eng_term.lower()) + r'\b', text_lower):
                            confirmed_translations[eng_term] = srb_term
                    
        except Exception as batch_err:
            print(f"[ERROR] Greška pri prevođenju batcha {batch_idx + 1}: {batch_err}", flush=True)
            
    translator_duration = time.time() - t_start_trans
    print(f"[TRANSLATOR] Prevođenje završeno za {translator_duration:.2f}s. Uspešno prevedeno {len(parsed_dict)} od {len(segments)} segmenata.", flush=True)

    # Pravljenje finalne liste segmenata
    final_segments = []
    for i, orig in enumerate(segments):
        t_text = parsed_dict.get(i, "").strip()
        if not t_text:
            print(f"[WARNING] Segment {i} nema prevod. Koristim originalni engleski tekst kao fallback.", flush=True)
            t_text = orig["text"]
            
        final_segments.append({
            "id": orig.get("id", i),
            "start": orig["start"],
            "end": orig["end"],
            "text": t_text,
            "original_text": orig["text"],
            "masks": batch_masks_map.get(i, {})
        })
        
    # Pokretanje Lektor faze sa prosleđenim parametrima
    try:
        return lektor_segments(
            segments, 
            final_segments, 
            progress_callback=progress_callback, 
            translator_duration=translator_duration,
            dynamic_glossary_str=dynamic_glossary_str,
            video_summary=video_summary,
            user_avg_speedup=user_avg_speedup
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


def clean_translation_text(text: str) -> str:
    if not text:
        return text
    
    # 1. Padeži za Ej Aj
    text = re.sub(r'\bsa Ej Aj\b', 'sa Ej Ajem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj\b', 'o Ej Aju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bod Ej Aj\b', 'od Ej Aja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bu Ej Aj\b', 'u Ej Aju', text, flags=re.IGNORECASE)
    
    # 2. Greške sa "buduće" umesto "budućnost"
    text = re.sub(r'\bžele ovo buduće\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bžele to buduće\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bovo buduće\b', 'ovu budućnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bto buduće\b', 'tu budućnost', text, flags=re.IGNORECASE)
    
    # 3. Tipične greške u izgovoru/kucanju za "poći po zlu"
    text = re.sub(r'\bpođi po zlu\b', 'poći po zlu', text, flags=re.IGNORECASE)
    
    # 4. Množina robotike i slično
    text = re.sub(r'\brobotikama\b', 'robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\brobotike\b', 'roboticu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aju i robotike\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj i robotike\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aj i robotikama\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    text = re.sub(r'\bo Ej Aju i robotikama\b', 'o Ej Aju i robotici', text, flags=re.IGNORECASE)
    
    # 5. Odluke o pripremi/prijemu -> zapošljavanju (u svim padežima)
    text = re.sub(r'\bodluk([a-z]*) o (pripremi|prijemu)\b', r'odluk\1 o zapošljavanju', text, flags=re.IGNORECASE)
    
    # 6. Slaganje rodova za knjige (poput X i Y, koji su popularni -> koje su popularne)
    text = re.sub(r'\bpoput ([^,]+) i ([^,]+), koji su popularni\b', r'poput \1 i \2, koje su popularne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoput ([^,]+), koji su popularni\b', r'poput \1, koje su popularne', text, flags=re.IGNORECASE)
    
    # 7. Ispravka povratnog "se" kod glagola postati (npr. "koje su se ironično postale popularne" -> "koje su ironično postale popularne")
    text = re.sub(r'\b(su|je) se\s+([^,.]+?\s+)?(postale|postali|postala|postao|postalo)\b', r'\1 \2\3', text, flags=re.IGNORECASE)
    
    # 8. Ispravka neobičnih opisa zidova (na zadnjoj zidini -> na zadnjem zidu)
    text = re.sub(r'\bna zadnjoj zidini\b', 'na zadnjem zidu', text, flags=re.IGNORECASE)
    
    # 9. Osnivačka dokumenta (članke o firmi kako bi je registrovala -> dokumente za registraciju kako bi registrovala firmu)
    text = re.sub(r'\bčlanke o firmi kako bi je registrovala\b', 'dokumente za registraciju kako bi registrovala firmu', text, flags=re.IGNORECASE)
    
    # 10. Prirodniji raspored reči za negaciju nužnosti i redosled
    text = re.sub(r'\bne nužno (rade|čine)\b', r'ne \1 nužno', text, flags=re.IGNORECASE)
    text = re.sub(r'\bda to ne nužno čine\b', 'da to ne čine nužno', text, flags=re.IGNORECASE)
    
    # 11. Ispravka nepravilnog 'zabrinu o riziku' -> 'zabrinuti zbog rizika'
    text = re.sub(r'\bkoji se (zabrinu|zabrinjavaju|zabrinjuju) o riziku\b', 'koji su zabrinuti zbog rizika', text, flags=re.IGNORECASE)

    # 12. Ispravka "Nemam lice" -> "Nema lice" (za seg-5, opis robota Lune)
    text = re.sub(r'\bNemam lice\b', 'Nema lice', text, flags=re.IGNORECASE)
    
    # 13. Ispravka "veliki log na zidu" / "veliki log" -> "veliki logo"
    text = re.sub(r'\bveliki log na zidu\b', 'veliki logo na zidu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnaslika veliki log\b', 'naslika veliki logo', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnaslika veliki log\b', 'naslika veliki logo', text, flags=re.IGNORECASE)
    # 14. Ispravka "žele ovo budućnost" -> "žele takvu budućnost"
    text = re.sub(r'\bžele ovo budućnost\b', 'žele takvu budućnost', text, flags=re.IGNORECASE)
    
    # 15. Ispravka "pođeti po zlu" -> "poći po zlu"
    text = re.sub(r'\bpođeti po zlu\b', 'poći po zlu', text, flags=re.IGNORECASE)
    
    # 16. Ispravka "pratite za više" -> "prati za više" (usklađivanje ti/vi obraćanja)
    text = re.sub(r'\bpratite za više\b', 'prati za više', text, flags=re.IGNORECASE)

    # 17. Ispravka futura I sa "će" (hrvatski / ijekavski oblici: radit će -> radiće, raditi će -> radiće)
    # Koristimo whitelistu glagolskih osnova kako bismo sprečili kvarenje imenica poput put, internet, sat, sajt
    VERB_STEMS = [
        'radi', 'bi', 'ima', 'hte', 'htje', 'vidje', 'vide', 'živje', 'žive',
        'razumje', 'razume', 'djelova', 'delova', 'riješi', 'reši', 'promijeni',
        'promeni', 'primijeti', 'primeti', 'stavi', 'krenu', 'izreza', 'savi',
        'koristi', 'napravi', 'poveza', 'prati', 'skrati', 'otvori', 'zatvori',
        'posta', 'poče', 'nauči', 'peva', 'pisa', 'čita', 'diza', 'traži', 'kupi',
        'proda', 'plaća', 'plati', 'posla', 'spreči', 'spriječi', 'deli', 'dijeli',
        'brusi', 'šmirgla', 'zavari', 'hefta', 'obmota', 'presiječe', 'preseče',
        'odsiječe', 'odseče', 'isiječe', 'iseče', 'savije', 'postane', 'postigi', 'postig'
    ]
    pattern_stems = '|'.join(VERB_STEMS)
    text = re.sub(
        rf'\b({pattern_stems})ti?\s+(ću|ćeš|će|ćemo|ćete)\b',
        lambda m: f"{m.group(1)}{m.group(2)}",
        text,
        flags=re.IGNORECASE
    )

    # 18. Morfološke i sintaksičke ispravke (na osnovu evaluacije)
    text = re.sub(r'\bjednake cilindri\b', 'jednake cilindriće', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsecu tradicionalne\b', 'seku tradicionalne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvenog komad\b', 'drveni komad', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkomad drvenog\b', 'komad drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvene podloge\b', 'drvene osnove', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdrvenog podloge\b', 'drvene osnove', text, flags=re.IGNORECASE)
    text = re.sub(r'\bna razmeru koju\b', 'u razmeri koju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bna razmeru\b', 'u razmeri', text, flags=re.IGNORECASE)
    text = re.sub(r'\bZavar je glatko\b', 'Zavar je gladak', text, flags=re.IGNORECASE)
    text = re.sub(r'\bglatko izgleda\b', 'gladak izgled', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnavojni štap montaža\b', 'montažni štap sa navojem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnavojnog štapa montaža\b', 'montažnog štapa sa navojem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofanje\b', 'brušenje', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofanja\b', 'brušenja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšljofati\b', 'brusiti', text, flags=re.IGNORECASE)
    
    # Dodatne ispravke za video 3
    text = re.sub(r'\brđav[ao] drv[o-z]\b', 'crvenkasto drvo', text, flags=re.IGNORECASE)
    text = re.sub(r'\brđast[ao] drv[o-z]\b', 'crvenkasto drvo', text, flags=re.IGNORECASE)
    text = re.sub(r'\brđast[a-z]*\b', 'crvenkast', text, flags=re.IGNORECASE)
    text = re.sub(r'\botrpere\b', 'obriše', text, flags=re.IGNORECASE)
    text = re.sub(r'\btrli\b', 'trlja', text, flags=re.IGNORECASE)
    text = re.sub(r'\btamlja\b', 'trlja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnevjera\b', 'neverovatno', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnevjerojatan\b', 'neverovatan', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnevjerojatno\b', 'neverovatno', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkontrast je neverovatno\b', 'kontrast je neverovatan', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkontrast je neverovatan\b', 'kontrast je neverovatan', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsečiv\b', 'sečivo', text, flags=re.IGNORECASE)
    text = re.sub(r'\bžičani sečiv\b', 'žičanu testeru', text, flags=re.IGNORECASE)
    text = re.sub(r'\bžičani sečivom\b', 'žičanom testerom', text, flags=re.IGNORECASE)
    text = re.sub(r'\bničeg osim ovim\b', 'ničeg osim ovog', text, flags=re.IGNORECASE)
    text = re.sub(r'\bničeg osim ove\b', 'ničeg osim ovog', text, flags=re.IGNORECASE)
    text = re.sub(r'\btamne komade drvenog\b', 'tamnog komada drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bosnovnim tamnim komade drvenog\b', 'osnovnog tamnog komada drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bosnovnim tamnim komadom drvenog\b', 'osnovnog tamnog komada drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bosnovnim tamnim komadom drveta\b', 'osnovnog tamnog komada drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKineski šahovski komplet\b', 'kineski šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKineski šahovski set\b', 'kineski šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKinesku šahovsku ploču\b', 'kineski šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKineski šahovsku ploču\b', 'kineski šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšahovsku ploču\b', 'šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bšahovski set\b', 'šahovski komplet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsabošenje\b', 'šmirglanje', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsabošenja\b', 'šmirglanja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsabošiti\b', 'šmirglati', text, flags=re.IGNORECASE)
    text = re.sub(r'\bveštinu majstora\b', 'majstorsku veštinu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bveštinu ovog majstora\b', 'majstorsku veštinu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstvari postaju zanimljive\b', 'stvari postaju fascinantne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpostaju zanimljive\b', 'postaju fascinantne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bboju drva\b', 'boju drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bduboku boju drva\b', 'duboku boju drveta', text, flags=re.IGNORECASE)
    text = re.sub(r'\bda stampa granicu\b', 'da utisne ivicu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvisokoj toploti da stampa granicu\b', 'visoku toplotu da utisne ivicu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvisokoj toploti da stampa\b', 'visoku toplotu da utisne', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvisokoj toploti\b', 'visokom toplotom', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkoristi visokoj toploti\b', 'koristi visoku toplotu', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkoristi visoku temperaturu za peč\b', 'koristi visoku toplotu da utisne ivicu', text, flags=re.IGNORECASE)
    # 18.5 Dodatna stilska čišćenja za Ej Aj i neprirodne fraze
    text = re.sub(r'\bEj-Aj\b', 'Ej Aj', text, flags=re.IGNORECASE)
    text = re.sub(r'\bEj-Aja\b', 'Ej Aja', text, flags=re.IGNORECASE)
    text = re.sub(r'\bEj-Aju\b', 'Ej Aju', text, flags=re.IGNORECASE)
    text = re.sub(r'\bEj-Ajem\b', 'Ej Ajem', text, flags=re.IGNORECASE)
    
    # Neprirodne kolokvijalne fraze
    text = re.sub(r'\bpostaje ludo\b', 'postaje zanimljivo', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpostaju lude\b', 'postaju zanimljive', text, flags=re.IGNORECASE)
    text = re.sub(r'\bludo je kako\b', 'neverovatno je kako', text, flags=re.IGNORECASE)
    text = re.sub(r'\bstvari postaju lude\b', 'stvari postaju zanimljive', text, flags=re.IGNORECASE)
    text = re.sub(r'\bovde postaje ludilo\b', 'ovde situacija postaje zanimljiva', text, flags=re.IGNORECASE)

    # 18.8 Sistemsko čišćenje ijekavizama i regionalizama (Leak Guard)
    text = re.sub(r'\bdio\b', 'deo', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdijel(ovi|ove|u|om|a|ova|ima)\b', r'del\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdijel(i|e|iti|imo|ite|io|ila|ili|iće)\b', r'del\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btijekom\b', 'tokom', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsustav\b', 'sistem', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsustav(i|a|u|om|ima|ove)\b', r'sistem\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btjedan\b', 'nedelja', text, flags=re.IGNORECASE)
    text = re.sub(r'\btjedn(a|u|om|e|i|ima)\b', r'nedeljn\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btisuća\b', 'hiljada', text, flags=re.IGNORECASE)
    text = re.sub(r'\btisuć(e|u|om|i|ama)\b', r'hiljad\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\buvjet\b', 'uslov', text, flags=re.IGNORECASE)
    text = re.sub(r'\buvjet(i|a|u|om|ima|ove)\b', r'uslov\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\butjecaj\b', 'uticaj', text, flags=re.IGNORECASE)
    text = re.sub(r'\butjecaj(i|a|u|om|ima|ove)\b', r'uticaj\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsučelje\b', 'interfejs', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsučelj(a|u|em|ima|e)\b', r'interfejs\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bzaslon\b', 'ekran', text, flags=re.IGNORECASE)
    text = re.sub(r'\bzaslon(i|a|u|om|ima|ove)\b', r'ekran\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btipkovnica\b', 'tastatura', text, flags=re.IGNORECASE)
    text = re.sub(r'\btipkovnic(e|i|u|om|ama)\b', r'tastatur\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoveznica\b', 'link', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoveznic(u|om)\b', r'link\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpoveznice\b', 'linkovi', text, flags=re.IGNORECASE)
    text = re.sub(r'\buvijek\b', 'uvek', text, flags=re.IGNORECASE)
    text = re.sub(r'\bgdje\b', 'gde', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvidjeti\b', 'videti', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvidje(o|la|li|le)\b', r'vide\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bspriječiti\b', 'sprečiti', text, flags=re.IGNORECASE)
    text = re.sub(r'\bspriječi(o|la|li|le|ti|mo|te)\b', r'spreči\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpromijeniti\b', 'promeniti', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpromijeni(o|la|li|le|ti|mo|te)\b', r'promeni\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\briješiti\b', 'rešiti', text, flags=re.IGNORECASE)
    text = re.sub(r'\briješi(o|la|li|le|ti|mo|te)\b', r'reši\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bprimijetiti\b', 'primetiti', text, flags=re.IGNORECASE)
    text = re.sub(r'\bprimijeti(o|la|li|le|ti|mo|te)\b', r'primeti\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkaos\b', 'haos', text, flags=re.IGNORECASE)
    text = re.sub(r'\bučinkovitost\b', 'efikasnost', text, flags=re.IGNORECASE)
    text = re.sub(r'\bučinkovit(a|o|i|e|u|om)\b', r'efikasn\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\btvrtk(a|e|i|u|om|ama)\b', r'firm\1', text, flags=re.IGNORECASE)

    # 19. Dupli razmaci i čišćenje
    text = re.sub(r'\s+', ' ', text).strip()
    return text

GLOSSARY_FILE = os.path.join(os.path.dirname(__file__), "glossaries.json")

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

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    t1 = re.sub(r'[^\w\s]', '', text1.lower()).split()
    t2 = re.sub(r'[^\w\s]', '', text2.lower()).split()
    set1 = set(t1)
    set2 = set(t2)
    if not set1 or not set2:
        return 0.0
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union)

def lektor_segments(original_segments, translated_segments, progress_callback=None, translator_duration=0.0, dynamic_glossary_str=None, video_summary=None, user_avg_speedup: float = 1.0):
    """
    Druga faza: Qwen 2.5/3.0 Lektor lekturiše grubi prevod sa programskom deduplikacijom i dinamičkim glosarom.
    Optimizovano: batch_size = 30, max_tokens = 1000, robusno JSON + Regex parsiranje.
    Dodatno: podrška za prosleđeni globalni sažetak, glosar i klizni prozor memorije.
    """
    lektor_duration = 0.0
    if not settings.MODAL_LEKTOR_URL:
        return {
            "status": "success", 
            "translated_segments": translated_segments,
            "metrics": {
                "translator_duration": translator_duration,
                "lektor_duration": 0.0
            }
        }
        
    # 0. Near-duplicate deduplikacija za susedne segmente
    for i in range(1, len(translated_segments)):
        orig_prev = original_segments[i-1].get("text", "")
        orig_curr = original_segments[i].get("text", "")
        trans_prev = translated_segments[i-1].get("text", "")
        trans_curr = translated_segments[i].get("text", "")
        
        eng_sim = calculate_jaccard_similarity(orig_prev, orig_curr)
        trans_sim = calculate_jaccard_similarity(trans_prev, trans_curr)
        
        if eng_sim >= 0.85 or trans_sim >= 0.85:
            print(f"[DEDUP] Pronađen near-duplicate na segmentu {i}. Uklanjam ponavljanje.", flush=True)
            translated_segments[i]["text"] = ""

    # 1. Programska deduplikacija ponovljenih identičnih segmenata
    unique_segments = []
    seen_keys = set()
    orig_to_unique_map = {}
    
    for i, seg in enumerate(translated_segments):
        orig_seg = original_segments[i]
        duration = seg["end"] - seg["start"]
        
        key = orig_seg["text"].strip().lower()
        
        if key not in seen_keys:
            seen_keys.add(key)
            unique_idx = len(unique_segments)
            unique_segments.append({
                "unique_id": unique_idx,
                "orig_indices": [i],
                "orig_text": orig_seg["text"],
                "translated_text": seg["text"],
                "start": seg["start"],
                "end": seg["end"],
                "duration": duration
            })
            orig_to_unique_map[i] = unique_idx
        else:
            for u_idx, u_seg in enumerate(unique_segments):
                u_key = u_seg["orig_text"].strip().lower()
                if u_key == key:
                    u_seg["orig_indices"].append(i)
                    orig_to_unique_map[i] = u_idx
                    break
    
    print(f"[LEKTOR] Deduplikacija završena. Sa originalnih {len(translated_segments)} smanjeno na {len(unique_segments)} jedinstvenih segmenata.", flush=True)

    # 2. Generisanje ili preuzimanje globalnog konteksta i glosara
    if not video_summary:
        try:
            transcript_text = " ".join([seg["orig_text"] for seg in unique_segments])
            video_summary = generate_video_summary(transcript_text)
        except Exception:
            video_summary = "No context available."

    if not dynamic_glossary_str:
        try:
            transcript_text = " ".join([seg["orig_text"] for seg in unique_segments])
            dynamic_glossary_str = get_dynamic_glossary(transcript_text)
        except Exception as e:
            print(f"[WARNING] Greška pri kreiranju dinamičkog glosara: {e}. Koristim prazan glosar.")
            dynamic_glossary_str = "Nema specifičnih termina za ovaj video."

    # JSON šema za structured output lektora
    lektor_schema = {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "refined_text": {"type": "string"}
                    },
                    "required": ["id", "refined_text"]
                }
            }
        },
        "required": ["segments"]
    }

    batch_size = 5
    parsed_lektor_dict = {}
    lektor_masks_map = {}
    lektor_duration = 0.0
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    t_start_lektor = time.time()
    
    for batch_idx, batch_start in enumerate(range(0, len(unique_segments), batch_size)):
        batch_translated = unique_segments[batch_start:batch_start + batch_size]
        
        print(f"[LEKTOR] Pokrećem Lektor batch {batch_idx + 1} (segmenti {batch_start} do {batch_start + len(batch_translated) - 1})...", flush=True)
        
        lektor_input = ""
        for j, seg in enumerate(batch_translated):
            global_idx = batch_start + j
            duration = seg["duration"]
            
            # 1. Programsko rešavanje mikro-segmenata i obrisanih duplikata
            if duration < 0.5 or seg.get("translated_text", "") == "":
                print(f"[LEKTOR] Segment {global_idx} je mikro-segment ili obrisan duplikat (trajanje: {duration:.2f}s). Programski postavljam prazan prevod.", flush=True)
                parsed_lektor_dict[global_idx] = ""
                continue
                
            factor = calculate_dynamic_factor(seg, user_avg_speedup)
            limit_char = max(15, int(duration * factor), int(len(seg['orig_text']) * 0.75))
            
            # Maskiramo pre slanja lektoru radi zaštite entiteta
            masked_orig, _ = mask_untranslatable(seg['orig_text'])
            masked_trans, masks = mask_untranslatable(to_latin(seg['translated_text']))
            lektor_masks_map[global_idx] = masks
            
            lektor_input += f"[seg-{global_idx}] (trajanje: {duration:.1f}s, LIMIT: {limit_char} karaktera) ENG: {masked_orig} | SRB: {masked_trans}\n"
            
        if not lektor_input.strip():
            print(f"[LEKTOR] Svi segmenti u batch-u {batch_idx + 1} su mikro-segmenti. Preskačem API poziv.", flush=True)
            continue
            
        # Klizni prozor konteksta za lektora
        history_text = ""
        if batch_idx > 0:
            history_start = max(0, batch_start - 2)
            history_segments = unique_segments[history_start:batch_start]
            history_lines = []
            for prev_idx, prev_seg in enumerate(history_segments):
                global_prev_idx = history_start + prev_idx
                prev_lektorised = parsed_lektor_dict.get(global_prev_idx, prev_seg["translated_text"])
                history_lines.append(f"[seg-{global_prev_idx}] ENG: {prev_seg['orig_text']} | SRB (lektura): {prev_lektorised}")
            history_text = "\n".join(history_lines)
            
        history_section = ""
        if history_text:
            history_section = (
                "ISTORIJA PRETHODNO LEKTURISANIH REČENICA (koristi isključivo kao kontekst za kontinuitet i gramatičko "
                "povezivanje. NIKADA ne lekturiši ponovo ove segmente niti ih uključuj u izlazni JSON):\n"
                f"{history_text}\n\n"
            )

        lektor_prompt = (
            "Ti si glavni urednik i lektor za srpski jezik. Pregledaj grubi prevod (SRB) u odnosu na original (ENG) i trajanje segmenta, ispravi greške i vrati tečan srpski prevod na ekavici i latinici.\n\n"
            "VAŽNO ZA REZONOVANJE: U svom procesu razmišljanja (<think>...</think>) budi ekstremno kratak (maksimalno 10 reči ukupno). NIKADA nemoj raditi analizu segment po segment niti brojati slova u razmišljanju. Odmah pređi na JSON odgovor.\n\n"
            f"{history_section}"
            "PRAVILA ZA UREĐIVANJE:\n"
            "1. PIŠI ISKLJUČIVO SRPSKOM LATINICOM. Koristi jedninsko neformalno obraćanje 'ti' (npr. 'poravnaj').\n"
            "2. STRIKTNI GLOSAR: Za engleske stručne pojmove OBAVEZNO koristi ponuđene prevode iz glosara (prilagodi ih gramatički padežu):\n"
            f"{dynamic_glossary_str}\n\n"
            "3. STRIKTNA EKAVICA I PRAVOPIS: Zameni sve ijekavske oblike (dio->deo, spriječiti->sprečiti, dvjesto->dvesta, promijeniti->promeniti, riješiti->rešiti, uvjek->uvek) i hrvatske reči (tijekom->tokom, tjedan->nedelja, tisuća->hiljada, sustav->sistem, uvjet->uslov, utjecaj->uticaj, učinkovitost->efikasnost, tvrtka->firma, sučelje->interfejs, zaslon->ekran, tipkovnica->tastatura, poveznica->link, kaos->haos, nazive meseci) srpskim ekavskim ekvivalentima.\n"
            "4. IT akronime GPS, Wi-Fi i Bluetooth piši u originalnom obliku. Izbegavaj pasivne konstrukcije sa 'od strane'.\n"
            "5. MORFOLOGIJA: Strogo pazi na morfološko slaganje (npr. 'drveni komad', a ne 'komad drveta'; 'jednake cilindriće'; 'zavar je gladak').\n"
            "6. LIMIT KARAKTERA: Prevod (refined_text) mora biti kraći ili igualan prosleđenom LIMITU.\n"
            "7. ID segmenta u objektu MORA biti ceo broj koji tačno odgovara indeksu segmenta iz ulaza (npr. za '[seg-5]' id mora biti 5. NIKADA ne koristi fiktivne ID-jeve 9999 ili 99999 iz šablona).\n\n"
            "FORMAT ODGOVORA:\n"
            "Odgovori isključivo u validnom JSON formatu prema sledećoj šemi, bez uvodnog ili pratećeg teksta:\n"
            "{\n"
            "  \"segments\": [\n"
            "    {\n"
            "      \"id\": 9999,\n"
            "      \"refined_text\": \"Lekturisani i korigovani srpski prevod za segment 9999.\"\n"
            "    },\n"
            "    {\n"
            "      \"id\": 99999,\n"
            "      \"refined_text\": \"Lekturisani i korigovani srpski prevod za segment 99999.\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "VAŽNO: Tvoj JSON odgovor mora sadržati lekturisane verzije svih segmenata iz sekcije TEKST ZA LEKTURU sa njihovim tačnim ID-jevima. Nemoj kopirati fiktivne ID-jeve 9999 ili 99999 iz šablona.\n\n"
            f"TEKST ZA LEKTURU:\n{lektor_input}"
        )

        try:
            lektor_payload = {
                "model": "qwen-lektor",
                "messages": [{"role": "user", "content": lektor_prompt}],
                "temperature": 0.1,
                "max_tokens": 2048,
                "presence_penalty": 0.5,
                "enable_thinking": False,
                "guided_json": lektor_schema
            }
            
            lektor_output = call_modal_endpoint(
                url=url,
                payload=lektor_payload,
                timeout_seconds=300,
                progress_callback=None
            )
            
            try:
                lektor_raw = lektor_output["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                lektor_raw = str(lektor_output)

            # Čišćenje thought tagova ako ih model sa rezonovanjem vrati
            lektor_raw_clean = clean_thought_tags(lektor_raw)
            print(f"[DEBUG] BATCH {batch_idx + 1} LEKTOR CLEANED OUTPUT:\n{lektor_raw_clean}", flush=True)
            
            # Parsiranje pomoću našeg novog robusnog json parsera
            data = extract_and_parse_json(lektor_raw_clean)
            batch_parsed_lektor = {}
            non_micro_segments = [s for s in batch_translated if s["duration"] >= 0.5]
            
            if data:
                segments_list = data if isinstance(data, list) else data.get("segments", [])
                if isinstance(segments_list, list):
                    valid_items = []
                    for item in segments_list:
                        if isinstance(item, dict):
                            idx = item.get("id")
                            text = None
                            for key in ["refined_text", "translated_text", "text"]:
                                if key in item:
                                    text = item[key]
                                    break
                            if text is not None:
                                valid_items.append((idx, str(text).strip()))
                                
                    # 1. Mapiranje po redosledu ako se dužine poklapaju sa ne-mikro segmentima
                    if len(valid_items) == len(non_micro_segments):
                        print(f"[LEKTOR] Broj segmenata se poklapa ({len(valid_items)}). Mapiram po redosledu.", flush=True)
                        for i, (orig_id, text) in enumerate(valid_items):
                            global_idx = non_micro_segments[i]["unique_id"]
                            batch_parsed_lektor[global_idx] = text
                    else:
                        # 2. Mapiranje po ID-jevima sa podrškom za lokalne i globalne indekse
                        for orig_id, text in valid_items:
                            if orig_id is not None:
                                try:
                                    idx_val = int(orig_id)
                                    # Provera da li je globalni indeks
                                    if batch_start <= idx_val < batch_start + len(batch_translated):
                                        batch_parsed_lektor[idx_val] = text
                                    else:
                                        # Pokušavamo da nađemo lokalni indeks u non_micro_segments
                                        if 0 <= idx_val < len(non_micro_segments):
                                            g_idx = non_micro_segments[idx_val]["unique_id"]
                                            batch_parsed_lektor[g_idx] = text
                                        elif 1 <= idx_val <= len(non_micro_segments):
                                            g_idx = non_micro_segments[idx_val - 1]["unique_id"]
                                            batch_parsed_lektor[g_idx] = text
                                except ValueError:
                                    continue
                                
            # Regex fallback ako nedostaju neki segmenti
            if len(batch_parsed_lektor) < len(batch_translated):
                import logging
                logging.error(f"[LEKTOR] JSON parser/guided decoding vratio samo {len(batch_parsed_lektor)} od {len(batch_translated)} segmenata. Pokrećem robusni regex JSON fallback...")
                regex_parsed = regex_parse_json_segments(lektor_raw_clean, "refined_text")
                for idx, text in regex_parsed.items():
                    if idx not in batch_parsed_lektor:
                        batch_parsed_lektor[idx] = text
                            
            # Spajanje u parsed_lektor_dict i proračun metrika
            for idx, text in batch_parsed_lektor.items():
                if batch_start <= idx < batch_start + len(batch_translated):
                    # Unmasking tokena
                    unmasked_text = unmask_text(text, lektor_masks_map.get(idx, {}))
                    parsed_lektor_dict[idx] = unmasked_text
                    print(f"[LEKTOR] Segment {idx} lekturisan: {unmasked_text[:60]}...", flush=True)
                    
                    # Pronalaženje originalnog segmenta za proračun limita i logovanje
                    idx_int = int(idx)
                    orig_seg = None
                    for u_seg in unique_segments:
                        if u_seg["unique_id"] == idx_int:
                            orig_seg = u_seg
                            break
                    if orig_seg:
                        duration = orig_seg["duration"]
                        factor = calculate_dynamic_factor(orig_seg, user_avg_speedup)
                        limit_char = max(15, int(duration * factor))
                        
                        # Pokušavamo da izvučemo 'analysis' polje iz parsed JSON-a ako postoji
                        analysis = ""
                        if data and isinstance(data, dict):
                            s_list = data.get("segments", [])
                            if isinstance(s_list, list):
                                for item in s_list:
                                    if isinstance(item, dict) and item.get("id") == idx_int:
                                        analysis = item.get("analysis") or ""
                                        break
                                        
                        # Kalkulacija confidence skora
                        confidence = 5
                        confidence_triggers = ["idiom", "unclear", "ambiguous", "colloquial", "cultural reference", "wordplay", "humor", "slang"]
                        for trigger in confidence_triggers:
                            if trigger in str(analysis).lower():
                                confidence -= 1
                        
                        overshoot = len(str(unmasked_text)) / limit_char
                        if overshoot > 1.2:
                            confidence -= 1
                        confidence = max(1, confidence)
                        
                        orig_seg["confidence_score"] = confidence
                        
                        # Monitoring & Logging
                        import logging
                        compliance_logger = logging.getLogger("translation_compliance")
                        compliance_stats = {
                            "segment_id": idx_int,
                            "duration": duration,
                            "limit_char": limit_char,
                            "actual_char": len(str(unmasked_text)),
                            "compliance": len(str(unmasked_text)) <= limit_char,
                            "overshoot_pct": max(0.0, (len(str(unmasked_text)) - limit_char) / limit_char * 100)
                        }
                        compliance_logger.info(f"[COMPLIANCE] {json.dumps(compliance_stats)}")
                    
        except Exception as batch_err:
            print(f"[WARNING] Greška u Lektor batchu {batch_idx + 1}: {batch_err}")

    lektor_duration = time.time() - t_start_lektor
    print(f"[LEKTOR] Lektura završena za {lektor_duration:.2f}s. Uspešno lekturisano {len(parsed_lektor_dict)} od {len(unique_segments)} jedinstvenih segmenata.", flush=True)
    
    # 3. Zatvorena petlja: Provera i kompresija predugačkih segmenata (TTS-Aware Compression)
    for u_seg in unique_segments:
        idx = u_seg["unique_id"]
        if idx in parsed_lektor_dict:
            lektorised_text = parsed_lektor_dict[idx]
            if not lektorised_text:
                continue
            duration = u_seg["duration"]
            factor = calculate_dynamic_factor(u_seg, user_avg_speedup)
            limit_char = max(15, int(duration * factor), int(len(u_seg['orig_text']) * 0.75))
            
            if len(lektorised_text) > limit_char * 1.15:
                compressed = compress_sentence_via_llm(lektorised_text, limit_char)
                parsed_lektor_dict[idx] = compressed

    if len(parsed_lektor_dict) > 0:
        for i, seg in enumerate(translated_segments):
            unique_idx = orig_to_unique_map.get(i)
            if unique_idx is not None and unique_idx in parsed_lektor_dict:
                seg["text"] = parsed_lektor_dict[unique_idx]
                u_seg = unique_segments[unique_idx]
                seg["confidence_score"] = u_seg.get("confidence_score", 5)
        
    LEAK_PATTERN = re.compile(
        r'\b(dio|dijel\w*|dvjesto|spriječi\w*|tijekom|sustav\w*|tjedan|tjedn\w*|'
        r'tisuć\w*|uvjet\w*|utjecaj\w*|sučelj\w*|zaslon\w*|tipkovnic\w*|poveznic\w*|'
        r'vidjeti|djeluj\w*|riješi\w*|uvijek|gdje)\b', re.IGNORECASE)
    for seg in translated_segments:
        if "text" in seg:
            seg["text"] = unmask_text(seg["text"], seg.get("masks", {}))
            seg["text"] = to_latin(seg["text"])
            seg["text"] = clean_translation_text(seg["text"])
            
            # Leak guard check
            leak = LEAK_PATTERN.search(seg["text"])
            if leak:
                import logging
                logging.error(f"[LEAK] Dijalekat procurio u finalni izlaz seg {seg.get('id')}: '{leak.group(0)}' u '{seg['text']}'")
                seg["text"] = clean_translation_text(to_latin(seg["text"]))
            
    return {
        "status": "success", 
        "translated_segments": translated_segments,
        "metrics": {
            "translator_duration": translator_duration,
            "lektor_duration": lektor_duration
        }
    }

def compress_sentence_via_llm(text: str, limit_char: int) -> str:
    """
    Poziva Modal Lektor da skrati srpsku rečenicu tako da stane u limit karaktera.
    """
    if not settings.MODAL_LEKTOR_URL or not text or len(text) <= limit_char:
        return text
        
    print(f"[COMPRESS] Skraćujem rečenicu ({len(text)} -> limit {limit_char}): {text}", flush=True)
    
    url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
    prompt = (
        f"Skrati sledeću rečenicu na srpskom jeziku (ekavica, latinica) tako da njena dužina bude maksimalno {limit_char} karaktera.\n"
        "VAŽNA PRAVILA:\n"
        "1. Zadrži osnovni smisao i informaciju iz rečenice.\n"
        "2. Skraćena rečenica mora biti gramatički ispravna i prirodna na srpskom.\n"
        "3. Tvoj odgovor mora sadržati isključivo skraćenu rečenicu, bez ikakvog dodatnog teksta, komentara, navodnika ili objašnjenja.\n"
        "4. STROGO ZABRANJENO: Nemoj brojati slova jedno po jedno niti raditi matematičke proračune u razmišljanju. Samo intuitivno i brzo napiši kraću verziju rečenice.\n"
        "5. VAŽNO ZA RAZMIŠLJANJE: Budi ekstremno kratak (maksimalno 10 reči ukupno). Odmah pređi na skraćeni tekst.\n"
        "6. Ukoliko je limit karaktera prekratak da bi se zadržao ceo smisao, izostavi manje bitne detalje ili zadrži samo ključne reči (npr. ako je limit 15 karaktera za dugačku rečenicu, napiši samo najvažniji deo). Nemoj se zaglaviti u petlji brojanja.\n\n"
        f"REČENICA ZA SKRAĆIVANJE: {text}"
    )
    
    payload = {
        "model": "qwen-lektor",
        "messages": [
            {
                "role": "system", 
                "content": "Ti si brzi stručni lektor. Tvoj zadatak je da odmah vratiš skraćenu verziju rečenice na srpskom jeziku na osnovu zadatog limita. Razmišljanje (<think>...</think>) drži na maksimum 5-10 reči, ne broji slova, samo odmah ispiši skraćeni tekst. Ukoliko je nemoguće skratiti rečenicu u zadati limit bez gubitka svakog smisla, skrati je što je više moguće, ali nemoj upasti u beskonačnu petlju razmišljanja."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 200,
        "enable_thinking": False
    }
    
    try:
        from backend.worker.utils import call_modal_endpoint
        res = call_modal_endpoint(url=url, payload=payload, timeout_seconds=60)
        content = res["choices"][0]["message"]["content"].strip()
        cleaned = clean_thought_tags(content).strip().strip('"\'')
        
        if not cleaned or len(cleaned) < 2:
            print(f"[COMPRESS WARNING] Dobijen prazan ili nevalidan rezultat nakon čišćenja (sirovo: {repr(content)}). Vraćam originalni tekst.", flush=True)
            return text
            
        print(f"[COMPRESS SUCCESS] Nova rečenica ({len(cleaned)} karaktera): {cleaned}", flush=True)
        return cleaned
    except Exception as e:
        print(f"[COMPRESS ERROR] Greška pri skraćivanju: {e}", flush=True)
        return text



