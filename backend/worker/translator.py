"""
Fasada za prevodilački servis.
Uvozi i eksponira sve javne funkcije iz paketa backend.worker.translation
radi unazadne kompatibilnosti sa ostatkom aplikacije i testovima.
"""

from backend.worker.utils import call_modal_endpoint
from backend.worker.translation import (
    mask_untranslatable,
    unmask_text,
    mask_segment_pair,
    to_latin,
    TO_LATIN_REPLACEMENTS,
    clean_translation_text,
    clean_thought_tags,
    load_glossaries,
    detect_topic_and_terms,
    get_dynamic_glossary,
    generate_video_summary,
    semantic_similarity,
    get_comet_kiwi_score,
    check_negation_preservation,
    translate_segments,
    retranslate_with_self_critique,
    lektor_segments,
    calculate_jaccard_similarity,
    get_llm_judge_score,
    extract_video_frames,
)
