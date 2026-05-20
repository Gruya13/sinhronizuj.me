import requests
import json
import cv2
import base64
import os
import time
import re
from typing import List, Dict
from backend.core.config import settings
from backend.worker.utils import call_modal_endpoint

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
    print(f"[MULTIMODAL] Izvučeno {len(frames_b64)} frejmova za vizuelni kontekst.")
    return frames_b64

def translate_segments(segments: list, video_path: str = None, progress_callback=None) -> dict:
    """
    Poziva Modal Serverless Translator (Qwen2-VL) koristeći vLLM OpenAI Vision format.
    """
    if not segments:
        return {"status": "success", "translated_segments": []}

    if not settings.MODAL_TRANSLATOR_URL:
        print("[WARNING] MODAL_TRANSLATOR_URL nije definisan. Vraćam originalni tekst.")
        return {
            "status": "success", 
            "translated_segments": [
                {"start": s["start"], "end": s["end"], "text": s["text"]} 
                for s in segments
            ]
        }

    # Priprema tekstualnog ulaza
    transcript_text = ""
    for i, s in enumerate(segments):
        transcript_text += f"{i}|{s['text']}\n"
    
    # Ekstrakcija frejmova za vizuelni kontekst
    frames_b64 = []
    if video_path:
        if progress_callback:
            progress_callback(detail="Analiza vizuelnog konteksta (ekstrakcija frejmova)...")
        frames_b64 = extract_video_frames(video_path, num_frames=10)

    # Priprema multimodalnog content-a za Qwen2-VL (OpenAI format)
    prompt_text = (
        "Ti si vrhunski profesionalni prevodilac za srpski jezik. Tvoj zadatak je da prevedeš priloženi transkript sa engleskog na SRPSKI jezik (EKAVICA).\n\n"
        "PRAVILA ZA PREVOD:\n"
        "1. ZNAČENJE, A NE BUKVALNI PREVOD: Prevod mora zvučati 100% prirodno. Koristi srpske idiome i termine (npr. 'articles of incorporation' su 'osnivački akti' ili 'registracioni dokumenti', a ne 'članci u korporaciju').\n"
        "2. PRIPREMA TEKSTA ZA TTS (SINTEZU GLASA) - ZLATNA PRAVILA:\n"
        "   - BROJEVI SLOVIMA: Sve brojeve, cifre i procente obavezno piši SLOVIMA (npr. 'sto hiljada dolara' umesto '100.000 dolara', 'tri godine' umesto '3 godine', 'pet minuta' umesto '5 minuta'). Godine (npr. 'dve hiljade dvadeset šesta') takođe piši slovima.\n"
        "   - FONETSKI STRANI BRENDOVI: Sve strane brendove, platforme i lična imena piši isključivo FONETSKI, tj. onako kako se izgovaraju na srpskom (npr. 'Linkedinu' umesto 'LinkedIn-u', 'Indidu' umesto 'Indeed-u', 'Kregzlistu' umesto 'Craigslist-u', 'Zumu' umesto 'Zoom-u', 'Klodu' umesto 'Claude-u', 'Ej-Aj' umesto 'AI'). Ne ostavljaj engleski pravopis niti crtice.\n"
        "3. GRAMATIKA I PRAVOPIS: Sve rečenice moraju biti gramatički ispravne. Posebno obrati pažnju:\n"
        "   - Glagol 'raditi' u 3. licu množine prezenta je isključivo 'RADE' (nikada 'radu').\n"
        "   - Množina imenice 'intervju' u akuzativu je 'INTERVJUE' (nikada 'intervjuove').\n"
        "   - Ne izmišljaj reči. Koristi standardne glagole (npr. 'unajmiti/angažovati' umesto 'naimeniti', 'naslikati' umesto 'namalovati').\n"
        "   - Strana imena i gradove prilagodi srpskom pravopisu (npr. 'u San Francisku' umesto 'u San Franciscu').\n"
        "4. LOKALIZACIJA TERMINA: Reč 'store' prevodi kao 'prodavnica' ili 'lokal' (trgovina je privredna grana). 'Retail lease' je 'zakup lokala' ili 'zakup prostora'. Frazu 'they'd rather' prevedi kao 'oni bi radije' ili 'radije bi' (nikako ne mešaj sa 'radnja'). Poznate knjige prevedi ako postoji poznat prevod (npr. 'Brave New World' -> 'Vrli novi svet').\n"
        "5. KONTEKST CELINE: Transkript je jedna povezana priča. Razumi ceo kontekst pre nego što prevedeš pojedinačni red.\n"
        "6. POL GOVORNIKA: Prilagodi glagole u prošlom vremenu u zavisnosti od pola (vidi priložene slike).\n\n"
        "PRIMER TRANSLACIJE:\n"
        "Ulaz:\n"
        "0|So this company just gave an AI agent $100 ,000, a credit card, and a three -year retail lease in San Francisco to see if he could run a store.\n"
        "1|Andon Labs built the AI and they named it Luna on Claude and gave her one direction, turn a profit.\n"
        "2|Within five minutes of turning on, she had posted job listings on LinkedIn, Indeed, and Craigslist, and even uploaded articles on incorporation to verify the business.\n"
        "3|And what's crazy is that Luna actually conducted interviews over Zoom with her camera off.\n"
        "4|They're doing it because they believe it's coming regardless, and they'd rather find out what could go wrong first.\n"
        "Izlaz:\n"
        "0|Ova kompanija je dala Ej-Aj agentu sto hiljada dolara, kreditnu karticu i trogodišnji zakup lokala u San Francisku kako bi videli da li može da vodi prodavnicu.\n"
        "1|Andon Labs je kreirao ovaj Ej-Aj i nazvao ga Luna (zasnovan na Klodu), a dali su joj samo jedno uputstvo: da ostvari profit.\n"
        "2|U roku od pet minuta nakon uključivanja, ona je objavila oglase za posao na Linkedinu, Indidu i Kregzlistu, pa čak i podnela osnivačke akte kako bi registrovala firmu.\n"
        "3|A najluđe od svega je to što je Luna zapravo vodila intervjue preko Zuma sa isključenom kamerom.\n"
        "4|Rade to jer veruju da to svakako dolazi i radije bi da prvi saznaju šta sve može da pođe po zlu.\n\n"
        "PRAVILA ZA FORMAT:\n"
        "1. Odgovor mora biti ISKLJUČIVO red po red, u formatu: ID|Prevedeni tekst\n"
        f"2. Tvoj odgovor mora sadržati TAČNO {len(segments)} redova (0 do {len(segments)-1}).\n"
        "3. Ne dodaj nikakav uvod ni zaključak.\n\n"
        f"TRANSKRIPT ZA PREVOD:\n{transcript_text}"
    )




    content = [{"type": "text", "text": prompt_text}]
    for f in frames_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{f}"}})

    payload = {
        "model": "qwen-vl",
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 4096
    }

    print(f"[TRANSLATOR VL] Šaljem {len(segments)} segmenata na Modal Translator: {settings.MODAL_TRANSLATOR_URL}")
    
    try:
        base_url = settings.MODAL_TRANSLATOR_URL.rstrip('/')
        if not base_url.endswith('/v1'):
            base_url += '/v1'
        url = f"{base_url}/chat/completions"
        
        output = call_modal_endpoint(
            url=url, 
            payload=payload, 
            timeout_seconds=900,
            progress_callback=progress_callback
        )
        
        try:
            raw_output = output["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raw_output = str(output)

        print(f"[DEBUG] RAW TRANSLATION OUTPUT: {raw_output[:500]}...", flush=True)
        
        # Parsiranje tekstualnog izlaza
        parsed_lines = []
        for line in raw_output.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 1)
            if len(parts) == 2:
                text = parts[1].strip()
                if text:
                    parsed_lines.append(text)
                        
        final_segments = []
        for i, orig in enumerate(segments):
            t_text = parsed_lines[i] if i < len(parsed_lines) else ""
            final_segments.append({
                "start": orig["start"],
                "end": orig["end"],
                "text": t_text or orig["text"],
                "original_text": orig["text"]
            })
            
        # POKRETANJE LEKTOR FAZE (KORAK 4.D)
        return lektor_segments(segments, final_segments, progress_callback=progress_callback)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

def lektor_segments(original_segments, translated_segments, progress_callback=None):
    """
    Druga faza: Qwen 2.5 32B (Lektor) lekturiše grubi prevod.
    """
    if not settings.MODAL_LEKTOR_URL:
        return {"status": "success", "translated_segments": translated_segments}
        
    print(f"[LEKTOR] Pokrećem Lektor fazu na {settings.MODAL_LEKTOR_URL}...")
    if progress_callback:
        progress_callback(detail="Lektura i poliranje prevoda (Qwen 32B)...")
        
    lektor_input = ""
    for i, seg in enumerate(translated_segments):
        lektor_input += f"{i}|ENG: {original_segments[i]['text']} | SRB: {seg['text']}\n"
        
    lektor_prompt = (
        "Ti si glavni lektor i korektor za srpski jezik (ekavica). Tvoj jedini zadatak je da detaljno pregledaš grubi prevod i ispraviš gramatiku, padeže, pravopis, idiome i neprirodne izraze.\n\n"
        "PRAVILA ZA LEKTURU:\n"
        "1. KORIGUJ GRAMATIKU I OBLIKE REČI:\n"
        "   - Strogo ispravi izmišljene ili nepravilne oblike reči: 'radu' -> ispravi u 'rade', 'intervjuove' -> ispravi u 'intervjue', 'naimenila' -> 'unajmila/angažovala', 'namaluje' -> 'naslika/nacrta'.\n"
        "   - Pazi na rod i slaganje zamenica (npr. 'logo koji je dizajnirala', a ne 'logo koju').\n"
        "   - Strana imena i gradove moraju biti u srpskoj transkripciji (npr. 'u San Francisku' umesto 'u San Franciscu').\n"
        "2. PRIPREMA TEKSTA ZA TTS (SINTEZU GLASA) - ZLATNA PRAVILA:\n"
        "   - BROJEVI SLOVIMA: Sve brojeve i cifre obavezno ispravi tako da budu napisani SLOVIMA (npr. '100.000 dolara' ili '100,000' -> 'sto hiljada dolara', '3 godine' -> 'tri godine').\n"
        "   - FONETSKI STRANI BRENDOVI: Sve strane brendove, platforme i lična imena obavezno ispravi da budu napisani isključivo FONETSKI, onako kako se izgovaraju na srpskom (npr. 'LinkedIn' ili 'LinkedIn-u' -> 'Linkedinu', 'Indeed' ili 'Indeed-u' -> 'Indidu', 'Craigslist' -> 'Kregzlistu', 'Zoom' -> 'Zumu', 'Claude' -> 'Klodu', 'AI' -> 'Ej-Aj'). Ukloni engleski pravopis, crtice i engleske nastavke.\n"
        "3. POPRAVI SMISAO I BUKVALNE PREVODE:\n"
        "   - Engleski tekst je dat kao kontekst (ENG). Ako je prevodilac napravio logičku grešku (npr. preveo 'they'd rather' kao 'radnja preferirala'), ti to obavezno ispravi u prirodan izraz ('oni bi radije' ili 'radije bi').\n"
        "   - 'articles of incorporation' ispravi u 'osnivački akti' ili 'registracioni dokumenti'.\n"
        "   - 'store' ispravi u 'prodavnica' ili 'lokal' (nikako 'trgovina').\n"
        "4. Zadrži isti broj linija. Svaka linija mora početi sa ID| (npr. 0|Korigovani prevod).\n"
        "5. Vrati SAMO korigovane redove, bez ikakvih uvoda ili komentara.\n\n"
        "PRIMER LEKTURE:\n"
        "Ulaz:\n"
        "0|ENG: So this company just gave an AI agent $100 ,000, a credit card, and a three -year retail lease in San Francisco to see if he could run a store. | SRB: Ova kompanija je dala AI agenciji 100.000 dolara, kreditnu karticu i tri godine retail leasa u San Francisku kako bi provjerila da li je moguće voditi prodavnicu.\n"
        "1|ENG: Andon Labs built the AI and they named it Luna on Claude and gave her one direction, turn a profit. | SRB: Andon Labs je izgradio AI i nazvali ga Luna na Claude-u, a ona je dobila jednu instrukciju: postići profit.\n"
        "2|ENG: Within five minutes of turning on, she had posted job listings on LinkedIn, Indeed, and Craigslist, and even uploaded articles on incorporation to verify the business. | SRB: U pet minuta nakon uključivanja, ona je postavila oglase za zaposlenje na LinkedInu, Indeedu i Craigslistu, a i objavila članke u korporativnim medijima kako bi potvrdila legitimnost posla.\n"
        "3|ENG: And what's crazy is that Luna actually conducted interviews over Zoom with her camera off. | SRB: Najzanimljivije je da Luna zapravo provodila intervjuove putem Zooma s kamerom isključenom.\n"
        "4|ENG: They're doing it because they believe it's coming regardless, and they'd rather find out what could go wrong first. | SRB: Oni to radu zato što veruju da će to doći uvek, i da bi radnja preferirala da prvo saznaju šta može poći po zlu.\n"
        "Izlaz:\n"
        "0|Ova kompanija je dala Ej-Aj agentu sto hiljada dolara, kreditnu karticu i trogodišnji zakup lokala u San Francisku kako bi videli da li može da vodi prodavnicu.\n"
        "1|Andon Labs je kreirao ovaj Ej-Aj i nazvao ga Luna (zasnovan na Klodu), a dali su joj samo jedno uputstvo: da ostvari profit.\n"
        "2|U roku od pet minuta nakon uključivanja, ona je objavila oglase za posao na Linkedinu, Indidu i Kregzlistu, pa čak i podnela osnivačke akte kako bi registrovala firmu.\n"
        "3|A najluđe od svega je to što je Luna zapravo vodila intervjue preko Zuma sa isključenom kamerom.\n"
        "4|Rade to jer veruju da to svakako dolazi i radije bi da prvi saznaju šta sve može da pođe po zlu.\n\n"
        f"TEKST ZA LEKTURU:\n{lektor_input}"
    )



    
    try:
        lektor_payload = {
            "model": "qwen-lektor", # Model name is set in lektor_worker.py
            "messages": [{"role": "user", "content": lektor_prompt}],
            "temperature": 0.2,
            "max_tokens": 4096
        }
        
        url = f"{settings.MODAL_LEKTOR_URL.rstrip('/')}/v1/chat/completions"
        lektor_output = call_modal_endpoint(
            url=url,
            payload=lektor_payload,
            timeout_seconds=900,
            progress_callback=None
        )
        
        try:
            lektor_raw = lektor_output["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            lektor_raw = str(lektor_output)

        print(f"[DEBUG] LEKTOR OUTPUT: {lektor_raw[:500]}...", flush=True)
        
        parsed_lektor = []
        for line in lektor_raw.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 1)
            if len(parts) == 2:
                text = parts[1].strip()
                if text:
                    parsed_lektor.append(text)
                    
        if len(parsed_lektor) > 0:
            for i, seg in enumerate(translated_segments):
                seg["text"] = parsed_lektor[i] if i < len(parsed_lektor) else seg["text"]
                
    except Exception as lektor_err:
        print(f"[WARNING] Lektor faza nije uspela: {lektor_err}. Nastavljam sa grubim prevodom.")
        
    return {"status": "success", "translated_segments": translated_segments}
