import pytest
import os
import sys
import time

# Add the backend directory to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import crypto
import steganography
import t5_unlock
import ai_gen
import database
from main import evaluate_incident_severity

# --- crypto.py tests ---

def test_aes_gcm_round_trip():
    master_key = crypto.generate_master_key()
    plaintext = b"Secret Exam Content"
    
    envelope = crypto.encrypt_payload(plaintext, master_key)
    decrypted = crypto.decrypt_payload(envelope, master_key)
    
    assert decrypted == plaintext

def test_tampered_ciphertext_fails():
    master_key = crypto.generate_master_key()
    plaintext = b"Secret Exam Content"
    envelope = bytearray(crypto.encrypt_payload(plaintext, master_key))
    
    # Tamper with ciphertext (last byte)
    envelope[-1] ^= 0x01
    
    with pytest.raises(ValueError, match="Invalid payload: wrong key or tampered ciphertext"):
        crypto.decrypt_payload(bytes(envelope), master_key)

# --- steganography.py tests ---

def test_zwsp_uuid_encode_decode():
    original_uuid = "123e4567-e89b-12d3-a456-426614174000"
    encoded = steganography.encode_uuid_zwsp(original_uuid)
    
    # Wrap it in text
    text = f"Question text goes here.{encoded} And more text."
    
    decoded_uuid = steganography.decode_uuid_zwsp(text)
    assert decoded_uuid == original_uuid

def test_synonym_fallback_deterministic():
    uuid_1 = "123e4567-e89b-12d3-a456-426614174000"
    uuid_2 = "987e6543-e21b-12d3-a456-426614174999"
    q_id = "42"
    
    text = "Please determine the value."
    
    # Same UUID should always get the same synonym
    res1 = steganography.apply_synonym_swap(text, uuid_1, q_id)
    res2 = steganography.apply_synonym_swap(text, uuid_1, q_id)
    assert res1 == res2
    
    # Different UUID might get different (or same, depending on hash modulo, but deterministic)
    res3 = steganography.apply_synonym_swap(text, uuid_2, q_id)
    # We just ensure it runs without error and replaces the word
    assert res1 != "Please determine the value." or res3 != "Please determine the value."

def test_ambiguous_leak_returns_none():
    leak = "This is a leaked question with no watermarks."
    result = steganography.trace_leak(leak, candidate_uuids=["uuid-1"])
    assert result["student_uuid"] is None
    assert result["method"] == "none"

# --- ai_gen.py tests ---

def test_irt_paper_assembly():
    questions = [
        {"id": 1, "topic": "A"}, {"id": 2, "topic": "B"},
        {"id": 3, "topic": "A"}, {"id": 4, "topic": "B"},
        {"id": 5, "topic": "C"}
    ]
    
    paper = ai_gen.assemble_balanced_paper(questions, "uuid-1", target_count=3)
    assert len(paper) == 3
    # Check deterministic behavior
    paper2 = ai_gen.assemble_balanced_paper(questions, "uuid-1", target_count=3)
    assert paper == paper2

# --- t5_unlock.py tests ---

def test_t5_window():
    now = int(time.time())
    start = now + 100 # Exam starts in 100s
    assert t5_unlock.is_within_t5_window(start, now) == True
    
    start_future = now + 600 # Starts in 10 mins (outside 5 min window)
    assert t5_unlock.is_within_t5_window(start_future, now) == False

# --- main.py tests ---

def test_incident_severity():
    assert evaluate_incident_severity("heartbeat", "") == "LOW"
    assert evaluate_incident_severity("clipboard_attempt", "") == "HIGH"
    assert evaluate_incident_severity("focus_loss", "") == "MEDIUM"

# --- database.py tests ---

def test_audit_signature():
    log = {
        "timestamp": 1234567890,
        "student_uuid": "user-1",
        "event_type": "TEST",
        "severity": "INFO",
        "detail": "Test detail",
        "signature": ""
    }
    
    # Generate valid signature
    entry_str = f"{log['timestamp']}|{log['student_uuid']}|{log['event_type']}|{log['severity']}|{log['detail']}"
    valid_sig = database.sign_audit_entry(entry_str)
    
    log["signature"] = valid_sig
    assert database.verify_audit_signature(log) == True
    
    log["detail"] = "Tampered detail"
    assert database.verify_audit_signature(log) == False
