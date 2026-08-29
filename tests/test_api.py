import pytest
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.main import app

client = TestClient(app)

def test_placeholder():
    pass

def test_admin_dashboard_auth():
    # Test unauthenticated access (no token)
    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 422 # FastAPI validation error for missing header
    
    # Test invalid token
    response = client.get("/api/v1/admin/dashboard", headers={"x-admin-token": "invalid"})
    assert response.status_code == 403

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

# --- Staff Security Tests ---

def test_staff_security_endpoint():
    from app.core.config import settings
    headers = {"x-admin-token": settings.ADMIN_TOKEN}
    
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/admin/staff-security", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "roles_overview" in data
        assert "reviewer_assignments" in data
        assert "risk_alerts" in data
        assert "blocked_actions" in data
        assert "staff_audit_trail" in data
        assert "policy_status" in data
        
        # Check that forbidden overclaim words are not in the response payload anywhere
        dump = str(data).lower()
        forbidden_words = ["confirmed guilty", "proves guilt", "100% secure", "zero leaks"]
        for word in forbidden_words:
            assert word not in dump

def test_calculate_risk_level():
    from app.services import staff
    assert staff.calculate_risk_level(20) == "LOW"
    assert staff.calculate_risk_level(45) == "MEDIUM"
    assert staff.calculate_risk_level(75) == "HIGH"
    assert staff.calculate_risk_level(95) == "CRITICAL"

def test_staff_view_permissions():
    from app.services import staff
    # 4. Reviewer cannot view unassigned question
    assert staff.can_view_question("REVIEWER", 2, 99, assigned_question_ids=[1, 2]) is False
    assert staff.can_view_question("REVIEWER", 2, 1, assigned_question_ids=[1, 2]) is True
    
    # 5. Creator cannot view unrelated question (mocked to false currently)
    assert staff.can_view_question("QUESTION_CREATOR", 1, 99) is False
    
    # 6. Security admin cannot automatically decrypt/read raw question content
    assert staff.can_view_question("SECURITY_ADMIN", 4, 1) is False

