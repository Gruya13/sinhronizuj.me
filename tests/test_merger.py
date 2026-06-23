from unittest.mock import patch, MagicMock
from backend.worker.merger import merge_audio_and_video_dynamic

@patch("backend.worker.merger.subprocess.run")
@patch("backend.worker.merger.get_video_duration")
def test_merge_audio_and_video_dynamic_success(mock_duration, mock_run):
    # Mock video duration na 10.0s
    mock_duration.return_value = 10.0
    
    # Mock-ujemo subprocess.run da vrati uspeh (returncode=0)
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_run.return_value = mock_res
    
    # Definišemo tts segmente sa različitim govornicima (npr. clone_0, clone_1)
    tts_segments = [
        {
            "id": 1,
            "start": 1.0,
            "end": 3.0,
            "duration": 2.5, # TTS je duži od originala (2.0s), pa treba da rastegne video
            "path": "dummy_tts_1.wav",
            "bg_volume": -2.0
        },
        {
            "id": 2,
            "start": 5.0,
            "end": 8.0,
            "duration": 3.0, # TTS je iste dužine (3.0s), nema rastezanja
            "path": "dummy_tts_2.wav",
            "bg_volume": 0.0
        }
    ]
    
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        
        res = merge_audio_and_video_dynamic(
            video_path="dummy_video.mp4",
            background_path="dummy_background.wav",
            tts_segments=tts_segments,
            background_vol=-5.0,
            dubbed_vol=2.0,
            workspace_path="/tmp"
        )
        
        assert res["status"] == "success"
        assert "final_video_path" in res
        assert "dubbed_audio_path" in res
        assert "speech_speedups" in res
        
        # Proveravamo speech speedups faktore za segmente
        # Segment 1: orig_duration = 2.0s, tts_duration = 2.5s
        # factor = 2.5 / 2.0 = 1.25. max_video_stretch = 1.05
        # video_stretch = min(1.05, 1.25) = 1.05
        # audio_speedup = 1.25 / 1.05 = 1.190476...
        # Segment 2: factor = 1.0 => video_stretch = 1.0, audio_speedup = 1.0
        assert res["speech_speedups"][1] > 1.0
        assert res["speech_speedups"][2] == 1.0
        
        # Proveravamo da li je FFmpeg pozvan sa očekivanim filter_complex
        assert mock_run.call_count == 2
        called_args = mock_run.call_args[0][0]
        
        # Treba da ima -filter_complex u komandi
        assert "-filter_complex" in called_args
        
        # Proveravamo da li se filter_complex referiše na rubberband filter za audio rastezanje i sidechaincompress
        filter_str = called_args[called_args.index("-filter_complex") + 1]
        assert "sidechaincompress" in filter_str
        assert "amix" in filter_str
        assert "concat" in filter_str
