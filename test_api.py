import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_forensic_scan_rejects_empty_payload():
    """
    Regression test: The API should actively reject empty leak_text inputs
    with an HTTP 400 Bad Request error.
    """
    response = client.post("/api/v1/admin/forensic-scan", json={"leak_text": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "Empty leak_text provided"

def test_forensic_scan_accepts_valid_payload():
    """
    Sanity check: Valid payload should succeed and return forensic data.
    """
    response = client.post("/api/v1/admin/forensic-scan", json={"leak_text": "Here is the leaked exam material."})
    assert response.status_code == 200
    assert response.json()["status"] == "matched"

def test_t5_ceremony_rejects_missing_keys():
    """
    Test that T-5 ceremony rejects empty keys.
    """
    response = client.post("/api/v1/admin/t5-ceremony", json={"key_a": "", "key_b": ""})
    assert response.status_code == 400
    assert "Missing required cryptographic keys." in response.json()["detail"]

def test_t5_ceremony_accepts_keys():
    """
    Test that T-5 ceremony accepts valid keys.
    """
    response = client.post("/api/v1/admin/t5-ceremony", json={"key_a": "1234", "key_b": "5678"})
    assert response.status_code == 200
    assert response.json()["status"] == "unlocked"

def test_browser_devtools_fix_returns_204():
    """
    Regression test: The chrome devtools endpoint should return a safe 204 No Content
    instead of crashing Uvicorn with a content length mismatch.
    """
    response = client.get("/.well-known/appspecific/com.chrome.devtools.json")
    assert response.status_code == 204
    assert response.content == b''  # Must be strictly empty body
    
    response2 = client.get("/favicon.ico")
    assert response2.status_code == 204
    assert response2.content == b''
