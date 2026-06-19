import pytest
import re
from unittest.mock import patch, MagicMock

from backend.worker.translator import (
    to_latin,
    clean_translation_text,
    lektor_segments,
    translate_segments,
    clean_thought_tags
)


# Testovi za Fazu 0.2: Regresija futura I sa "će"
def test_clean_translation_future():
    # Pomoćna funkcija da test liči na assert iz zahteva
    def clean(text):
        return clean_translation_text(text)
        
    assert clean("auto put će biti gotov") == "auto put će biti gotov"
    assert clean("internet će raditi") == "internet će raditi"
    assert clean("raditi će sutra") == "radiće sutra"
    assert clean("radit će sutra") == "radiće sutra"
    assert clean("sat će proći") == "sat će proći"
    assert clean("sajt će raditi") == "sajt će raditi"

# Testovi za Fazu 0.3: Padež meseca
def test_to_latin_month_case():
    assert to_latin("15. listopada") == "15. oktobra"
    assert to_latin("u listopadu") == "u oktobru"

# Testovi za Fazu 0.5: cijeli -> ceo i novi uopšteni ijekavizmi
def test_to_latin_cijeli():
    assert to_latin("cijeli svijet") == "ceo svet"
    assert to_latin("cijela kuća") == "cela kuća"
    assert to_latin("cijelo vrijeme") == "celo vreme"
    
    # Novi uopšteni ijekavizmi i regionalizmi
    assert to_latin("osjećaš li se dobro") == "osećaš li se dobro"
    assert to_latin("osjećam radost i osmijeh") == "osećam radost i osmeh"
    assert to_latin("smiješno i nasmiješeno") == "smešno i nasmešeno"
    assert to_latin("predloži rješenje problema") == "predloži rešenje problema"
    assert to_latin("promjena i primjena mjera") == "promena i primena mera"
    assert to_latin("smjer kretanja i vjera") == "smer kretanja i vera"
    assert to_latin("sljedeća riječ i sljedbenici") == "sledeća reč i sledbenici"
    assert to_latin("tijekom tjedna ili cijelog vijeka") == "tokom nedelje ili celog veka"
    assert to_latin("on je donio i htio") == "on je doneo i hteo"

# Testovi za Fazu 0.1: Leak Guard i ijekavski ulaz kroz ceo pipeline
@patch("backend.worker.translator.call_modal_endpoint")
@patch("backend.worker.translator.get_dynamic_glossary")
@patch("backend.worker.translator.generate_video_summary")
def test_pipeline_leak_guard(mock_summary, mock_glossary, mock_call_endpoint):
    mock_summary.return_value = "Mock summary"
    mock_glossary.return_value = "- \"welding\" -> \"zavarivanje\""
    
    mock_response_translator = {
        "choices": [
            {
                "message": {
                    "content": '{"segments": [{"id": 0, "translated_text": "Da bi spriječio deformaciju, primetićeš da dio gornjeg ruba viri."}]}'
                }
            }
        ]
    }
    mock_response_lektor = {
        "choices": [
            {
                "message": {
                    "content": '{"segments": [{"id": 0, "refined_text": "Da bi spriječio deformaciju, primetićeš da dio gornjeg ruba viri."}]}'
                }
            }
        ]
    }
    
    mock_call_endpoint.side_effect = [mock_response_translator, mock_response_lektor]
    
    segments = [
        {"id": 0, "start": 0.0, "end": 2.0, "text": "To prevent the structure from deforming, you will notice part of the upper edge sticks out."}
    ]
    
    with patch("backend.core.config.settings.MODAL_LEKTOR_URL", "http://fake-modal-endpoint"):
        res = translate_segments(segments)
        
    assert res["status"] == "success"
    translated = res["translated_segments"][0]["text"]
    
    LEAK_PATTERN = re.compile(
        r'\b(dio|dijel\w*|dvjesto|spriječi\w*|tijekom|sustav\w*|tjedan|tjedn\w*|'
        r'tisuć\w*|uvjet\w*|utjecaj\w*|sučelj\w*|zaslon\w*|tipkovnic\w*|poveznic\w*|'
        r'vidjeti|djeluj\w*|riješi\w*|uvijek|gdje)\b', re.IGNORECASE)
        
    assert not LEAK_PATTERN.search(translated), f"Dijalekat procurio: {translated}"
    assert "sprečio" in translated
    assert "deo" in translated

# Testovi za clean_thought_tags sa raznim kombinacijama
def test_clean_thought_tags():
    # Slučaj 1: Standardni zatvoreni tagovi
    text1 = "<think>razmišljanje</think>{\n  \"segments\": []\n}"
    assert clean_thought_tags(text1) == "{\n  \"segments\": []\n}"
    
    text2 = "<thought>razmišljanje</thought>{\n  \"segments\": []\n}"
    assert clean_thought_tags(text2) == "{\n  \"segments\": []\n}"
    
    # Slučaj 2: Nezatvoren tag na početku ali sa JSON-om posle
    text3 = "<think>razmišljanje bez kraja... {\n  \"segments\": []\n}"
    assert clean_thought_tags(text3) == "{\n  \"segments\": []\n}"
    
    text4 = "<thought>razmišljanje bez kraja... [\n  1, 2, 3\n]"
    assert clean_thought_tags(text4) == "[\n  1, 2, 3\n]"
    
    # Slučaj 3: Nezatvoren tag na kraju bez JSON-a posle
    text5 = "Ovo je prevod.<think>razmišljanje koje nije zatvoreno"
    assert clean_thought_tags(text5) == "Ovo je prevod."
    
    # Slučaj 4: Prazan ulaz
    assert clean_thought_tags("") == ""
    assert clean_thought_tags(None) == ""

