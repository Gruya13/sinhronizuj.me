import re

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
