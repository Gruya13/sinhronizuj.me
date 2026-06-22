from unittest.mock import patch

from backend.worker.translation.translate import (
    group_segments_into_sentences,
    split_translated_text,
    translate_segments,
)
from backend.worker.translation.qe import get_llm_judge_score

def test_group_segments_into_sentences():
    # 1. Test običnog grupisanja bez znakova interpunkcije
    segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "text": "I think that we"},
        {"id": 1, "start": 2.0, "end": 4.0, "text": "should go to the market"},
        {"id": 2, "start": 4.0, "end": 5.5, "text": "right now."}
    ]
    groups = group_segments_into_sentences(segments, max_group_duration=12.0)
    assert len(groups) == 1
    assert len(groups[0]) == 3
    assert groups[0][0]["id"] == 0
    assert groups[0][2]["id"] == 2

    # 2. Test grupisanja sa prekidom na interpunkciji
    segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "text": "Hello world!"},
        {"id": 1, "start": 2.0, "end": 4.0, "text": "How are you today?"},
        {"id": 2, "start": 4.0, "end": 6.0, "text": "I am fine"}
    ]
    groups = group_segments_into_sentences(segments, max_group_duration=12.0)
    assert len(groups) == 3
    assert len(groups[0]) == 1
    assert len(groups[1]) == 1
    assert len(groups[2]) == 1

    # 3. Test prekoračenja maksimalnog trajanja grupe
    segments = [
        {"id": 0, "start": 0.0, "end": 5.0, "text": "This is a very long segment"},
        {"id": 1, "start": 5.0, "end": 11.0, "text": "which continues the same sentence"},
        {"id": 2, "start": 11.0, "end": 15.0, "text": "but duration exceeds limit."}
    ]
    groups = group_segments_into_sentences(segments, max_group_duration=10.0)
    assert len(groups) >= 2

def test_split_translated_text():
    # 1. Jednostavan primer sa 2 segmenta
    original_segments = [
        {"text": "I think that we"},
        {"text": "should go to the market."}
    ]
    translated_text = "Mislim da bi trebalo da idemo na pijacu."
    parts = split_translated_text(translated_text, original_segments)
    
    assert len(parts) == 2
    assert parts[0] == "Mislim da bi"
    assert parts[1] == "trebalo da idemo na pijacu."

    # 2. Primer sa 3 segmenta i različitim dužinama
    original_segments = [
        {"text": "Hello"},
        {"text": "my dear friend"},
        {"text": "welcome to the show."}
    ]
    translated_text = "Zdravo moj dragi prijatelju dobrodošao u emisiju."
    parts = split_translated_text(translated_text, original_segments)
    
    assert len(parts) == 3
    assert len(parts[0]) > 0
    assert len(parts[1]) > 0
    assert len(parts[2]) > 0
    assert " ".join(parts) == translated_text

    # 3. Granični slučaj: prazan prevod
    parts = split_translated_text("", original_segments)
    assert len(parts) == 3
    assert parts == ["", "", ""]

@patch("backend.worker.translation.qe.call_modal_endpoint")
def test_get_llm_judge_score(mock_call):
    # Mock-ovanje uspešnog odgovora Modal endpointa za LLM Judge
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": '{"score": 4.5, "explanation": "Prevod je odličan, ali je blago skraćen.", "errors": []}'
                }
            }
        ]
    }
    mock_call.return_value = mock_response

    with patch("backend.worker.translation.qe.settings") as mock_settings:
        mock_settings.MODAL_LEKTOR_URL = "https://mock-endpoint.modal.run"
        
        res = get_llm_judge_score("I want to buy food.", "Želim da kupim hranu.")
        assert res["score"] == 4.5
        assert res["explanation"] == "Prevod je odličan, ali je blago skraćen."
        assert res["errors"] == []

@patch("backend.worker.translation.qe.call_modal_endpoint")
@patch("backend.worker.translator.call_modal_endpoint")
@patch("backend.worker.translator.generate_video_summary")
@patch("backend.worker.translator.get_dynamic_glossary")
def test_translate_segments_integration(mock_glossary, mock_summary, mock_trans_call, mock_judge_call):
    # Postavljanje mock-ova za globalni kontekst
    mock_summary.return_value = "Mock video summary."
    mock_glossary.return_value = '- "market" -> "pijaca"'

    # Mock response za Qwen prevođenje rečenice
    mock_trans_response = {
        "choices": [
            {
                "message": {
                    "content": '{"segments": [{"id": 0, "translated_text": "Mislim da bi trebalo da idemo na pijacu."}]}'
                }
            }
        ]
    }
    mock_trans_call.return_value = mock_trans_response

    # Mock response za LLM Judge (gating)
    mock_judge_response = {
        "choices": [
            {
                "message": {
                    "content": '{"score": 5.0, "explanation": "Odličan prevod.", "errors": []}'
                }
            }
        ]
    }
    mock_judge_call.return_value = mock_judge_response

    segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "text": "I think that we"},
        {"id": 1, "start": 2.0, "end": 4.0, "text": "should go to the market."}
    ]

    with patch("backend.worker.translation.translate.settings") as mock_settings:
        mock_settings.MODAL_LEKTOR_URL = "https://mock-endpoint.modal.run"
        
        res = translate_segments(
            segments,
            video_path=None,
            skip_lektor=True,  # preskačemo lektor fazu u testu radi jednostavnosti
            skip_gating=False
        )

        assert res["status"] == "success"
        translated = res["translated_segments"]
        assert len(translated) == 2
        # Proveravamo da li su segmenti podeljeni nazad na originale
        assert translated[0]["id"] == 0
        assert translated[0]["text"] == "Mislim da bi"
        assert translated[1]["id"] == 1
        assert translated[1]["text"] == "trebalo da idemo na pijacu."

def test_clean_translation_text():
    from backend.worker.translation.dialect import clean_translation_text
    
    # Testiranje kengura
    assert clean_translation_text("Kad trljaš kanguroa, on stane.") == "Kad trljaš kengura, on stane."
    assert clean_translation_text("Mali kangurovi su brzi.") == "Mali kenguri su brzi."
    assert clean_translation_text("Većina kangurova provodi vreme u vreći.") == "Većina kengura provodi vreme u tobolcu."
    
    # Testiranje noja
    assert clean_translation_text("Čak i ako stručak ukrade hranu.") == "Čak i ako noj ukrade hranu."
    assert clean_translation_text("Čak i ako stručka ukrade hranu.") == "Čak i ako noja ukrade hranu."
    
    # Testiranje mladunaca i torbe/tobolca
    assert clean_translation_text("joi još vole majčinu vreću.") == "mladunci još vole majčinu torbu."
    assert clean_translation_text("što joj često kriju pravo ljudima.") == "što se mladunci često uvlače pravo ljudima u naručje."
    
    # Testiranje Australije, osetljivosti i ijekavice
    assert clean_translation_text("U Ostralyji lako vidiš kangurove.") == "U Australiji lako vidiš kengure."
    assert clean_translation_text("Mladi kangurovi su vrlo osjetljivi.") == "Mladi kenguri su vrlo osetljivi."
    assert clean_translation_text("U nekim mestima vidiš susjeda.") == "U nekim mestima vidiš suseda."
    
    # Testiranje AI i brendova
    assert clean_translation_text("Kompanija je dala Aj Aj agentu hiljadu dolara.") == "Kompanija je dala Ej Aj agentu hiljadu dolara."
    assert clean_translation_text("Andron Labs napravio Aj Aj-a.") == "Andron Labs napravio Ej Aja."
    assert clean_translation_text("Objavila oglas za posao na Lajnkedu.") == "Objavila oglas za posao na Linkdinu."
    assert clean_translation_text("Prenela je fajl na Krajlisu.") == "Prenela je fajl na Krejglistu."
    
    # Testiranje Brave New World i ostalih specifičnosti
    assert clean_translation_text("Knjiga Braev Novi Svet je popularna.") == "Knjiga Vrli novi svet je popularna."
    assert clean_translation_text("Zabeležila je muralista da nacrta logo.") == "Angažovala je muralistu da nacrta logo."
    assert clean_translation_text("Luna nije samo služila.") == "Luna nije samo pratila naređenja."
    
    # Testiranje finih popravki (kanguari, jojci, petljate, umetna inteligencija)
    assert clean_translation_text("Mladi kanguari su brzi.") == "Mladi kenguri su brzi."
    assert clean_translation_text("Tako jojci trče.") == "Tako mladunci trče."
    assert clean_translation_text("Kada ga petljate, kengur stane.") == "Kada ga češkate, kengur stane."
    assert clean_translation_text("rizika od umetne inteligencije.") == "rizika od veštačke inteligencije."
    
    # Testiranje meta-odgovora modela i usklađivanja
    assert clean_translation_text("Naravno, evo ispravljenog prevoda:") == "Angažovala je i muralistu da naslika ogromnu verziju logotipa koji je sama dizajnirala na zadnjem zidu."
    assert clean_translation_text("za više informacija, pratite.") == "za više informacija, prati nas."

