import pytest
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import pytest
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.main import app

@pytest.fixture(autouse=True)
def init_test_db():
    with TestClient(app) as test_client:
        yield test_client

client = TestClient(app)
def test_placeholder():
    pass

def test_admin_dashboard_auth():
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/admin/dashboard")
        assert response.status_code == 422 # FastAPI validation error for missing header
        
        response = test_client.get("/api/v1/admin/dashboard", headers={"x-admin-token": "invalid"})
        assert response.status_code == 403

def test_health_endpoint():
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200

def test_openapi_schema_loads():
    with TestClient(app) as test_client:
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema

def test_student_fetch_paper_no_secrets():
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/student/fetch-paper?student_uuid=demo-uuid-1234")
        if response.status_code == 200:
            paper = response.json().get("paper", {})
            qs = paper.get("questions", []) if isinstance(paper, dict) else paper
            for q in qs:
                assert "correct_answer" not in q
                assert "answer_key" not in q
                assert "raw_answer" not in q
                assert "secret" not in q
                assert "encryption_key" not in q

def test_kiosk_full_student_flow():
    with TestClient(app) as test_client:
        auth_resp = test_client.post("/api/v1/student/authenticate", json={"roll_number": "ROLL001"})
        assert auth_resp.status_code == 200
        auth_data = auth_resp.json()
        assert auth_data["ok"] is True
        student_uuid = auth_data["student_uuid"]
        assert student_uuid == "demo-uuid-1234"

        fetch_get_resp = test_client.get(f"/api/v1/student/fetch-paper?student_uuid={student_uuid}")
        assert fetch_get_resp.status_code == 200
        fetch_get_data = fetch_get_resp.json()
        assert fetch_get_data["ok"] is True
        assert "paper" in fetch_get_data
        assert "questions" in fetch_get_data

        fetch_post_resp = test_client.post("/api/v1/student/fetch-paper", json={"student_uuid": student_uuid})
        assert fetch_post_resp.status_code == 200
        fetch_post_data = fetch_post_resp.json()
        assert fetch_post_data["ok"] is True

        heartbeat_resp = test_client.post("/api/v1/student/heartbeat", json={
            "student_uuid": student_uuid,
            "active_question_id": 1,
            "responses": {"1": "W = nRT ln(V2/V1)"},
            "remaining_seconds": 3500,
            "status": "active"
        })
        assert heartbeat_resp.status_code == 200
        assert heartbeat_resp.json()["ok"] is True

        sec_resp = test_client.post("/api/v1/student/log-security-event", json={
            "student_uuid": student_uuid,
            "type": "clipboard_attempt_copy",
            "question_idx": 0
        })
        assert sec_resp.status_code == 200
        assert sec_resp.json()["ok"] is True

        submit_resp = test_client.post("/api/v1/student/submit", json={
            "student_uuid": student_uuid,
            "responses": {"1": "W = nRT ln(V2/V1)"},
            "remaining_seconds": 3400,
            "auto_submit": False
        })
        assert submit_resp.status_code == 200
        submit_data = submit_resp.json()
        assert submit_data["ok"] is True
        assert "receipt_hash" in submit_data
        assert "score" in submit_data
        assert "correct" in submit_data
        assert "total" in submit_data

def test_forensic_endpoint_safe_language():
    with TestClient(app) as test_client:
        from app.core.config import settings
        headers = {"x-admin-token": settings.ADMIN_TOKEN}
        payload = {"leaked_text": "Determine the work done in an isothermal expansion"}
        
        response = test_client.post("/api/v1/admin/forensic/trace", headers=headers, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        lead = data.get("forensic_investigation_lead", "").lower()
        
        assert "investigation lead" in lead or "likely source" in lead
        assert "guilty" not in lead

# --- Staff Security Tests ---

def test_staff_security_endpoint():
    with TestClient(app) as test_client:
        from app.core.config import settings
        headers = {"x-admin-token": settings.ADMIN_TOKEN}
        
        response = test_client.get("/api/v1/admin/staff-security", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "roles_overview" in data
        assert "reviewer_assignments" in data
        assert "risk_alerts" in data
        assert "blocked_actions" in data
        assert "staff_audit_trail" in data
        assert "policy_status" in data
        
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
    assert staff.can_view_question("REVIEWER", 2, 99, assigned_question_ids=[1, 2]) is False
    assert staff.can_view_question("REVIEWER", 2, 1, assigned_question_ids=[1, 2]) is True
    assert staff.can_view_question("QUESTION_CREATOR", 1, 99) is False
    assert staff.can_view_question("SECURITY_ADMIN", 4, 1) is False

