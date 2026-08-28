# PROJECT NIVASHA: ZERO TRUST EXAM ENGINE

NIVASHA is an AI-powered zero-trust exam platform that protects question papers by enforcing minimum knowledge access, continuous behavioral risk scoring, and tri-layer forensic leak tracing before, during, and after an exam.

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
- **Tri-Layer Forensic Leak Tracing:**
  - Zero-width Unicode characters for invisible digital signatures
  - Semantic synonym substitution for semantic watermarking
  - Honeytokens insertion for unique, traceable decoys

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

### 2-Minute Demo Script

1. **Setup & Start:** Run `pip install -r requirements.txt` then `python main.py`. Open `http://127.0.0.1:8000/admin/dashboard` to see the empty admin panel.
2. **Seed Data:** Run `curl -X POST http://127.0.0.1:8000/seed` to create an Admin (ID 1), Creator (ID 2), and Student (ID 3).
3. **Create Question:** As Creator (ID 2), run:
   ```bash
   curl -X POST http://127.0.0.1:8000/questions/ -H "x-user-id: 2" -H "Content-Type: application/json" -d "{\"topic\":\"Math\", \"content\":\"Examine the significant logic of 2+2=4.\"}"
   ```
4. **View as Student:** The student (ID 3) requests the question:
   ```bash
   curl -X GET http://127.0.0.1:8000/questions/1 -H "x-user-id: 3"
   ```
   Notice the content comes back with invisible zero-width characters (invisible in standard terminals, but they're there!) and any synonyms swapped.
5. **Investigate Leak:** Imagine the student copied and leaked the text. As Admin, run a forensics check on the leaked text:
   ```bash
   curl -X POST http://127.0.0.1:8000/forensics/analyze -H "x-user-id: 1" -H "Content-Type: application/json" -d "{\"text\":\"Examine the significant logic of 2+2=4. <insert copied invisible zero-width chars here>\"}"
   ```
   The system will return an investigation lead pointing to ID 3 based on the tri-layer watermark.

### Limitations & Next Steps

- **MVP Simplifications:**
  - **Authentication:** Uses a mock `x-user-id` header for simplicity in API calls instead of full JWT flow.
  - **Key Management:** Uses an auto-generated symmetric key stored in memory/env for the encryption vault. Production requires KMS.
  - **Synonym Dictionary:** Uses a static dictionary mapping for MVP. A production system would employ an LLM or broader dynamic semantic replacement dictionary.
- **Forensic Constraints:**
  - Zero-width characters can be destroyed by advanced text sanitizers or "paste as plain text" in some environments (which is why the multi-layer approach includes synonym and honeytoken layers).
  - The forensics engine provides an "investigation lead" and is explicitly designed not to output automatic guilt, as manual verification of context is always necessary.
