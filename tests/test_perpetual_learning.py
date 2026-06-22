import os
from unittest.mock import patch, MagicMock
from backend.core.models import TranslationMemory, PendingTranslationMemory, WikiRule, Segment, Project
from backend.worker.tasks import promote_pending_tm_task
from backend.worker.translation.pattern_miner import run_nightly_pattern_analysis
from backend.worker.training.data_generator import run_data_generation
from backend.worker.training.train_lora import run_lora_training

# ==========================================
# 1. TESTOVI ZA SUBAGENT ALPHA (Real-time TM)
# ==========================================

@patch("redis.Redis.from_url")
@patch("backend.worker.translator.call_modal_endpoint")
@patch("backend.worker.translator.generate_video_summary")
@patch("backend.worker.translator.get_dynamic_glossary")
@patch("backend.worker.translation.translate.get_comet_kiwi_score")
@patch("backend.worker.translator.lektor_segments")
@patch("backend.core.database.SessionLocal")
def test_alpha_real_time_tm_insertion(mock_db_session, mock_lektor, mock_qe_score, mock_glossary, mock_summary, mock_call_modal, mock_redis_from_url):
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db

    # Mock Redis klijent da spreči mrežne timeouts
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis_from_url.return_value = mock_redis

    # Postavljanje mock-ova za globalni kontekst
    mock_summary.return_value = "Mock video summary."
    mock_glossary.return_value = '- "exceptional" -> "izuzetan"'

    # Mock response za Qwen prevođenje
    mock_trans_response = {
        "choices": [
            {
                "message": {
                    "content": '{"segments": [{"id": 0, "translated_text": "Ovo je izuzetan prevod."}]}'
                }
            }
        ]
    }
    mock_call_modal.return_value = mock_trans_response

    # Mock Lektor izlaz
    mock_lektor.return_value = {
        "status": "success",
        "translated_segments": [
            {
                "id": 0,
                "original_text": "This is an exceptional translation.",
                "text": "Ovo je izuzetan prevod.",
                "confidence_score": 4.9
            },
            {
                "id": 1,
                "original_text": "This is a decent translation.",
                "text": "Ovo je pristojan prevod.",
                "confidence_score": 3.8
            }
        ]
    }

    # Prvi poziv (prevod seg 0) -> 0.95, drugi poziv (TM upis seg 0) -> 0.95, treći poziv (TM upis seg 1) -> 0.87
    mock_qe_score.side_effect = [0.95, 0.95, 0.87, 0.87]

    mock_project = MagicMock(spec=Project)
    mock_project.user_id = "mock-user-id"

    # Robustan SQLAlchemy mock lanac
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    # Prvi i drugi poziv za first() vraćaju mock_project, a ostali vraćaju None (nema duplog TM-a)
    mock_query.first.side_effect = [mock_project, mock_project, None, None]

    from backend.worker.translation.translate import translate_segments

    # Pokrećemo prevođenje sa postavljenim project_id
    with patch("backend.worker.translation.translate.settings") as mock_settings, \
         patch("backend.services.embedding.embedding_service") as mock_emb:
        mock_settings.MODAL_LEKTOR_URL = "https://mock-lektor.modal.run"
        mock_emb.get_embedding.return_value = [0.1] * 384

        res = translate_segments(
            [{"id": 0, "start": 0.0, "end": 2.0, "text": "This is an exceptional translation."}],
            video_path=None,
            project_id="mock-proj-id",
            skip_lektor=False,
            skip_gating=True
        )

        assert res["status"] == "success"

        # Proveravamo dodate objekte u bazu
        added_objects = [args[0] for args, kwargs in mock_db.add.call_args_list]
        
        # 1. Treba da bude direktan upis u TranslationMemory za QE > 0.92 i Conf > 4.5
        has_tm = any(
            isinstance(obj, TranslationMemory) and 
            obj.source_text == "This is an exceptional translation." and 
            obj.auto_approved == True 
            for obj in added_objects
        )
        assert has_tm

        # 2. Treba da bude upis u PendingTranslationMemory za QE > 0.85 i Conf > 3.5
        has_pending = any(
            isinstance(obj, PendingTranslationMemory) and 
            obj.source_text == "This is a decent translation." and 
            obj.occurrence_count == 1
            for obj in added_objects
        )
        assert has_pending

@patch("backend.core.database.SessionLocal")
def test_alpha_promote_pending_tm_task(mock_db_session):
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db

    # Kreiramo lažne grupisane rezultate gde je zbir occurrence_count >= 2
    mock_group = MagicMock()
    mock_group.user_id = "mock-user-id"
    mock_group.source_text = "Repeat translation."
    mock_group.target_text = "Ponovljeni prevod."
    mock_group.project_id = "mock-proj-id"
    mock_group.total_occurrence = 2

    # Robustan SQLAlchemy mock lanac za grupisanje i agregaciju
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.group_by.return_value = mock_query
    mock_query.having.return_value = mock_query
    mock_query.all.return_value = [mock_group]
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None # Nema u glavnoj TM

    with patch("backend.services.embedding.embedding_service") as mock_emb:
        mock_emb.get_embedding.return_value = [0.1] * 384
        
        res = promote_pending_tm_task()
        assert res["status"] == "success"
        assert res["promoted_count"] == 1

        # Provera da li je kreiran TranslationMemory objekat i obrisan iz Pending
        added_objects = [args[0] for args, kwargs in mock_db.add.call_args_list]
        has_tm = any(isinstance(obj, TranslationMemory) and obj.source_text == "Repeat translation." for obj in added_objects)
        assert has_tm
        assert mock_query.delete.called

# ==========================================
# 2. TESTOVI ZA SUBAGENT BETA (Lovac na Obrasce)
# ==========================================

@patch("backend.worker.translation.pattern_miner.call_modal_endpoint")
@patch("backend.worker.translation.pattern_miner.SessionLocal")
def test_beta_nightly_pattern_analysis(mock_db_session, mock_modal):
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db

    # 1. Kreiramo 5 loših segmenata sa sličnim tekstom
    bad_segs = []
    texts = [
        "This actually works.",
        "Actually, that is correct.",
        "It is actually fine.",
        "Actually, I don't know.",
        "That was actually bad."
    ]
    for i, txt in enumerate(texts):
        seg = MagicMock(spec=Segment)
        seg.original = txt
        seg.translated = f"Lokalno {i}"
        seg.qe_score = 0.75
        bad_segs.append(seg)

    # Robustan SQLAlchemy mock lanac za pretragu loših segmenata
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = bad_segs
    mock_query.first.return_value = None # Nema duplikata pravila

    # Mock response od Qwen za predlog pravila
    mock_modal.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"rule_text": "Prevedi reč actually kao zapravo ili u stvari.", "category": "style"}'
                }
            }
        ]
    }

    with patch("backend.worker.translation.pattern_miner.settings") as mock_settings, \
         patch("backend.worker.translation.pattern_miner.embedding_service") as mock_emb:
        mock_settings.MODAL_TRANSLATOR_URL = "https://mock-translator.modal.run"
        # Dajemo svima slične embeddinge da bi DBSCAN formirao klaster
        mock_emb.get_embedding.side_effect = [[0.9, 0.1, 0.0] for _ in range(5)]

        res = run_nightly_pattern_analysis()
        assert res["status"] == "success"
        assert res["new_rules_added"] == 1

        # Provera da li je pravilo snimljeno u bazu
        added_objects = [args[0] for args, kwargs in mock_db.add.call_args_list]
        has_rule = any(isinstance(obj, WikiRule) and obj.is_global == True and "actually" in obj.content for obj in added_objects)
        assert has_rule

# ==========================================
# 3. TESTOVI ZA SUBAGENT GAMA (LoRA Fine-Tuner)
# ==========================================

@patch("backend.worker.training.data_generator.generate_paraphrases")
@patch("backend.worker.training.data_generator.SessionLocal")
def test_gamma_data_generator(mock_db_session, mock_para):
    mock_db = MagicMock()
    mock_db_session.return_value = mock_db

    # Mock zlatni segmenti
    seg = MagicMock(spec=Segment)
    seg.original = "Golden sentence."
    seg.translated = "Zlatna rečenica."
    seg.qe_score = 0.96
    seg.confidence_score = 4.8
    seg.status = "draft"

    # Robustan SQLAlchemy mock lanac za izvlačenje zlatnih segmenata
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [seg]

    mock_para.return_value = ["Zlatna rečenica 1.", "Zlatna rečenica 2.", "Zlatna rečenica 3."]

    res = run_data_generation()
    assert res["status"] == "success"
    assert res["examples_generated"] > 0
    assert os.path.exists(res["output_path"])

    # Čistimo fajl posle testa
    if os.path.exists(res["output_path"]):
        os.remove(res["output_path"])

@patch("backend.worker.training.train_lora.modal.Function.from_name")
def test_gamma_train_lora_local_dry_run(mock_modal_from_name):
    # Mock-ujemo da modal baci grešku kako bismo odmah prešli na lokalni dry-run bez timeout-a
    mock_modal_from_name.side_effect = Exception("Mocked modal connection error")

    # Pokrećemo lokalni dry run za trening i proveravamo da li uspešno generiše adaptere
    res = run_lora_training(dry_run=True)
    assert res["status"] == "success"
    assert "adapter_dir" in res
    assert os.path.exists(res["adapter_dir"])
    assert os.path.exists(os.path.join(res["adapter_dir"], "adapter_config.json"))

    # Čistimo privremene fajlove
    import shutil
    if os.path.exists(res["adapter_dir"]):
        shutil.rmtree(res["adapter_dir"])

# ==========================================
# 4. TESTOVI ZA CELERY PARALELIZACIJU
# ==========================================

def test_celery_chunking_logic_on_silence():
    # Simuliramo transkript i proveravamo split markere na bazi tišine
    optimized_segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "text": "Sentence 1."},
        {"id": 1, "start": 2.1, "end": 4.0, "text": "Sentence 2."},
        {"id": 2, "start": 6.5, "end": 8.0, "text": "Sentence 3."}, # Velika pauza od 2.5 sekunde između 1 i 2 (blizu 1/3)
        {"id": 3, "start": 8.1, "end": 10.0, "text": "Sentence 4."},
        {"id": 4, "start": 13.0, "end": 15.0, "text": "Sentence 5."}, # Velika pauza od 3.0 sekunde između 3 i 4 (blizu 2/3)
        {"id": 5, "start": 15.1, "end": 17.0, "text": "Sentence 6."}
    ]

    start_time = optimized_segments[0]["start"]
    end_time = optimized_segments[-1]["end"]
    total_duration = end_time - start_time

    t1 = start_time + total_duration / 3.0 # ~5.66s
    t2 = start_time + 2.0 * total_duration / 3.0 # ~11.33s
    w = total_duration / 6.0 # ~2.83s

    best_i = -1
    max_gap1 = -1.0

    best_j = -1
    max_gap2 = -1.0

    for idx_s in range(len(optimized_segments) - 1):
        seg_end = optimized_segments[idx_s]["end"]
        next_start = optimized_segments[idx_s+1]["start"]
        gap = next_start - seg_end

        if t1 - w <= seg_end <= t1 + w:
            if gap > max_gap1:
                max_gap1 = gap
                best_i = idx_s

        if t2 - w <= seg_end <= t2 + w:
            if gap > max_gap2:
                max_gap2 = gap
                best_j = idx_s

    # Provera da li su prepoznati splitovi oko segmenata sa najvećim pauzama
    assert best_i == 1  # Razmak posle id=1 (2.1-4.0) i pre id=2 (6.5-8.0) je 2.5s
    assert best_j == 3  # Razmak posle id=3 (8.1-10.0) i pre id=4 (13.0-15.0) je 3.0s
