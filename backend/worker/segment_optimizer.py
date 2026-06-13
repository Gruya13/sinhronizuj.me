import re

def optimize_segments_for_translation(segments: list, min_duration: float = 1.0, max_duration: float = 6.0) -> list:
    """
    Optimizuje spisak segmenata pre prevođenja:
    1. Spaja mikro-segmente (< min_duration) rekurzivno sa susednim.
    2. Deli preduge segmente (> max_duration) na logičkim pauzama/interpunkciji.
    """
    if not segments:
        return []

    # Korak 1: Spajanje prekratkih segmenata
    merged = []
    buffer = []
    
    for seg in segments:
        duration = seg["end"] - seg["start"]
        if duration < min_duration:
            buffer.append(seg)
            # Ako buffer spajanjem pređe min_duration, formiramo segment i praznimo buffer
            buffer_duration = buffer[-1]["end"] - buffer[0]["start"]
            if buffer_duration >= min_duration:
                merged.append(merge_segment_list(buffer))
                buffer = []
        else:
            if buffer:
                # Ako već imamo nešto u bufferu, spajamo i to sa trenutnim dužim segmentom
                buffer.append(seg)
                merged.append(merge_segment_list(buffer))
                buffer = []
            else:
                merged.append(seg)
                
    if buffer:
        if merged:
            # Preostali kratki segmenti na kraju se pripajaju poslednjem spojenom
            last = merged.pop()
            buffer.insert(0, last)
            merged.append(merge_segment_list(buffer))
        else:
            merged.append(merge_segment_list(buffer))

    # Korak 2: Podela predugih segmenata
    final_segments = []
    for seg in merged:
        final_segments.extend(split_on_punctuation(seg, max_duration))

    # Re-indeksiranje segmenata od 0
    for idx, seg in enumerate(final_segments):
        seg["id"] = idx

    return final_segments

def merge_segment_list(segment_list: list) -> dict:
    """
    Spaja listu segmenata u jedan jedinstveni segment.
    """
    if not segment_list:
        return {}
    return {
        "start": segment_list[0]["start"],
        "end": segment_list[-1]["end"],
        "text": " ".join([s["text"].strip() for s in segment_list if s.get("text")])
    }

def split_on_punctuation(seg: dict, max_duration: float = 6.0) -> list:
    """
    Deli predugačak segment na logičkim pauzama/interpunkciji.
    """
    duration = seg["end"] - seg["start"]
    if duration <= max_duration:
        return [seg]
        
    text = seg["text"].strip()
    # Regex split koji zadržava interpunkciju
    parts = re.split(r'([.,?!;])', text)
    
    sentences = []
    current = ""
    for p in parts:
        if p is None:
            continue
        if p in ".,?!;":
            current += p
            sentences.append(current.strip())
            current = ""
        else:
            if current:
                sentences.append(current.strip())
            current = p
            
    if current.strip():
        sentences.append(current.strip())
        
    # Čišćenje praznih rečenica
    sentences = [s for s in sentences if s]

    if len(sentences) <= 1:
        # Nema znakova interpunkcije, delimo na pola po rečima
        words = text.split()
        if len(words) <= 4:
            return [seg]
        mid = len(words) // 2
        sentences = [" ".join(words[:mid]), " ".join(words[mid:])]

    # Proporcionalni proračun trajanja
    total_len = sum(len(s) for s in sentences)
    if total_len == 0:
        return [seg]

    result = []
    current_start = seg["start"]
    for s in sentences:
        s_len = len(s)
        s_dur = duration * (s_len / total_len)
        result.append({
            "start": round(current_start, 2),
            "end": round(current_start + s_dur, 2),
            "text": s
        })
        current_start += s_dur

    # Rekurzivno proveravamo ako je neki podsegment i dalje predugačak
    final_result = []
    for r in result:
        final_result.extend(split_on_punctuation(r, max_duration))
        
    return final_result
