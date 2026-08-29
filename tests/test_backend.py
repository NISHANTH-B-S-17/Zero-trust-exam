import pytest
import os
import sys
import time

# Add the backend directory to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import crypto
import steganography
import t5_unlock
from app.exam.generator import FairExamFormGenerator
import database
from main import evaluate_insider_risk, app
from fastapi.testclient import TestClient

# ... existing code

# --- main.py tests ---

def test_incident_severity():
    assert evaluate_insider_risk("uuid-1", [{"type": "heartbeat"}]) == 0
    assert evaluate_insider_risk("uuid-1", [{"type": "clipboard_attempt"}]) == 25
    assert evaluate_insider_risk("uuid-1", [{"type": "focus_loss"}]) == 10

def test_fastapi_lifespan():
    pass

def test_tampered_ciphertext_fails():
    pass

# --- steganography.py tests ---

def test_zwsp_uuid_encode_decode():
    original_uuid = "123e4567-e89b-12d3-a456-426614174000"
    encoded = steganography.encode_uuid_zwsp(original_uuid)
    
    # Wrap it in text
    text = f"Question text goes here.{encoded} And more text."
    
    decoded_uuid = steganography.decode_uuid_zwsp(text)
    assert decoded_uuid == original_uuid

def test_ambiguous_leak_returns_none():
    leak = "This is a leaked question with no watermarks."
    result = steganography.trace_leak(leak)
    assert result["layer1_uuid"] is None

# --- generator.py tests ---

def test_irt_paper_assembly():
    questions = [
        {"id": 1, "topic": "A"}, {"id": 2, "topic": "B"},
        {"id": 3, "topic": "A"}, {"id": 4, "topic": "B"},
        {"id": 5, "topic": "C"}
    ]
    
    paper = FairExamFormGenerator.generate_deterministic_paper(questions, "uuid-1", target_count=3)
    assert len(paper) == 3
    # Check deterministic behavior
    paper2 = FairExamFormGenerator.generate_deterministic_paper(questions, "uuid-1", target_count=3)
    assert paper == paper2

# --- t5_unlock.py tests ---

def test_t5_window():
    pass

# --- main.py tests ---

def test_incident_severity_duplicate():
    pass

def test_fastapi_lifespan_duplicate():
    pass

# --- database.py tests ---

def test_database_creation():
    import asyncio
    async def run_test():
        db = await database.get_db()
        assert db is not None
        await db.close()
    
    asyncio.run(run_test())

def test_firebase_config_exists():
    import os
    assert os.path.exists("firebase.json")
    assert os.path.exists(".firebaserc")
    
    with open("firebase.json", "r") as f:
        content = f.read()
        assert "admin" in content
        assert "dashboard.html" in content
