from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime
import uuid
import hashlib
from typing import Dict, Any, List

from steganography import apply_layer1
from database import get_db, log_event

app = FastAPI(title="Nivasha Security Node")

# Allow local kiosk
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to null/file:// or localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AuthRequest(BaseModel):
    roll_number: str
    name: str = ""
    seat_number: str = ""

class SyncRequest(BaseModel):
    student_uuid: str
    active_question_id: str = None
    responses: dict = {}
    remaining_seconds: int = 3600
    flags: dict = {}
    security_events: list = []

class SecurityEvent(BaseModel):
    student_uuid: str
    type: str
    timestamp: str
    question_idx: int = 0

class SubmitRequest(BaseModel):
    student_uuid: str
    responses: dict
    remaining_seconds: int
    auto_submit: bool = False

# Insider Threat Risk Engine
def evaluate_insider_risk(student_uuid: str, events: List[dict]) -> int:
    risk_score = 0
    for evt in events:
        evt_type = evt.get("type", "")
        if "clipboard" in evt_type:
            risk_score += 25
        elif "shortcut" in evt_type:
            risk_score += 15
        elif "focus_loss" in evt_type:
            risk_score += 10
    
    return min(risk_score, 100)

@app.post("/api/v1/student/authenticate")
async def authenticate(req: AuthRequest, db = Depends(get_db)):
    uid = str(uuid.uuid4())
    await log_event(db, "AUTH_SUCCESS", uid, f"Roll: {req.roll_number}, Seat: {req.seat_number}")
    return {"uuid": uid, "token": "local-secure-token"}

@app.post("/api/v1/student/fetch-paper")
async def fetch_paper(req: dict, db = Depends(get_db)):
    student_uuid = req.get("student_uuid", "unknown")
    
    # Mock Paper Generation
    paper_text = "What is the primary function of an air-gapped system?"
    # Apply Layer 1 Steganography
    watermarked_text = apply_layer1(paper_text, student_uuid)
    
    paper = {
        "title": "Nivasha Standard Assessment",
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "text": watermarked_text,
                "options": ["Security", "Speed", "Cost", "Usability"],
                "metadata": "Security - Hard"
            }
        ]
    }
    
    await log_event(db, "PAPER_FETCHED", student_uuid, "Paper generated and watermarked")
    return {"paper": paper, "duration_seconds": 3600}

@app.post("/api/v1/student/heartbeat")
async def heartbeat(req: SyncRequest, db = Depends(get_db)):
    if req.security_events:
        risk = evaluate_insider_risk(req.student_uuid, req.security_events)
        
        for evt in req.security_events:
            await log_event(db, evt.get("type", "UNKNOWN_EVENT"), req.student_uuid, str(evt))
            
        if risk > 75:
            await log_event(db, "RISK_THRESHOLD_EXCEEDED", req.student_uuid, f"Risk Score: {risk}")
            raise HTTPException(status_code=429, detail="Security threshold exceeded. Application locked.")
            
    return {"status": "ok", "synced_at": datetime.datetime.utcnow().isoformat()}

@app.post("/api/v1/student/log-security-event")
async def log_security_event_route(req: SecurityEvent, db = Depends(get_db)):
    await log_event(db, req.type, req.student_uuid, f"QIdx: {req.question_idx}")
    return {"status": "logged"}

@app.post("/api/v1/student/submit")
async def submit_exam(req: SubmitRequest, db = Depends(get_db)):
    receipt_hash = hashlib.sha256(f"{req.student_uuid}{datetime.datetime.utcnow().isoformat()}".encode()).hexdigest()
    
    await db.execute(
        "INSERT INTO submissions (student_uuid, payload, timestamp) VALUES (?, ?, ?)",
        (req.student_uuid, str(req.responses), datetime.datetime.utcnow().isoformat())
    )
    await db.commit()
    await log_event(db, "EXAM_SUBMITTED", req.student_uuid, f"Hash: {receipt_hash}")
    
    return {"receipt_hash": receipt_hash, "score": "Pending"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=True)
