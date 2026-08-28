# Nivasha Zero-Trust Exam Security Engine - Backend

Real-time API and fairness engine for the zero-trust exam platform.

## Architecture
Domain-Driven Design (DDD) layout:
- `api/`: FastAPI route handlers (admin, student, websocket).
- `core/`: Config and environment secrets.
- `db/`: SQLite WAL + Text Field Encryption layer.
- `exam/`: Deterministic paper assembly.
- `forensic/`: Tri-layer forensic watermarking.
- `psychometrics/`: 3PL IRT logic and fairness validation.
- `schemas/`: Pydantic V2 models.
- `security/`: AES-256-GCM crypto and T-5 unlock rules.
- `services/`: Audit log signing and telemetry parsing.

## Installation

```bash
python -m venv .venv
# Activate venv:
# Windows: .\.venv\Scripts\Activate.ps1
# Mac/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

## Running the Backend

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

## Running Tests

```bash
cd backend
pytest tests/
```

## Endpoints Overview

- `GET /api/v1/health`: Node status.
- `WS /ws/admin/telemetry`: Admin real-time WebSocket.
- `GET /api/v1/admin/*`: Admin dashboard reads.
- `POST /api/v1/admin/forensic/trace`: Evaluate leaks.
- `POST /api/v1/student/authenticate`: UUID login.
- `GET /api/v1/student/fetch-paper`: Gets personalized watermarked paper.
- `POST /api/v1/student/log-security-event`: Receives kiosk restriction failures.
- `POST /api/v1/student/submit`: Server-side scoring and receipt generation.

## Demo Flow
1. Start the server (auto-seeds the DB and generates `admin_token.txt` in the root).
2. Kiosk authenticates using `demo-uuid-1234`.
3. Kiosk calls `/fetch-paper`. The backend uses IRT algorithms to select questions, applies synonyms/zero-width watermarks, and returns the JSON without answer keys.
4. Kiosk triggers events (e.g. `clipboard_attempt`). Backend stores it, assigns `HIGH` severity, signs the audit log, and broadcasts via WS.
5. Admin dashboard consumes the WS stream and REST endpoints to monitor the live session.

## Security Limitations
- This software **does not** make exams 100% leak-proof.
- External hardware captures (e.g., phone cameras) cannot be completely prevented by software alone.
- Forensic tracing output provides **investigation leads only**, not definitive legal proof of guilt.
- OCR image processing is not implemented natively yet (future work); currently, text must be pasted manually into the forensic tracer.
