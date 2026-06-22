import os
import uuid
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient

# Onemogućavamo slowapi limiter pre uvoza ruta
from backend.core.limiter import limiter
limiter.enabled = False  # noqa: E402

from backend.main import app  # noqa: E402
from backend.core.database import get_db  # noqa: E402
from backend.worker.translation.qe import get_llm_judge_score  # noqa: E402

# -------------------------------------------------------------------------
# 1. Testovi za LLM Judge (Llama 3.1 8B na Modalu)
# -------------------------------------------------------------------------

@patch("backend.worker.translation.qe.call_modal_endpoint")
def test_get_llm_judge_score_success(mock_call):
    # Postavljamo lažne parametre u okruženje
    with patch.dict(os.environ, {"MODAL_JUDGE_URL": "https://modal-judge.run"}):
        # Mock-ovanje odgovora sa vLLM endpoint-a (Llama 8B)
        mock_call.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"score": 4.8, "explanation": "Prevod je prirodan i tačan.", "errors": []}'
                    }
                }
            ]
        }
        
        result = get_llm_judge_score("Hello world", "Zdravo svete", limit_char=50)
        
        assert result["score"] == 4.8
        assert "prirodan" in result["explanation"]
        assert len(result["errors"]) == 0
        mock_call.assert_called_once()


@patch("backend.worker.translation.qe.call_modal_endpoint")
def test_get_llm_judge_score_error(mock_call):
    with patch.dict(os.environ, {"MODAL_JUDGE_URL": "https://modal-judge.run"}):
        # Simuliramo grešku na endpoint-u
        mock_call.side_effect = Exception("Veza je prekinuta")
        
        result = get_llm_judge_score("Hello world", "Zdravo svete")
        
        # Treba da vrati fallback rezultat sa score=5.0 bez pucanja
        assert result["score"] == 5.0
        assert "Greška sudije" in result["explanation"]
        assert len(result["errors"]) == 0


# -------------------------------------------------------------------------
# 2. Testovi za paralelnu validaciju u translate_segments
# -------------------------------------------------------------------------

@patch("backend.worker.translation.translate.get_llm_judge_score")
@patch("backend.worker.translation.translate.get_comet_kiwi_score")
@patch("backend.worker.translator.call_modal_endpoint")
@patch("backend.worker.translator.generate_video_summary")
@patch("backend.worker.translator.get_dynamic_glossary")
@patch("backend.core.database.SessionLocal")
@patch("redis.Redis.from_url")
def test_translate_segments_parallel_validation(
    mock_redis_from_url,
    mock_session_local,
    mock_get_glossary,
    mock_get_summary,
    mock_call_modal,
    mock_kiwi,
    mock_judge
):
    from backend.worker.translation.translate import translate_segments

    # Mock-ovanje baze podataka da sprečimo OperationalError
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    # Mock za Project u bazi
    mock_project = MagicMock()
    mock_project.user_id = "1"
    mock_db.query().filter().first.return_value = mock_project
    mock_db.query().filter().all.return_value = [] # Prazan TM i Wiki rules

    # Mock-ovanje Redis-a za active_lora_path
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis_from_url.return_value = mock_redis

    # Mock-ovanje CometKiwi skora: prvi segment je dobar, drugi je sumnjiv i zahteva sudiju
    mock_kiwi.side_effect = [0.95, 0.75]
    
    # Mock-ovanje LLM sudije za sumnjivi segment
    mock_judge.return_value = {
        "score": 4.5,
        "explanation": "Dobar prevod nakon suđenja.",
        "errors": []
    }
    
    # Mock za sažetak i glosar
    mock_get_summary.return_value = "Mockovani sažetak videa."
    mock_get_glossary.return_value = "hello -> zdravo"

    # Mock-ovanje Lektor LLM poziva za sam prevod. Pošto su segmenti razdvojeni velikom pauzom,
    # biće grupisani u dve odvojene rečenice (id 0 i id 1).
    mock_call_modal.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"translations": [{"id": 0, "translated_text": "Zdravo svete"}, {"id": 1, "translated_text": "Kako si"}]}'
                }
            }
        ]
    }
    
    # Prvi segment se završava tačkom da se grupa prekine
    segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "text": "Hello world.", "voice_type": "clone"},
        {"id": 1, "start": 22.0, "end": 24.0, "text": "How are you", "voice_type": "clone"}
    ]
    
    # Pozivamo prevođenje sa skip_lektor=True
    result = translate_segments(segments, skip_lektor=True, project_id=str(uuid.uuid4()))
    
    # Provera rezultata
    assert result["status"] == "success"
    translated = result["translated_segments"]
    assert len(translated) == 2
    assert translated[0]["text"] == "Zdravo svete"
    assert translated[1]["text"] == "Kako si"
    
    # Provera da li su evaluacije pozvane
    assert mock_kiwi.call_count == 2
    mock_judge.assert_called_once()  # Samo drugi (sumnjivi) segment ide na suđenje


# -------------------------------------------------------------------------
# 3. Testovi za WebSocket i Redis Pub/Sub status rute
# -------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("backend.routes.websocket.get_ws_user")
@patch("backend.routes.websocket.aioredis.from_url")
async def test_websocket_endpoint(mock_redis_from_url, mock_get_user):
    # Mock-ovanje korisnika
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.email = "test@sinhronizuj.me"
    mock_get_user.return_value = mock_user

    # Mock-ovanje baze i modela
    mock_db = MagicMock()
    mock_project = MagicMock()
    mock_project.id = "proj-123"
    mock_project.user_id = 1
    
    # Konfigurišemo mock_db.query da vrati projekat kad se filtrira
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_project
    mock_db.query.return_value = mock_query

    # Mock-ovanje asinhronog Redis klijenta i Pub/Sub-a
    mock_pubsub = AsyncMock()
    future_msg_1 = {
        "type": "message",
        "pattern": None,
        "channel": "project:proj-123:progress",
        "data": '{"progress": 45, "phase": "translation"}'
    }
    
    # Konfigurišemo get_message da vrati poruku pa podigne TimeoutError
    mock_pubsub.get_message.side_effect = [
        future_msg_1,
        asyncio.TimeoutError("Timeout"),
        asyncio.TimeoutError("Timeout")
    ]
    
    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub
    mock_redis_from_url.return_value = mock_redis

    # Overujemo get_db dependency u FastAPI aplikaciji sa ispravnim ključem get_db
    def override_get_db():
        yield mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Da bismo testirali WebSocket sa TestClient-om
    client = TestClient(app)
    
    with client.websocket_connect("/api/v1/ws/project/proj-123?token=valid-jwt-token") as websocket:
        # 1. Čitamo inicijalnu poruku o uspešnoj pretplati
        data = websocket.receive_json()
        assert data["status"] == "connected"
        assert "uspešna" in data["message"]
        
        # 2. Čitamo prvu Pub/Sub poruku koja je prosleđena sa Redisa
        data_progress = websocket.receive_json()
        assert data_progress["progress"] == 45
        assert data_progress["phase"] == "translation"
        
        # Zatvaramo konekciju ručno
        websocket.close()

    # Čistimo dependency overrides
    app.dependency_overrides.clear()
