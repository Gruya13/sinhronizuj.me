import torch
import torchaudio
import torchaudio.functional as F
import os

def detect_gender_from_audio(audio_path: str, start_time: float = None, end_time: float = None) -> str:
    """
    Učitava audio fajl (ili deo fajla) i određuje rod govornika (male/female)
    na osnovu fundamentalne frekvencije (pitch/F0).
    Lokalno, brzo, besplatno.
    """
    if not audio_path or not os.path.exists(audio_path):
        print(f"[GENDER DETECTION] Audio fajl ne postoji: {audio_path}")
        return "male"

    try:
        # Učitavanje celog fajla ili samo određenog vremenskog segmenta
        if start_time is not None and end_time is not None:
            # torchaudio.info nam daje metapodatke
            info = torchaudio.info(audio_path)
            sr = info.sample_rate
            
            # Računanje frejmova za učitavanje
            frame_offset = int(start_time * sr)
            num_frames = int((end_time - start_time) * sr)
            
            waveform, sample_rate = torchaudio.load(
                audio_path,
                frame_offset=frame_offset,
                num_frames=num_frames
            )
        else:
            waveform, sample_rate = torchaudio.load(audio_path)

        if waveform.numel() == 0:
            return "male"

        # Pretvaranje u mono ako je stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # Resemplovanje na 16kHz radi bržeg i stabilnijeg pitch tracking-a ako je veći sr
        if sample_rate > 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            waveform = resampler(waveform)
            sample_rate = 16000

        # Detekcija pitch frekvencije pomoću YIN / NCCF algoritma
        # detect_pitch_frequency vraća frekvenciju za svaki prozor
        pitch = F.detect_pitch_frequency(waveform, sample_rate)
        
        # Filtriranje nula (tišina/nevojsirani delovi) i nerealno visokih/niskih frekvencija za ljudski glas
        # Ljudski glas je obično u opsegu 60Hz - 400Hz
        valid_pitch = pitch[(pitch > 60.0) & (pitch < 400.0)]

        if valid_pitch.numel() == 0:
            print(f"[GENDER DETECTION] Nema detektovanog govora u audio segmentu. Koristim default: male")
            return "male"

        # Koristimo medijanu jer je robusnija na šum i anomalije od aritmetičke sredine
        median_pitch = torch.median(valid_pitch).item()
        
        # Klasifikacija:
        # Prosečni muški glas: 85 - 180 Hz (medijana obično oko 110-120 Hz)
        # Prosečni ženski glas: 165 - 255 Hz (medijana obično oko 200-210 Hz)
        # Prag od 160 Hz je standardna granica
        gender = "female" if median_pitch >= 160.0 else "male"
        
        print(f"[GENDER DETECTION] Detektovan median pitch: {median_pitch:.1f} Hz -> Rod: {gender.upper()}")
        return gender

    except Exception as e:
        print(f"[GENDER DETECTION ERROR] Greška pri detekciji roda: {e}")
        return "male"
