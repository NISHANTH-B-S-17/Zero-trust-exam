import pytest
import os
import sys
import time
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from app.main import app
from app.security import crypto, t5
from app.forensic import watermark, tracer
from app.psychometrics import fairness, irt
from app.services import telemetry, audit

# Start client with lifespan context to initialize DB
@pytest.fixture
def test_client():
    with TestClient(app) as client:
        yield client

# 1. health endpoint works
def test_health_endpoint(test_client):
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# 2. SQLite initializes / 5. student authentication works for seeded student
def test_student_authentication(test_client):
    response = test_client.post("/api/v1/student/authenticate", json={"identifier": "demo-uuid-1234"})
    assert response.status_code == 200
    assert response.json()["status"] == "authenticated"

# 3. AES-GCM encrypt/decrypt round trip
def test_aes_gcm_round_trip():
    master_key = crypto.generate_master_key()
    plaintext = b"Secret Data"
    envelope = crypto.encrypt_payload(plaintext, master_key)
    decrypted = crypto.decrypt_payload(envelope, master_key)
    assert decrypted == plaintext

# 4. tampered ciphertext fails
def test_tampered_ciphertext_fails():
    master_key = crypto.generate_master_key()
    envelope = bytearray(crypto.encrypt_payload(b"Data", master_key))
    envelope[-1] ^= 0x01
    with pytest.raises(ValueError):
        crypto.decrypt_payload(bytes(envelope), master_key)

# 6. fetch-paper returns questions but no answer keys
def test_fetch_paper_no_answer_keys(test_client):
    response = test_client.get("/api/v1/student/fetch-paper?student_uuid=demo-uuid-1234")
    assert response.status_code == 200
    paper = response.json()["paper"]
    assert len(paper) > 0
    for q in paper:
        assert "correct_answer" not in q
        assert "correct_answer_encrypted" not in q

# 7. generated papers pass fairness validation
def test_generated_papers_fairness():
    q1 = {"id": 1, "irt_difficulty": 0.5, "marks": 1, "estimated_time_seconds": 60}
    q2 = {"id": 2, "irt_difficulty": 0.6, "marks": 1, "estimated_time_seconds": 60}
    form_a = [q1, q2]
    form_b = [q2, q1]
    
    report = fairness.FormEquivalenceValidator.validate_equivalence(form_a, form_b)
    assert report["is_fair"] is True

# 8. ZWSP encode/decode works
def test_zwsp_encode_decode():
    import hashlib
    uuid_val = "123e4567-e89b-12d3-a456-426614174000"
    md5_val = hashlib.md5(uuid_val.encode()).hexdigest()
    encoded = watermark.encode_uuid_zwsp(uuid_val)
    decoded = watermark.decode_uuid_zwsp(f"Hello{encoded}World")
    assert decoded == md5_val

# 9. synonym watermark is deterministic
def test_synonym_deterministic():
    text = "Please determine the velocity."
    uid = "demo-uuid"
    res1 = watermark.apply_synonym_swap(text, uid, "1")
    res2 = watermark.apply_synonym_swap(text, uid, "1")
    assert res1 == res2

# 10. ambiguous leak does not force a guilty result
def test_ambiguous_leak_trace():
    res = tracer.trace_leak("A generic leak with no watermark.")
    assert res["likely_source_session"] is None
    assert "investigation lead" in res["note"]

# 11. heartbeat records telemetry
def test_heartbeat_telemetry(test_client):
    payload = {
        "student_uuid": "demo-uuid-1234", "session_id": "sess-1",
        "active_question_id": 1, "responses": {}, "time_remaining": 3600
    }
    response = test_client.post("/api/v1/student/heartbeat", json=payload)
    assert response.status_code == 200

# 12. security event severity works
def test_security_event_severity(test_client):
    assert telemetry.evaluate_incident_severity("heartbeat", "") == "LOW"
    assert telemetry.evaluate_incident_severity("clipboard_attempt", "") == "HIGH"
    
    payload = {
        "student_uuid": "demo-uuid-1234", "session_id": "sess-1",
        "event_type": "clipboard_attempt", "detail": "Copied text"
    }
    response = test_client.post("/api/v1/student/log-security-event", json=payload)
    assert response.status_code == 200
    assert response.json()["severity"] == "HIGH"

# 13. audit signature verifies
def test_audit_signature_verifies():
    entry = "123456789|demo-uuid|TEST|INFO|Detail"
    sig = audit.sign_audit_entry(entry, "secret")
    log = {"timestamp": "123456789", "student_uuid": "demo-uuid", "event_type": "TEST", "severity": "INFO", "detail": "Detail", "signature": sig}
    assert audit.verify_audit_signature(log, "secret") is True

# 14. submission returns receipt hash
def test_submission_receipt(test_client):
    # Ensure paper is generated first
    test_client.get("/api/v1/student/fetch-paper?student_uuid=demo-uuid-1234")
    
    payload = {"student_uuid": "demo-uuid-1234", "answers": {"1": "11"}}
    response = test_client.post("/api/v1/student/submit", json=payload)
    assert response.status_code == 200
    assert "receipt_hash" in response.json()

# 15. Unauthorized admin request is rejected
def test_unauthorized_admin_rejected(test_client):
    # Missing header
    response = test_client.get("/api/v1/admin/dashboard")
    assert response.status_code == 422 # FastAPI missing header validation
    
    # Invalid header
    response = test_client.get("/api/v1/admin/dashboard", headers={"x-admin-token": "invalid-token"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin token"

# 16. Sensitive secrets are not returned in API responses
def test_no_sensitive_secrets_in_responses(test_client):
    response = test_client.get("/api/v1/student/fetch-paper?student_uuid=demo-uuid-1234")
    paper_str = str(response.json())
    # Should not contain master keys or explicit token files
    assert "admin_token" not in paper_str.lower()
    assert "master_key" not in paper_str.lower()

# 17. No duplicate questions in one paper
def test_no_duplicate_questions(test_client):
    response = test_client.get("/api/v1/student/fetch-paper?student_uuid=demo-uuid-1234")
    paper = response.json()["paper"]
    question_ids = [q["id"] for q in paper]
    assert len(question_ids) == len(set(question_ids))

# 18. OpenAPI Schema loads
def test_openapi_schema_loads(test_client):
    response = test_client.get("/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()
