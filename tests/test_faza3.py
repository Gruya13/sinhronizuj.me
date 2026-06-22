import os
import uuid
from unittest.mock import patch, MagicMock

# Onemogućavamo slowapi limiter pre uvoza ruta
from backend.core.limiter import limiter
limiter.enabled = False  # noqa: E402

# Mock-ujemo get_embedding na nivou embedding_service da ne uvozi stvarni model
from backend.services.embedding import embedding_service  # noqa: E402
embedding_service.get_embedding = MagicMock(return_value=[0.1, 0.2, 0.3])

from backend.worker.tasks import learn_user_glossary_batch_task  # noqa: E402
from backend.routes.projects import save_project_draft  # noqa: E402

# -------------------------------------------------------------------------
# Testovi za save_project_draft (N+1 i Batch glosar)
# -------------------------------------------------------------------------

@patch("backend.routes.projects.get_project_draft")
@patch("backend.worker.tasks.learn_user_glossary_batch_task")
@patch("backend.routes.projects.Depends")
def test_save_project_draft_batch(mock_depends, mock_batch_task, mock_get_draft):
    # Mock-ovanje korisnika
    mock_user = MagicMock()
    mock_user.id = 1

    # Mock-ovanje baze
    mock_db = MagicMock()
    
    # Mock projekat i segmenti
    mock_project = MagicMock()
    mock_project.id = uuid.uuid4()
    mock_project.user_id = 1
    
    # Konfigurišemo db upit za projekat
    mock_db.query().filter().first.return_value = mock_project
    
    # Kreiramo 2 segmenta u bazi
    seg1 = MagicMock()
    seg1.segment_id = 0
    seg1.original = "Hello world"
    seg1.translated = "Zdravo svete"
    seg1.voice_type = "clone"
    
    seg2 = MagicMock()
    seg2.segment_id = 1
    seg2.original = "How are you"
    seg2.translated = "Kako si"
    seg2.voice_type = "clone"
    
    # Konfigurišemo db upit za sve segmente projekta (all)
    mock_db.query().filter().all.return_value = [seg1, seg2]

    # Pripremamo zahtev za čuvanje
    from backend.core.schemas import SaveProjectRequest, SegmentItem
    
    # Menjamo oba segmenta (oba prevoda)
    req_seg1 = SegmentItem(id=0, start=0.0, end=1.0, original="Hello world", translated="Zdravo narode", voice_type="clone")
    req_seg2 = SegmentItem(id=1, start=1.0, end=2.0, original="How are you", translated="Kako si danas", voice_type="clone")
    
    request_data = SaveProjectRequest(segments=[req_seg1, req_seg2])
    
    # Pozivamo funkciju
    res = save_project_draft(
        project_id=str(mock_project.id),
        request=request_data,
        current_user=mock_user,
        db=mock_db
    )
    
    assert res["status"] == "success"
    
    # Proveravamo da li su vrednosti segmenta ažurirane u memoriji
    assert seg1.translated == "Zdravo narode"
    assert seg2.translated == "Kako si danas"
    
    # Proveravamo da li je db.commit() pozvan
    mock_db.commit.assert_called_once()
    
    # Proveravamo da li je okrenut batch Celery task sa tačnim korekcijama
    mock_batch_task.delay.assert_called_once_with(
        str(mock_user.id),
        [
            {"original": "Hello world", "old_translated": "Zdravo svete", "new_translated": "Zdravo narode"},
            {"original": "How are you", "old_translated": "Kako si", "new_translated": "Kako si danas"}
        ]
    )

# -------------------------------------------------------------------------
# Test za learn_user_glossary_batch_task (Celery)
# -------------------------------------------------------------------------

@patch("backend.worker.utils.call_modal_endpoint")
@patch("backend.core.database.SessionLocal")
def test_learn_user_glossary_batch_task(mock_session_local, mock_call):
    # Postavljamo Lektor URL preko patch.dict
    with patch.dict(os.environ, {"MODAL_LEKTOR_URL": "https://modal-lektor.run"}):
        # Mock embedding
        embedding_service.get_embedding = MagicMock(return_value=[0.1, 0.2, 0.3])
        
        # Mock LLM response
        mock_call.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"welding machine": "aparat za zavarivanje"}'
                    }
                }
            ]
        }
        
        # Mock baze
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        
        # Konfigurišemo da glosar ne postoji od ranije
        mock_db.query().filter().first.return_value = None
        
        corrections = [
            {"original": "This is a welding machine.", "old_translated": "Ovo je mašina za varenje.", "new_translated": "Ovo je aparat za zavarivanje."}
        ]
        
        # Pokrećemo task
        learn_user_glossary_batch_task("1", corrections)
        
        # Proveravamo da li se pozvao Modal
        mock_call.assert_called_once()
        
        # Proveravamo da li su Glossary i TranslationMemory stavke dodate u bazu
        assert mock_db.add.call_count == 2
        
        # Proveravamo da li je pozvan commit
        mock_db.commit.assert_called_once()
