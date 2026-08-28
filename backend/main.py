import os
import json
import uuid
import time
import hashlib
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import database
import crypto
import steganography
import t5_unlock
import ai_gen

app = FastAPI(title="Nivasha Security Engine")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin Token Setup
ADMIN_TOKEN_FILE = "admin_token.txt"
if not os.path.exists(ADMIN_TOKEN_FILE):
    admin_token = "admin-" + os.urandom(16).hex()
    with open(ADMIN_TOKEN_FILE, "w") as f:
        f.write(admin_token)
else:
    with open(ADMIN_TOKEN_FILE, "r") as f:
        admin_token = f.read().strip()

def verify_admin(x_admin_token: str = Header(...)):
    if x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return True

# --- Pydantic Models ---

class SyncPayloadRequest(BaseModel):
    envelope_hex: str
    
class T5UnlockRequest(BaseModel):
    center_secret: str
    invigilator_token: str
    exam_id: str
    totp_code: str
    exam_start_timestamp: int
    
class TraceLeakRequest(BaseModel):
    leaked_text: str
    candidate_uuids: Optional[List[str]] = None

class AuthRequest(BaseModel):
    identifier: str # UUID or Roll No
    
class HeartbeatRequest(BaseModel):
    student_uuid: str
    session_id: str
    active_question_id: int
    responses: dict
    time_remaining: int
    
class SecurityEventRequest(BaseModel):
    student_uuid: str
    session_id: str
    event_type: str
    detail: str
    
class SubmitRequest(BaseModel):
    student_uuid: str
    answers: Dict[str, str]

# --- Startup ---

@app.on_event("startup")
async def startup_event():
    await database.init_db()
    await database.seed_demo_data()

# --- WebSocket ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/admin/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    # In a real app we'd auth the WS connection.
    await manager.connect(websocket)
    try:
        while True:
            # Just keep alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- Endpoints ---

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "service": "Nivasha Security Engine"}

@app.post("/api/v1/admin/sync-payload")
async def sync_payload(request: SyncPayloadRequest, _: bool = Depends(verify_admin)):
    # Safely buffer encrypted payload to disk
    try:
        envelope = bytes.fromhex(request.envelope_hex)
        with open("buffered_payload.enc", "wb") as f:
            f.write(envelope)
        return {"status": "buffered", "bytes": len(envelope)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/admin/t5-unlock")
async def t5_unlock_endpoint(request: T5UnlockRequest, _: bool = Depends(verify_admin)):
    try:
        # Validate window
        t5_unlock.validate_t5_unlock(
            request.exam_start_timestamp,
            request.center_secret,
            request.invigilator_token,
            request.exam_id,
            request.totp_code
        )
        
        # In a real system, we derive key and decrypt buffered_payload.enc here.
        # For demo, we just log it and assume the DB is pre-seeded with demo data.
        await database.log_audit("system", "T5_UNLOCK_SUCCESS", "INFO", f"Exam {request.exam_id} unlocked successfully")
        
        return {"status": "unlocked", "message": "Vault open for distribution"}
        
    except ValueError as e:
        await database.log_audit("system", "T5_UNLOCK_FAILED", "HIGH", str(e))
        raise HTTPException(status_code=403, detail=str(e))

@app.post("/api/v1/admin/trace-leak")
async def trace_leak_endpoint(request: TraceLeakRequest, _: bool = Depends(verify_admin)):
    result = steganography.trace_leak(request.leaked_text, request.candidate_uuids)
    await database.log_audit("admin", "LEAK_TRACE_RUN", "MEDIUM", f"Result: {result['student_uuid']}")
    return result

@app.get("/api/v1/admin/audit-logs")
async def get_audit_logs(_: bool = Depends(verify_admin)):
    logs = await database.fetch_audit_logs()
    # Verify signatures before returning
    verified_logs = []
    for log in logs:
        log['is_valid'] = database.verify_audit_signature(log)
        verified_logs.append(log)
    return {"logs": verified_logs}

@app.get("/api/v1/admin/live-monitor")
async def get_live_monitor(_: bool = Depends(verify_admin)):
    sessions = await database.list_live_sessions()
    incidents = await database.fetch_recent_incidents()
    return {
        "active_sessions": sessions,
        "recent_incidents": incidents
    }

@app.post("/api/v1/student/authenticate")
async def student_auth(request: AuthRequest):
    student = await database.get_student(request.identifier)
    if not student:
        student = await database.get_student_by_roll(request.identifier)
        
    if not student:
        raise HTTPException(status_code=401, detail="Invalid student identifier")
        
    return {"status": "authenticated", "student": {"uuid": student['uuid'], "name": student['name']}}

@app.get("/api/v1/student/fetch-paper")
async def fetch_paper(student_uuid: str):
    student = await database.get_student(student_uuid)
    if not student:
        raise HTTPException(status_code=401, detail="Student not found")
        
    # Check if already generated
    existing_paper = await database.get_paper(student_uuid)
    if existing_paper:
        return {"paper": json.loads(existing_paper['paper_json'])}
        
    # Generate new
    all_q = await database.fetch_all_questions()
    selected_qs = ai_gen.assemble_balanced_paper(all_q, student_uuid, target_count=4) # Demo uses 4
    
    # Watermark and strip correct answers
    watermarked_paper = []
    honeytoken_answers = {}
    
    for q in selected_qs:
        wq = steganography.embed_watermark(q, student_uuid)
        # Save correct answer for scoring, strip from client payload
        honeytoken_answers[str(wq['id'])] = wq.get('correct_answer')
        
        # Don't send correct answers to client
        if 'correct_answer' in wq:
            del wq['correct_answer']
        if 'correct_answer_encrypted' in wq:
            del wq['correct_answer_encrypted']
            
        watermarked_paper.append(wq)
        
    await database.save_paper(student_uuid, watermarked_paper, honeytoken_answers, 60)
    await database.log_audit(student_uuid, "PAPER_FETCHED", "INFO", "Generated watermarked paper")
    
    return {"paper": watermarked_paper}

@app.post("/api/v1/student/heartbeat")
async def student_heartbeat(request: HeartbeatRequest):
    await database.save_student_heartbeat(request.student_uuid, json.dumps(request.model_dump()))
    await database.record_telemetry_event(request.student_uuid, request.session_id, "heartbeat", "LOW", "Alive")
    await manager.broadcast({
        "type": "heartbeat",
        "student_uuid": request.student_uuid,
        "timestamp": int(time.time())
    })
    return {"status": "recorded"}

def evaluate_incident_severity(event_type: str, detail: str) -> str:
    rules = {
        "heartbeat": "LOW",
        "focus_returned": "LOW",
        "exam_submit": "INFO",
        "focus_loss": "MEDIUM",
        "suspicious_keystroke": "HIGH",
        "clipboard_attempt": "HIGH",
        "shortcut_attempt": "HIGH"
    }
    return rules.get(event_type, "LOW")

@app.post("/api/v1/student/log-security-event")
async def log_security_event(request: SecurityEventRequest):
    severity = evaluate_incident_severity(request.event_type, request.detail)
    
    await database.record_telemetry_event(
        request.student_uuid, request.session_id, request.event_type, severity, request.detail
    )
    
    if severity in ["HIGH", "CRITICAL"]:
        await database.log_audit(request.student_uuid, f"SECURITY_ALERT_{request.event_type.upper()}", severity, request.detail)
        
    await manager.broadcast({
        "type": "security_event",
        "student_uuid": request.student_uuid,
        "event_type": request.event_type,
        "severity": severity,
        "detail": request.detail,
        "timestamp": int(time.time())
    })
    
    return {"status": "logged", "severity": severity}

@app.post("/api/v1/student/submit")
async def submit_exam(request: SubmitRequest):
    paper_record = await database.get_paper(request.student_uuid)
    if not paper_record:
        raise HTTPException(status_code=400, detail="No paper found for student")
        
    honeytoken_answers = json.loads(paper_record['honeytoken_answers_json'])
    
    total = len(honeytoken_answers)
    correct = 0
    
    for q_id, true_ans in honeytoken_answers.items():
        if str(q_id) in request.answers and request.answers[str(q_id)] == true_ans:
            correct += 1
            
    score = (correct / total * 100) if total > 0 else 0
    
    # Receipt
    receipt = {
        "student_uuid": request.student_uuid,
        "submitted_at": int(time.time()),
        "total_answered": len(request.answers)
    }
    receipt_str = json.dumps(receipt, sort_keys=True)
    receipt_hash = hashlib.sha256(receipt_str.encode()).hexdigest()
    
    await database.record_submission(request.student_uuid, request.answers, score, total, correct, receipt_hash, receipt)
    await database.log_audit(request.student_uuid, "EXAM_SUBMITTED", "INFO", f"Hash: {receipt_hash}")
    
    await manager.broadcast({
        "type": "exam_submit",
        "student_uuid": request.student_uuid,
        "timestamp": int(time.time())
    })
    
    return {
        "status": "submitted",
        "receipt_hash": receipt_hash,
        "submitted_at": receipt["submitted_at"]
    }
