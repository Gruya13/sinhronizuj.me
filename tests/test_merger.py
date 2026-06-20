import os
import pytest
from unittest.mock import MagicMock, patch

from backend.worker.merger import (
    merge_audio_and_video,
    merge_audio_and_video_dynamic,
    get_video_duration,
    speedup_audio_file
)

# --- 1. Test za statički merger sa ducking-om ---
@patch("backend.worker.merger.os.path.exists")
@patch("backend.worker.merger.os.remove")
@patch("backend.worker.merger.subprocess.run")
def test_merge_audio_and_video_ducking(mock_run, mock_remove, mock_exists):
    # Pretvaramo se da svi ulazni fajlovi postoje
    mock_exists.return_value = True
    
    # Mock-ujemo uspeh FFmpeg komandi
    mock_run.return_value = MagicMock(returncode=0)
    
    res = merge_audio_and_video(
        video_path="fake_video.mp4",
        background_path="fake_bg.wav",
        dubbed_path="fake_dub.wav",
        background_vol=-6.0,
        dubbed_vol=1.0,
        workspace_path="/tmp"
    )
    
    assert res["status"] == "success"
    assert "final_video_path" in res
    
    # Proveravamo da li je FFmpeg pozvan sa sidechaincompress filterom
    calls = mock_run.call_args_list
    assert len(calls) >= 2  # Prvi za postprocesiranje, drugi za miksanje
    
    # Proveravamo argumente druge FFmpeg komande (miksanje)
    mix_cmd = calls[1][0][0]
    assert "ffmpeg" in mix_cmd
    
    # Proveravamo da li filter_complex sadrži sidechaincompress i podešavanja glasnoće
    filter_complex_arg = ""
    for i, arg in enumerate(mix_cmd):
        if arg == "-filter_complex":
            filter_complex_arg = mix_cmd[i+1]
            break
            
    assert "sidechaincompress" in filter_complex_arg
    assert "volume=-6.0dB" in filter_complex_arg
    assert "volume=1.0dB" in filter_complex_arg


# --- 2. Test za koliziju segmenata u dinamičkom mergeru ---
@patch("backend.worker.merger.os.path.exists")
@patch("backend.worker.merger.os.remove")
@patch("backend.worker.merger.get_video_duration")
@patch("backend.worker.merger.subprocess.run")
@patch("backend.worker.merger.speedup_audio_file")
def test_merge_audio_and_video_dynamic_collision(mock_speedup, mock_run, mock_duration, mock_remove, mock_exists):
    mock_exists.return_value = True
    mock_duration.return_value = 10.0
    mock_run.return_value = MagicMock(returncode=0)
    mock_speedup.side_effect = lambda path, speed: f"{path}_speed.wav"
    
    # Definišemo koliziju: drugi segment počinje na 2.5s iako se prvi završava na 3.0s
    segments = [
        {"id": 0, "start": 1.0, "end": 3.0, "duration": 2.0, "path": "tts0.wav"},
        {"id": 1, "start": 2.5, "end": 4.5, "duration": 3.0, "path": "tts1.wav"}
    ]
    
    res = merge_audio_and_video_dynamic(
        video_path="fake_video.mp4",
        background_path="fake_bg.wav",
        tts_segments=segments,
        max_video_stretch=1.05,
        workspace_path="/tmp"
    )
    
    assert res["status"] == "success"
    
    # FFmpeg komanda za miksanje
    mix_cmd = mock_run.call_args_list[0][0][0]
    filter_complex_arg = ""
    for i, arg in enumerate(mix_cmd):
        if arg == "-filter_complex":
            filter_complex_arg = mix_cmd[i+1]
            break
            
    # Proveravamo da li su trimi izračunati sa ispravljenom kolizijom:
    # Segment 1 originalno trajanje: 3.0 - 1.0 = 2.0s
    # Segment 2 originalno trajanje zbog kolizije: 4.5 - 3.0 = 1.5s (jer se start pomera na 3.0s)
    assert "trim=start=0.0:end=1.0" in filter_complex_arg  # gap
    assert "trim=start=1.0:end=3.0" in filter_complex_arg  # seg 0
    assert "trim=start=3.0:end=4.5" in filter_complex_arg  # seg 1 (ispeglana kolizija: start=3.0 umesto 2.5)


# --- 3. Test za A/V sinhronizaciju i time-stretching ---
@patch("backend.worker.merger.os.path.exists")
@patch("backend.worker.merger.os.remove")
@patch("backend.worker.merger.get_video_duration")
@patch("backend.worker.merger.subprocess.run")
@patch("backend.worker.merger.speedup_audio_file")
def test_merge_audio_and_video_dynamic_av_sync(mock_speedup, mock_run, mock_duration, mock_remove, mock_exists):
    mock_exists.return_value = True
    mock_duration.return_value = 5.0
    mock_run.return_value = MagicMock(returncode=0)
    mock_speedup.side_effect = lambda path, speed: f"{path}_speed.wav"
    
    # Segment 0: orig_duration = 2.0s, tts_duration = 2.4s (factor = 1.20)
    # Pošto je max_video_stretch = 1.05:
    # video_stretch = 1.05
    # audio_speedup = 1.20 / 1.05 = 1.142857 (brzina zvuka se ubrzava da bi stigla rastegnuti video)
    segments = [
        {"id": 0, "start": 1.0, "end": 3.0, "duration": 2.4, "path": "tts0.wav"}
    ]
    
    res = merge_audio_and_video_dynamic(
        video_path="fake_video.mp4",
        background_path="fake_bg.wav",
        tts_segments=segments,
        max_video_stretch=1.05,
        workspace_path="/tmp"
    )
    
    assert res["status"] == "success"
    
    # Proveravamo da li je audio ubrzan za odgovarajući faktor
    mock_speedup.assert_called_once_with("tts0.wav", pytest.approx(1.142857, rel=1e-4))
    
    # Proveravamo filter complex za setpts video rastezanje (koje treba da bude 1.05)
    mix_cmd = mock_run.call_args_list[0][0][0]
    filter_complex_arg = ""
    for i, arg in enumerate(mix_cmd):
        if arg == "-filter_complex":
            filter_complex_arg = mix_cmd[i+1]
            break
            
    # Proveravamo setpts faktor rastezanja za video block 1 (Segment 0)
    assert "setpts=1.05*(PTS-STARTPTS)" in filter_complex_arg
