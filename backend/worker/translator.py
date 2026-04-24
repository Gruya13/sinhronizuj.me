import json
import asyncio
import httpx
import re
from typing import List, Dict, Any
from backend.core.config import settings

# TOON Specifikacija: [ID] [START] [END] [TEXT]
TOON_HEADER = "# [START]\n# ID | START | END | ORIGINAL_TEXT\n"
TOON_FOOTER = "# [END]"

def to_toon(segments: List[Dict[str, Any]]) -> str:
    """Pretvara listu segmenata u TOON format (Token-Oriented Object Notation)."""
    lines = [TOON_HEADER]
    for idx, s in enumerate(segments):
        # Čistimo tekst od novih redova da ne pokvarimo tabelu
        text = s['text'].replace('\n', ' ').strip()
        lines.append(f"{idx} | {s['start']:.2f} | {s['end']:.2f} | {text}")
    lines.append(TOON_FOOTER)
    return "\n".join(lines)

def from_toon(toon_str: str, original_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parsira TOON odgovor i vraća listu prevedenih segmenata."""
    translated = []
    # Tražimo linije koje počinju brojem (ID)
    pattern = re.compile(r"^(\d+)\s*\|\s*[\d\.]+\s*\|\s*[\d\.]+\s*\|\s*(.*)$")
    
    lines = toon_str.strip().split('\n')
    translated_map = {}
    
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            idx = int(match.group(1))
            text = match.group(2).strip()
            translated_map[idx] = text

    # Spajamo sa originalnim segmentima da očuvamo metapodatke
    for i, orig in enumerate(original_segments):
        new_text = translated_map.get(i, orig['text'])
        translated.append({
            **orig,
            "text": new_text
        })
        
    return translated

async def runpod_generate(prompt: str, visual_context_url: str = None) -> str:
    """Šalje zahtev RunPod Serverless endpoint-u."""
    if not settings.RUNPOD_TRANSLATOR_ID:
        # Fallback na mock ako nema endpoint ID-a za testiranje
        print("[WARNING] RUNPOD_TRANSLATOR_ID nije definisan. Koristim mock.")
        return "0 | 0.00 | 0.00 | Prevedeni tekst (MOCK)"

    url = f"https://api.runpod.ai/v2/{settings.RUNPOD_TRANSLATOR_ID}/runsync"
    headers = {
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Qwen 32B Multimodal Prompt
    payload = {
        "input": {
            "prompt": prompt,
            "visual_context": visual_context_url,
            "max_new_tokens": 4096,
            "temperature": 0.2
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=600)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "COMPLETED":
            return result["output"]
        else:
            raise Exception(f"RunPod greška: {result}")

async def translate_chunk(chunk_segments: List[Dict[str, Any]], visual_context_url: str = None) -> List[Dict[str, Any]]:
    """Obrađuje jedan blok (chunk) segmenata."""
    toon_input = to_toon(chunk_segments)
    
    system_prompt = (
        "ZADATAK: Profesionalni prevodilac na SRPSKI jezik (LATINICA).\n"
        "FORMAT: Odgovori isključivo u TOON formatu. Ne menjaj ID-eve.\n"
        "STIL: Prirodan srpski, koristi š, ć, č, ž, đ. Ne prevodi brendove.\n"
        "INPUT TOON:\n"
    )
    
    full_prompt = f"{system_prompt}\n{toon_input}\n\nPREVEDI KOLONU ORIGINAL_TEXT:"
    
    try:
        toon_output = await runpod_generate(full_prompt, visual_context_url)
        return from_toon(toon_output, chunk_segments)
    except Exception as e:
        print(f"[ERROR] Greška u chunk-u: {e}")
        return chunk_segments # Fallback na original u slučaju totalne greške

async def translate_segments_async(segments: list, visual_context_url: str = None, chunk_size: int = 50) -> dict:
    """Glavna funkcija za paralelni prevod transkripta."""
    print(f"[TRANSLATOR V2] Pokrećem hibridni prevod ({len(segments)} segmenata)...")
    
    # Podela na chunkove
    chunks = [segments[i:i + chunk_size] for i in range(0, len(segments), chunk_size)]
    
    # Paralelno izvršavanje
    tasks = [translate_chunk(c, visual_context_url) for c in chunks]
    results = await asyncio.gather(*tasks)
    
    # Spajanje rezultata
    final_segments = []
    for r in results:
        final_segments.extend(r)
        
    return {
        "status": "success",
        "translated_segments": final_segments,
        "engine": "qwen-32b-serverless-toon"
    }

def translate_segments(segments: list, original_language: str = "en", progress_callback=None) -> dict:
    """Wrapper za sinhroni poziv iz Celery-ja."""
    return asyncio.run(translate_segments_async(segments))
