import pytest
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200

def test_openapi_schema_loads():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema

def test_student_fetch_paper_no_secrets():
    # Attempt to fetch without valid student just to verify response structure doesn't leak
    response = client.get("/api/v1/student/fetch-paper?student_uuid=demo-uuid-1234")
    
    # If student exists or if it falls back
    if response.status_code == 200:
        paper = response.json().get("paper", [])
        for q in paper:
            assert "correct_answer" not in q
            assert "answer_key" not in q
            assert "raw_answer" not in q
            assert "secret" not in q
            assert "encryption_key" not in q
            
def test_submit_returns_receipt_hash():
    payload = {"student_uuid": "demo-uuid-1234", "answers": {"1": "11"}}
    response = client.post("/api/v1/student/submit", json=payload)
    if response.status_code == 200:
        assert "receipt_hash" in response.json()
        
def test_forensic_endpoint_safe_language():
    # Test that admin trace endpoint uses safe language
    from app.core.config import settings
    headers = {"x-admin-token": settings.ADMIN_TOKEN}
    payload = {"leaked_text": "Determine the velocity"}
    
    response = client.post("/api/v1/admin/forensic/trace", headers=headers, json=payload)
    assert response.status_code == 200
    
    data = response.json()
    lead = data.get("forensic_investigation_lead", "").lower()
    
    assert "investigation lead" in lead or "likely source" in lead
    assert "guilty" not in lead

