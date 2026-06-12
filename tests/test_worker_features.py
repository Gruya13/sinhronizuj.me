import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
import torch
import numpy as np
import cv2

from backend.worker.audio_gender import detect_gender_from_audio
from backend.worker.active_speaker import is_speaker_active_on_screen
from backend.worker.lipsync import apply_selective_lip_sync

# --- TESTOVI ZA AUDIO GENDER DETEKCIJU ---
@patch("os.path.exists")
@patch("backend.worker.audio_gender.torchaudio")
def test_detect_gender_female(mock_torchaudio, mock_exists):
    mock_exists.return_value = True
    
    # Mock-ujemo torchaudio.info
    mock_meta = MagicMock()
    mock_meta.sample_rate = 16000
    mock_torchaudio.info.return_value = mock_meta
    
    # Mock-ujemo torchaudio.load
    mock_waveform = torch.ones(1, 16000)
    mock_torchaudio.load.return_value = (mock_waveform, 16000)
    
    # Mock-ujemo F (torchaudio.functional)
    with patch("backend.worker.audio_gender.F") as mock_F:
        mock_F.detect_pitch_frequency.return_value = torch.full((1, 100), 200.0)
        
        gender = detect_gender_from_audio("fake_path.wav", 0.0, 1.0)
        assert gender == "female"

@patch("os.path.exists")
@patch("backend.worker.audio_gender.torchaudio")
def test_detect_gender_male(mock_torchaudio, mock_exists):
    mock_exists.return_value = True
    
    mock_meta = MagicMock()
    mock_meta.sample_rate = 16000
    mock_torchaudio.info.return_value = mock_meta
    
    mock_waveform = torch.ones(1, 16000)
    mock_torchaudio.load.return_value = (mock_waveform, 16000)
    
    # Mock-ujemo pitch na 110 Hz
    with patch("backend.worker.audio_gender.F") as mock_F:
        mock_F.detect_pitch_frequency.return_value = torch.full((1, 100), 110.0)
        
        gender = detect_gender_from_audio("fake_path.wav", 0.0, 1.0)
        assert gender == "male"


# --- TESTOVI ZA DETEKCIJU AKTIVNOG GOVORNIKA (FaceMesh) ---
@patch("os.path.exists")
@patch("cv2.VideoCapture")
@patch("backend.worker.active_speaker.mp")
def test_is_speaker_active_on_screen(mock_mp, mock_video_capture, mock_exists):
    mock_exists.return_value = True
    
    # Mock-ujemo OpenCV VideoCapture
    mock_cap = MagicMock()
    mock_cap.get.side_effect = lambda prop: {
        cv2.CAP_PROP_FRAME_COUNT: 100,
        cv2.CAP_PROP_FPS: 25.0
    }.get(prop, 0.0)
    mock_cap.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))
    mock_video_capture.return_value = mock_cap
    
    # Mock-ujemo MediaPipe FaceMesh
    mock_face_mesh_inst = MagicMock()
    mock_mp.solutions.face_mesh.FaceMesh.return_value = mock_face_mesh_inst
    
    mock_results = MagicMock()
    
    # Kreiramo fiktivne landmarke (tačke 13, 14, 78, 308)
    landmark_13 = MagicMock(x=0.5, y=0.48)
    landmark_14 = MagicMock(x=0.5, y=0.52)
    landmark_78 = MagicMock(x=0.45, y=0.5)
    landmark_308 = MagicMock(x=0.55, y=0.5)
    
    landmarks = [MagicMock() for _ in range(468)]
    landmarks[13] = landmark_13
    landmarks[14] = landmark_14
    landmarks[78] = landmark_78
    landmarks[308] = landmark_308
    
    face_landmarks = MagicMock()
    face_landmarks.landmark = landmarks
    mock_results.multi_face_landmarks = [face_landmarks]
    mock_face_mesh_inst.process.return_value = mock_results
    
    # Pozivamo funkciju (očekujemo False jer nema pomeranja usta kroz frejmove)
    is_active = is_speaker_active_on_screen("fake_video.mp4", 0.0, 1.0)
    assert is_active == False


# --- TEST ZA SELEKTIVNI LIP-SYNC ---
@patch("os.path.exists")
@patch("os.path.getsize")
@patch("os.remove")
@patch("backend.worker.lipsync.cv2.VideoCapture")
@patch("subprocess.run")
def test_apply_selective_lip_sync(mock_sub_run, mock_video_capture, mock_remove, mock_getsize, mock_exists):
    mock_exists.side_effect = lambda path: True
    mock_getsize.return_value = 100
    
    # Mock-ujemo OpenCV VideoCapture za dužinu videa
    mock_cap = MagicMock()
    mock_cap.get.side_effect = lambda prop: {
        cv2.CAP_PROP_FRAME_COUNT: 250,
        cv2.CAP_PROP_FPS: 25.0
    }.get(prop, 0.0)
    mock_video_capture.return_value = mock_cap
    
    # Mock-ujemo subprocess.run da uvek uspeva
    mock_sub_run.return_value = MagicMock(returncode=0)
    
    # Definišemo test segmente
    segments = [
        {"id": 0, "start": 1.0, "end": 3.0, "active_speaker": True},
        {"id": 1, "start": 4.0, "end": 6.0, "active_speaker": False}
    ]
    
    # Pozivamo selektivni LipSync
    with patch("os.path.abspath") as mock_abs:
        mock_abs.side_effect = lambda x: x
        with patch("builtins.open", mock_open()):
            res = apply_selective_lip_sync("video.mp4", "audio.wav", segments)
            assert res["status"] == "success"
            assert res["skipped"] is False
            assert "lipsync_video_path" in res
            
            # Proveravamo da li je Wav2Lip pozvan tačno jednom (samo za segment 0)
            wav2lip_calls = 0
            for call in mock_sub_run.call_args_list:
                cmd = call[0][0]
                if "inference.py" in cmd[1]:
                    wav2lip_calls += 1
            assert wav2lip_calls == 1
