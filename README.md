# PROJECT NIVASHA: ZERO TRUST EXAM ENGINE

NIVASHA is an AI-powered zero-trust exam platform that protects question papers by enforcing minimum knowledge access, continuous behavioral risk scoring, and forensic leak tracing before, during, and after an exam.

## MVP Phase 1 Status
- **Backend Framework:** FastAPI (Python)
- **Data Validation:** Pydantic v2
- **Database:** SQLite
- **Security:** Standard Python `cryptography` library for vault encryption concepts.

### Features Implemented
- Clean project structure
- SQLite database schema (Users, Questions, AuditLogs, RiskEvents)
- Pydantic models for data validation
- Encrypted Question Vault service (AES-style using Fernet)
- Minimum Knowledge Access Engine (Role-based checks)
- Basic Insider Risk Engine (Rule-based heuristics)
- Professional Light Theme Admin Dashboard

### Setup and Run Commands

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the backend application:**
   ```bash
   python main.py
   # Or using uvicorn directly: uvicorn nivasha.api.main:app --reload
   ```
   The backend will start on `http://127.0.0.1:8000`.

3. **Seed Initial Data:**
   Run this once to create demo users (Admin=1, Creator=2, Student=3):
   ```bash
   curl -X POST http://127.0.0.1:8000/seed
   ```

4. **Open the Admin Dashboard:**
   Navigate in your browser to:
   ```
   http://127.0.0.1:8000/admin/dashboard
   ```
   *(Note: This uses a mock header bypass for the browser MVP. In a real app, this requires JWT).*

5. **Run Tests:**
   ```bash
   pytest tests/
   ```

### Notes on MVP Simplifications
- **Authentication:** Uses a mock `x-user-id` header for simplicity in API calls instead of full JWT flow.
- **Key Management:** Uses an auto-generated symmetric key stored in memory/env for the encryption vault. Production requires KMS.
