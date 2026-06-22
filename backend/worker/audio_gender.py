import torch
import torchaudio.functional as F
import os
import numpy as np
from pydub import AudioSegment

# Globalne promenljive za keširanje učitanog audia u memoriji
_cached_audio_path = None
_cached_audio_segment = None

def detect_gender_from_audio(audio_path: str, start_time: float = None, end_time: float = None) -> str:
    """
    Učitava audio fajl (ili deo fajla) i određuje rod govornika (male/female)
    na osnovu fundamentalne frekvencije (pitch/F0).
    Lokalno, brzo, besplatno.
    """
    global _cached_audio_path, _cached_audio_segment

    if not audio_path or not os.path.exists(audio_path):
        print(f"[GENDER DETECTION] Audio fajl ne postoji: {audio_path}")
        return "male"

    try:
        # Keširanje celog audia u memoriji radi performansi
        if _cached_audio_path == audio_path and _cached_audio_segment is not None:
            sound = _cached_audio_segment
        else:
            print(f"[GENDER DETECTION] Učitavam novi audio fajl u memoriju: {audio_path}", flush=True)
            sound = AudioSegment.from_file(audio_path)
            _cached_audio_path = audio_path
            _cached_audio_segment = sound
        
        # Sečemo segment iz memorije (ekstremno brzo)
        if start_time is not None and end_time is not None:
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            sound_segment = sound[start_ms:end_ms]
        else:
            sound_segment = sound

        sample_rate = sound_segment.frame_rate
        
        # Dobijamo uzorke kao numpy niz
        samples = np.array(sound_segment.get_array_of_samples(), dtype=np.float32)
        
        if len(samples) == 0:
            return "male"

        # Normalizacija amplitude na opseg [-1.0, 1.0]
        if sound_segment.sample_width == 2:
            samples = samples / 32768.0
        elif sound_segment.sample_width == 4:
            samples = samples / 2147483648.0
        elif sound_segment.sample_width == 1:
            samples = (samples - 128.0) / 128.0

        # Konvertujemo u mono ako je stereo
        if sound_segment.channels > 1:
            # pydub vraća isprepletene (interleaved) kanale za višekanalne audio zapise
            samples = samples.reshape(-1, sound_segment.channels)
            samples = np.mean(samples, axis=1)

        waveform = torch.from_numpy(samples).unsqueeze(0) # Oblik [1, num_samples]

        # Resemplovanje na 16kHz radi bržeg i stabilnijeg pitch tracking-a ako je veći sr
        if sample_rate > 16000:
            try:
                import torchaudio.transforms as T
                resampler = T.Resample(orig_freq=sample_rate, new_freq=16000)
                waveform = resampler(waveform)
                sample_rate = 16000
            except Exception as e:
                # Fallback ako transforms modul nije dostupan ili baci grešku
                print(f"[GENDER DETECTION] Resampling transforms greška: {e}", flush=True)

        # Detekcija pitch frekvencije pomoću YIN / NCCF algoritma
        pitch = F.detect_pitch_frequency(waveform, sample_rate)
        
        # Filtriranje ljudskog vokalnog opsega (60Hz - 400Hz)
        valid_pitch = pitch[(pitch > 60.0) & (pitch < 400.0)]

        if valid_pitch.numel() == 0:
            return "male"

        # Koristimo medijanu jer je robusnija na šum
        median_pitch = torch.median(valid_pitch).item()
        
        # Klasifikacija: prag od 160 Hz
        gender = "female" if median_pitch >= 160.0 else "male"
        
        print(f"[GENDER DETECTION] Segment {start_time:.2f}s-{end_time:.2f}s | Median pitch: {median_pitch:.1f} Hz -> Rod: {gender.upper()}", flush=True)
        return gender

    except Exception as e:
        print(f"[GENDER DETECTION ERROR] Greška pri detekciji roda: {e}", flush=True)
        return "male"

