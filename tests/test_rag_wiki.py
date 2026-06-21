import pytest
from unittest.mock import patch, MagicMock
from backend.services.embedding import embedding_service
from backend.core.models import TranslationMemory, WikiRule, User
from backend.routes.wiki import WikiRuleCreate, WikiRuleUpdate

# 1. Testiranje embedding servisa (kosinusna sličnost)
def test_embedding_service_cosine_similarity():
    # Test identičnih vektora
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    sim = embedding_service.calculate_cosine_similarity(vec1, vec2)
    assert pytest.approx(sim, 0.001) == 1.0

    # Test suprotnih vektora
    vec3 = [-1.0, 0.0, 0.0]
    sim = embedding_service.calculate_cosine_similarity(vec1, vec3)
    assert pytest.approx(sim, 0.001) == -1.0

    # Test ortogonalnih vektora
    vec4 = [0.0, 1.0, 0.0]
    sim = embedding_service.calculate_cosine_similarity(vec1, vec4)
    assert pytest.approx(sim, 0.001) == 0.0

    # Test praznih vektora
    assert embedding_service.calculate_cosine_similarity([], vec1) == 0.0

# 2. Testiranje RAG integracije u translate prompt
@patch("backend.worker.translation.translate.group_segments_into_sentences")
@patch("backend.worker.translator.call_modal_endpoint")
@patch("backend.worker.translator.generate_video_summary")
@patch("backend.worker.translator.get_dynamic_glossary")
@patch("backend.worker.translation.translate.settings")
@patch("backend.core.database.SessionLocal")
def test_translate_segments_rag_integration(mock_db_session, mock_settings, mock_get_glossary, mock_get_summary, mock_modal_call, mock_group):
    # Mock-ovanje baze podataka da vrati predefinisani TM i WikiRule
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db
    
    # Mock-ovanje funkcija za sažetak i glosar kako ne bi pozivale pravi Modal endpoint
    mock_get_summary.return_value = "Ovo je mockovani sažetak videa o konfiguraciji servera."
    mock_get_glossary.return_value = "server -> server\nconfigure -> konfigurisati"
    
    # Mock za Project
    mock_project = MagicMock()
    mock_project.user_id = "mock-user-id"
    mock_db.query().filter().first.return_value = mock_project
    
    # Mock za TranslationMemory
    mock_tm = MagicMock()
    mock_tm.id = "mock-tm-id"
    mock_tm.source_text = "I need to configure the server."
    mock_tm.target_text = "Moram da konfigurišem server."
    # Generišemo realan embedding za potrebe poređenja (384 dimenzije za paraphrase-multilingual model)
    mock_tm.embedding = embedding_service.get_embedding(mock_tm.source_text)
    
    # Mock za WikiRule
    mock_wiki = MagicMock()
    mock_wiki.title = "Stil programiranja"
    mock_wiki.content = "Koristi 'drajver' umesto 'upravljački program'."
    
    # Postavljanje povratnih vrednosti za queries
    mock_db.query().filter().all.side_effect = [
        [mock_tm],  # Prvi poziv za TranslationMemory
        [mock_wiki]  # Drugi poziv za WikiRule
    ]

    # Mock-ovanje prevođenja
    mock_group.return_value = [[{"id": 0, "start": 0.0, "end": 2.0, "text": "Please configure the server."}]]
    mock_settings.MODAL_LEKTOR_URL = "https://mock-lektor.modal.run"
    mock_modal_call.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"segments": [{"id": 0, "translated_text": "Molim vas konfigurišite server."}]}'
                }
            }
        ]
    }

    from backend.worker.translation.translate import translate_segments
    
    segments = [{"id": 0, "start": 0.0, "end": 2.0, "text": "Please configure the server."}]
    res = translate_segments(segments, project_id="mock-project-id", skip_lektor=True, skip_gating=True)

    assert res["status"] == "success"
    
    # Provera da li je model pretrage bio pozvan
    mock_modal_call.assert_called_once()
    payload = mock_modal_call.call_args[1]["payload"]
    system_prompt = payload["messages"][0]["content"]
    user_prompt = payload["messages"][1]["content"]

    # Provera da li su Wiki pravila ugrađena u sistemski prompt
    assert "DODATNA STILSKA I BREND PRAVILA (WIKI):" in system_prompt
    assert "Stil programiranja" in system_prompt
    assert "Koristi 'drajver'" in system_prompt

    # Provera da li su RAG primeri prepoznati i ugrađeni u korisnički prompt
    assert "PRETHODNI PREVODI IZ KORISNIČKE MEMORIJE (RAG):" in user_prompt
    assert "I need to configure the server." in user_prompt
    assert "Moram da konfigurišem server." in user_prompt

# 3. Testiranje feedback loop-a (learn_user_glossary_task)
@patch("backend.worker.utils.call_modal_endpoint")
@patch("backend.core.database.SessionLocal")
def test_learn_user_glossary_task_feedback_loop(mock_db_session, mock_modal_call):
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db
    
    # Mock LLM response za izvlačenje glosara
    mock_modal_call.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"welding machine": "aparat za zavarivanje"}'
                }
            }
        ]
    }
    
    # Mock provere postojanja u bazi
    mock_db.query().filter().first.return_value = None  # Pretvaramo se da nema postojećih zapisa
    
    from backend.worker.tasks import learn_user_glossary_task
    
    # Pokrećemo Celery zadatak direktno (sinhrono)
    learn_user_glossary_task(
        user_id="mock-user-id",
        original="I am using a new welding machine today.",
        old_translated="Danas koristim novu mašinu za varenje.",
        new_translated="Danas koristim novi aparat za zavarivanje."
    )
    
    # Proveravamo da li je dodan novi TranslationMemory objekat
    added_objects = [args[0] for args, kwargs in mock_db.add.call_args_list]
    has_tm = any(isinstance(obj, TranslationMemory) and obj.source_text == "I am using a new welding machine today." and obj.target_text == "Danas koristim novi aparat za zavarivanje." for obj in added_objects)
    assert has_tm, "Nije kreiran TranslationMemory objekat sa ispravnim podacima."
    # Proveravamo da li je izvršen commit
    mock_db.commit.assert_called_once()
