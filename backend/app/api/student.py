import time
import json
import hashlib
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
import aiosqlite

from app.db.database import encrypt_field, decrypt_field
from app.core.config import settings
from app.schemas.base import AuthRequest, HeartbeatRequest, SecurityEventRequest, SubmitRequest
from app.db import database
from app.exam.generator import FairExamFormGenerator
from app.psychometrics.fairness import FormEquivalenceValidator
from app.forensic import watermark
from app.services import telemetry, audit
from app.api.ws import manager

router = APIRouter()

@router.post("/authenticate")
async def student_auth(request: AuthRequest):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Students WHERE uuid = ? OR roll_no = ?', (request.identifier, request.identifier))
        student = await cursor.fetchone()
        
    if not student:
        raise HTTPException(status_code=401, detail="Invalid student identifier")
        
    return {"status": "authenticated", "student": {"uuid": student['uuid'], "name": student['name']}}

@router.get("/fetch-paper")
async def fetch_paper(student_uuid: str):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Generated_Papers WHERE student_uuid = ?', (student_uuid,))
        existing_paper = await cursor.fetchone()
        
    if existing_paper:
        return {"paper": json.loads(existing_paper['paper_json'])}
        
    all_q = await database.fetch_all_questions()
    selected_qs = FairExamFormGenerator.generate_deterministic_paper(all_q, student_uuid, target_count=2)
    
    # Optional: run fairness validator here and log report
    report = FormEquivalenceValidator.validate_equivalence(selected_qs, selected_qs)
    
    watermarked_paper = []
    honeytoken_answers = {}
    
    for q in selected_qs:
        wq = watermark.embed_watermark(q, student_uuid)
        honeytoken_answers[str(wq['id'])] = wq.get('correct_answer')
        
        # Strip true answers before sending to client
        wq.pop('correct_answer', None)
        wq.pop('correct_answer_encrypted', None)
        watermarked_paper.append(wq)
        
    now = int(time.time())
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Generated_Papers (student_uuid, paper_json, honeytoken_answers_json, created_at)
            VALUES (?, ?, ?, ?)''', (student_uuid, json.dumps(watermarked_paper), json.dumps(honeytoken_answers), now))
        
        # Audit Log
        entry = f"{now}|{student_uuid}|PAPER_FETCHED|INFO|Generated watermarked paper"
        sig = audit.sign_audit_entry(entry)
        await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
            VALUES (?, ?, ?, ?, ?, ?)''', (now, student_uuid, "PAPER_FETCHED", "INFO", "Generated watermarked paper", sig))
        await db.commit()
        
    return {"paper": watermarked_paper}

@router.post("/heartbeat")
async def student_heartbeat(request: HeartbeatRequest):
    now = int(time.time())
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('UPDATE Students SET updated_at = ? WHERE uuid = ?', (now, request.student_uuid))
        await db.commit()
        
    await manager.broadcast({
        "type": "heartbeat", "student_uuid": request.student_uuid, "timestamp": now
    })
    return {"status": "recorded"}

@router.post("/log-security-event")
async def log_security_event(request: SecurityEventRequest):
    severity = telemetry.evaluate_incident_severity(request.event_type, request.detail)
    now = int(time.time())
    
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Telemetry_Events (student_uuid, session_id, event_type, severity, detail, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)''', (request.student_uuid, request.session_id, request.event_type, severity, request.detail, now))
            
        if severity in ["HIGH", "CRITICAL"]:
            entry = f"{now}|{request.student_uuid}|SECURITY_ALERT_{request.event_type}|{severity}|{request.detail}"
            sig = audit.sign_audit_entry(entry)
            await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
                VALUES (?, ?, ?, ?, ?, ?)''', (now, request.student_uuid, f"SECURITY_ALERT_{request.event_type}", severity, request.detail, sig))
        await db.commit()
        
    await manager.broadcast({
        "type": "security_event", "student_uuid": request.student_uuid, 
        "event_type": request.event_type, "severity": severity, "timestamp": now
    })
    return {"status": "logged", "severity": severity}

@router.post("/submit")
async def submit_exam(request: SubmitRequest):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Generated_Papers WHERE student_uuid = ?', (request.student_uuid,))
        paper_record = await cursor.fetchone()
        
    if not paper_record:
        raise HTTPException(status_code=400, detail="No paper found for student")
        
    honeytoken_answers = json.loads(paper_record['honeytoken_answers_json'])
    
    total = len(honeytoken_answers)
    correct = sum(1 for q_id, true_ans in honeytoken_answers.items() if request.answers.get(str(q_id)) == true_ans)
    score = (correct / total * 100) if total > 0 else 0
    
    now = int(time.time())
    receipt = {"student_uuid": request.student_uuid, "submitted_at": now, "total_answered": len(request.answers)}
    receipt_hash = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Submissions (student_uuid, score, receipt_hash, receipt_json, submitted_at)
            VALUES (?, ?, ?, ?, ?)''', (request.student_uuid, score, receipt_hash, json.dumps(receipt), now))
            
        entry = f"{now}|{request.student_uuid}|EXAM_SUBMITTED|INFO|Hash: {receipt_hash}"
        sig = audit.sign_audit_entry(entry)
        await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
            VALUES (?, ?, ?, ?, ?, ?)''', (now, request.student_uuid, "EXAM_SUBMITTED", "INFO", f"Hash: {receipt_hash}", sig))
        await db.commit()
        
    await manager.broadcast({"type": "exam_submit", "student_uuid": request.student_uuid, "timestamp": now})
    
    return {"status": "submitted", "receipt_hash": receipt_hash, "submitted_at": now}
