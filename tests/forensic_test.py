import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import steganography

def test_zwsp_exact_recovery():
    test_uuid = "a1b2c3d4-e5f6-7890-1234-567890abcdef"
    original_text = "What is the speed of light in a vacuum?"
    
    watermarked = steganography.apply_layer1(original_text, test_uuid)
    assert len(watermarked) > len(original_text)
    
    recovered_uuid = steganography.decode_uuid_zwsp(watermarked)
    assert recovered_uuid == test_uuid

def test_deterministic_synonym_watermarking():
    text = "Please determine and explain the equation. Calculate and identify the root. Analyze the result."
    candidate_uuid = "123e4567-e89b-12d3-a456-426614174000"
    
    res1 = steganography.apply_synonym_swap(text, candidate_uuid)
    res2 = steganography.apply_synonym_swap(text, candidate_uuid)
    
    assert res1 == res2 # Deterministic
    assert res1 != text # Changed from original
    # Casing preserved roughly since first letter is caps or lower
    assert res1[0].isupper() or text[0].isupper() 

def test_honeytoken_transformation():
    question = {
        "id": "q_99",
        "text": "Solve 2+2",
        "options": ["3", "4", "5", "6"]
    }
    candidate_uuid = "123e4567-e89b-12d3-a456-426614174000"
    
    transformed = steganography.apply_honeytoken(question, candidate_uuid)
    
    # Assert deterministic and options preserved but spaces added safely
    assert len(transformed["options"]) == 4
    assert any(opt.endswith(" ") for opt in transformed["options"])
    assert not any(opt.endswith(" ") for opt in question["options"])

def test_leak_tracing_outputs():
    # 1. ZWSP copy-paste
    test_uuid = "a1b2c3d4-e5f6-7890-1234-567890abcdef"
    zwsp_leak = steganography.apply_layer1("The leaked question.", test_uuid)
    
    res_zwsp = steganography.trace_leak(zwsp_leak)
    assert res_zwsp["method"] == "zwsp"
    assert res_zwsp["confidence"] >= 0.99
    assert res_zwsp["student_uuid"] == test_uuid
    assert "investigation lead" in res_zwsp["forensic_investigation_lead"].lower()
    assert "guilty" not in res_zwsp["forensic_investigation_lead"].lower() or "not confirmed guilty" in res_zwsp["forensic_investigation_lead"].lower()

    # 2. OCR/Synonym fallback
    # The text stripped of ZWSP
    synonym_leak = "Please find out and clarify the equation." # Synonyms for determine and explain
    res_synonym = steganography.trace_leak(synonym_leak, candidate_uuids=[test_uuid])
    
    assert res_synonym["method"] == "synonym"
    assert res_synonym["confidence"] < 0.99
    assert res_synonym["confidence"] > 0.0
    assert "likely source copy" in res_synonym["forensic_investigation_lead"].lower()
    
    # 3. Very short snippet
    res_short = steganography.trace_leak("The", candidate_uuids=[test_uuid])
    assert res_short["student_uuid"] is None
    assert res_short["confidence"] == 0.0