import uuid
from unittest.mock import patch, MagicMock
from starlette.requests import Request
from backend.worker.lipsync import apply_lip_sync, apply_selective_lip_sync

# Isključujemo slowapi limiter pre uvoza ruta
from backend.core.limiter import limiter
limiter.enabled = False  # noqa: E402


# -------------------------------------------------------------------------
# Testovi za FastAPI rute (Asinhroni TTS)
# -------------------------------------------------------------------------

@patch("backend.services.redis.get_redis_client")
@patch("backend.worker.tasks.generate_segment_tts_task")
@patch("backend.routes.segments.get_current_user")
def test_generate_segment_tts_route(mock_get_user, mock_task, mock_redis_client):
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_redis = MagicMock()
    mock_redis_client.return_value = mock_redis

    # Mock-ovanje Celery taska i delay metode
    mock_task_instance = MagicMock()
    mock_task_instance.id = "mock-task-id-123"
    mock_task.delay.return_value = mock_task_instance

    mock_db = MagicMock()
    mock_project = MagicMock()
    mock_project.id = uuid.uuid4()
    mock_project.user_id = 1
    
    mock_segment = MagicMock()
    mock_segment.segment_id = 1

    mock_db.query().filter().first.side_effect = [mock_project, mock_segment]

    from backend.routes.segments import generate_segment_tts, SegmentTTSRequest
    
    # Kreiramo pravi starlette Request
    scope = {
        "type": "http",
        "method": "POST",
        "path": f"/api/v1/project/{mock_project.id}/segment/1/tts",
        "headers": [],
    }
    req = Request(scope=scope)
    
    data = SegmentTTSRequest(
        text="Ovo je test sinteza.",
        voice_type="male",
        volume=1.0,
        speed=1.0,
        pitch=0.0,
        bg_volume=0.2
    )
    
    res = generate_segment_tts(
        request=req,
        project_id=str(mock_project.id),
        segment_id=1,
        data=data,
        current_user=mock_user,
        db=mock_db
    )
    
    assert res["status"] == "success"
    assert res["task_id"] == "mock-task-id-123"
    mock_task.delay.assert_called_once_with(
        str(mock_project.id),
        1,
        "Ovo je test sinteza.",
        "male",
        1.0,
        1.0,
        0.0,
        0.2
    )
    mock_redis.set.assert_called_once_with("task:mock-task-id-123:project_id", str(mock_project.id), ex=86400)


@patch("backend.services.redis.get_redis_client")
@patch("backend.worker.tasks.generate_all_tts_task")
@patch("backend.routes.segments.get_current_user")
def test_generate_all_tts_route(mock_get_user, mock_task, mock_redis_client):
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_redis = MagicMock()
    mock_redis_client.return_value = mock_redis

    # Mock-ovanje Celery taska i delay metode
    mock_task_instance = MagicMock()
    mock_task_instance.id = "mock-task-all-123"
    mock_task.delay.return_value = mock_task_instance

    mock_db = MagicMock()
    mock_project = MagicMock()
    mock_project.id = uuid.uuid4()
    mock_project.user_id = 1
    
    mock_segment = MagicMock()

    mock_db.query().filter().first.return_value = mock_project
    mock_db.query().filter().all.return_value = [mock_segment]

    from backend.routes.segments import generate_all_tts, GenerateAllTTSRequest
    
    scope = {
        "type": "http",
        "method": "POST",
        "path": f"/api/v1/project/{mock_project.id}/generate-all-tts",
        "headers": [],
    }
    req = Request(scope=scope)
    
    data = GenerateAllTTSRequest(voice_type="female")
    
    res = generate_all_tts(
        request=req,
        project_id=str(mock_project.id),
        data=data,
        current_user=mock_user,
        db=mock_db
    )
    
    assert res["status"] == "success"
    assert res["task_id"] == "mock-task-all-123"
    mock_task.delay.assert_called_once_with(
        str(mock_project.id),
        "female"
    )
    mock_redis.set.assert_called_once_with("task:mock-task-all-123:project_id", str(mock_project.id), ex=86400)

# -------------------------------------------------------------------------
# Testovi za lipsync.py (S3 integracija i pre-signed URL)
# -------------------------------------------------------------------------

@patch("backend.worker.lipsync.delete_file_from_s3")
@patch("backend.worker.lipsync.download_file_from_s3")
@patch("backend.worker.lipsync.upload_file_to_s3")
@patch("backend.worker.lipsync.get_presigned_upload_url")
@patch("backend.worker.lipsync.get_presigned_download_url")
@patch("backend.worker.utils.call_modal_endpoint")
@patch("os.getenv")
def test_apply_lip_sync_s3(mock_getenv, mock_call, mock_presign_down, mock_presign_up, mock_upload, mock_download, mock_delete):
    # Postavljamo da je Modal URL aktivan
    mock_getenv.side_effect = lambda key, default="": "https://modal-wav2lip.run" if key == "MODAL_WAV2LIP_URL" else default
    
    # Mock presigned URL-ove
    mock_presign_down.side_effect = lambda bucket, key, expires_in: f"https://s3.download/{key}"
    mock_presign_up.side_effect = lambda bucket, key, expires_in: f"https://s3.upload/{key}"
    
    mock_upload.return_value = True
    mock_download.return_value = True
    
    # Mock-ujemo uspešan odgovor Modal-a
    mock_call.return_value = {"status": "success"}

    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        
        res = apply_lip_sync(
            video_path="dummy_video.mp4",
            audio_path="dummy_audio.wav",
            workspace_path="/tmp"
        )
        
        assert res["status"] == "success"
        assert res["provider"] == "modal"
        
        # Proveravamo da li su uploadovani ulazi
        assert mock_upload.call_count == 2
        # Proveravamo da li je pozvan Modal sa URL-ovima
        mock_call.assert_called_once()
        called_payload = mock_call.call_args[0][1]
        assert "video_url" in called_payload
        assert "audio_url" in called_payload
        assert "result_upload_url" in called_payload
        
        # Proveravamo da li je preuzet rezultat
        mock_download.assert_called_once()
        # Proveravamo da li su obrisani S3 privremeni ključevi
        assert mock_delete.call_count == 3


@patch("backend.worker.lipsync.delete_file_from_s3")
@patch("backend.worker.lipsync.download_file_from_s3")
@patch("backend.worker.lipsync.upload_file_to_s3")
@patch("backend.worker.lipsync.get_presigned_upload_url")
@patch("backend.worker.lipsync.get_presigned_download_url")
@patch("backend.worker.utils.call_modal_endpoint")
@patch("backend.worker.lipsync.cv2.VideoCapture")
@patch("backend.worker.lipsync.subprocess.run")
@patch("os.getenv")
def test_apply_selective_lip_sync_s3(mock_getenv, mock_sub_run, mock_cap_class, mock_call, mock_presign_down, mock_presign_up, mock_upload, mock_download, mock_delete):
    # Postavljamo da je Modal URL aktivan
    mock_getenv.side_effect = lambda key, default="": "https://modal-wav2lip.run" if key == "MODAL_WAV2LIP_URL" else default
    
    # Mock OpenCV video
    mock_cap = MagicMock()
    mock_cap.get.side_effect = lambda prop: 30.0 if prop == 5 else 300 # fps=30, frames=300 => 10s
    mock_cap_class.return_value = mock_cap
    
    # Mock FFmpeg subprocess
    mock_sub_run.return_value = MagicMock(returncode=0)
    
    mock_presign_down.side_effect = lambda bucket, key, expires_in: f"https://s3.download/{key}"
    mock_presign_up.side_effect = lambda bucket, key, expires_in: f"https://s3.upload/{key}"
    
    mock_upload.return_value = True
    mock_download.return_value = True
    mock_call.return_value = {"status": "success"}
    
    # Definišemo segmente - jedan aktivan, jedan neaktivan
    segments = [
        {"start": 0.0, "end": 2.0, "active_speaker": True},
        {"start": 2.0, "end": 5.0, "active_speaker": False}
    ]
    
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        
        res = apply_selective_lip_sync(
            video_path="dummy_video.mp4",
            audio_path="dummy_audio.wav",
            segments=segments,
            workspace_path="/tmp"
        )
        
        assert res["status"] == "success"
        assert res["provider"] == "modal"
        
        # Proveravamo da li su uploadovani pod-fajlovi za aktivni segment na S3
        assert mock_upload.call_count == 2 # 1 video i 1 audio
        # Proveravamo da li je pozvan Modal za aktivni segment
        mock_call.assert_called_once()
        called_payload = mock_call.call_args[0][1]
        assert "video_url" in called_payload
        assert "audio_url" in called_payload
        assert "result_upload_url" in called_payload
        
        # Preuzet je samo 1 rezultat za aktivni segment
        mock_download.assert_called_once()
        # Obrisani su svi privremeni S3 ključevi (ulazni video, ulazni audio, izlazni video)
        assert mock_delete.call_count == 3
