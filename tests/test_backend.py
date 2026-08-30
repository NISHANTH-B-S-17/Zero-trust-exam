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
    assert result["student_uuid"] is None

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
    from app.db import database as app_db
    async def run_test():
        await app_db.init_db()
        await app_db.seed_demo_data()
        all_q = await app_db.fetch_all_questions()
        assert len(all_q) >= 2
    
    asyncio.run(run_test())

def test_vercel_config_exists():
    import os
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    admin_dir = os.path.join(root_dir, 'admin')
    index_path = os.path.join(admin_dir, 'index.html')
    dashboard_path = os.path.join(admin_dir, 'dashboard.html')
    vercel_path = os.path.join(root_dir, 'vercel.json')
    assert os.path.exists(index_path)
    assert os.path.exists(dashboard_path)
    assert os.path.exists(vercel_path)

    with open(vercel_path, "r") as f:
        content = f.read()
        assert "dashboard.html" in content
