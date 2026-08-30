import time
import json
import hashlib
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Optional
import aiosqlite

from app.db.database import encrypt_field, decrypt_field
from app.core.config import settings
from app.schemas.base import AuthRequest, FetchPaperRequest, HeartbeatRequest, SecurityEventRequest, SubmitRequest
from app.db import database
from app.exam.generator import FairExamFormGenerator
from app.psychometrics.fairness import FormEquivalenceValidator
from app.forensic import watermark
from app.services import telemetry, audit
from app.api.ws import manager

router = APIRouter()

@router.post("/authenticate")
async def student_auth(request: AuthRequest):
    identifier = request.get_identifier()
    if not identifier:
        raise HTTPException(status_code=400, detail="Identifier (UUID or Roll Number) is required")

    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Students WHERE uuid = ? OR roll_no = ?', (identifier, identifier))
        student = await cursor.fetchone()
        
    if not student:
        raise HTTPException(status_code=401, detail="Invalid student identifier")
        
    now = int(time.time())
    return {
        "ok": True,
        "status": "authenticated",
        "student_uuid": student['uuid'],
        "uuid": student['uuid'],
        "name": student['name'],
        "roll_no": student['roll_no'],
        "seat": "A1",
        "center": "Main Center",
        "exam_id": "EXAM-2026-001",
        "duration_seconds": 3600,
        "server_time": now,
        "exam_start_time": now - 60,
        "login_window_open": True,
        "token": f"jwt-{student['uuid']}-session",
        "student": {"uuid": student['uuid'], "name": student['name']}
    }

async def _get_or_generate_paper(student_uuid: str):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Generated_Papers WHERE student_uuid = ?', (student_uuid,))
        existing_paper = await cursor.fetchone()
        
    if existing_paper:
        paper_data = json.loads(existing_paper['paper_json'])
        if isinstance(paper_data, list):
            paper_data = {
                "questions": paper_data,
                "total_questions": len(paper_data),
                "duration_seconds": 3600
            }
        return paper_data
        
    all_q = await database.fetch_all_questions()
    selected_qs = FairExamFormGenerator.generate_deterministic_paper(all_q, student_uuid, target_count=len(all_q))
    
    watermarked_paper = []
    honeytoken_answers = {}
    
    for q in selected_qs:
        wq = watermark.embed_watermark(q, student_uuid)
        honeytoken_answers[str(wq['id'])] = wq.get('correct_answer')
        
        # Ensure question field structure aligns with kiosk UI expectations
        if "type" not in wq and "question_type" in wq:
            wq["type"] = wq["question_type"].lower()
            
        wq.pop('correct_answer', None)
        wq.pop('correct_answer_encrypted', None)
        watermarked_paper.append(wq)
        
    now = int(time.time())
    paper_structure = {
        "questions": watermarked_paper,
        "total_questions": len(watermarked_paper),
        "duration_seconds": 3600
    }

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Generated_Papers (student_uuid, paper_json, honeytoken_answers_json, created_at)
            VALUES (?, ?, ?, ?)''', (student_uuid, json.dumps(paper_structure), json.dumps(honeytoken_answers), now))
        
        entry = f"{now}|{student_uuid}|PAPER_FETCHED|INFO|Generated watermarked paper"
        sig = audit.sign_audit_entry(entry)
        await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
            VALUES (?, ?, ?, ?, ?, ?)''', (now, student_uuid, "PAPER_FETCHED", "INFO", "Generated watermarked paper", sig))
        await db.commit()
        
    return paper_structure

@router.get("/fetch-paper")
async def fetch_paper_get(student_uuid: str):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Students WHERE uuid = ?', (student_uuid,))
        student = await cursor.fetchone()
    if not student:
        raise HTTPException(status_code=401, detail="Student session unauthenticated")

    paper_structure = await _get_or_generate_paper(student_uuid)
    return {
        "ok": True,
        "paper": paper_structure,
        "duration_seconds": 3600,
        "questions": paper_structure["questions"]
    }

@router.post("/fetch-paper")
async def fetch_paper_post(request: FetchPaperRequest):
    student_uuid = request.student_uuid or request.uuid
    if not student_uuid:
        raise HTTPException(status_code=400, detail="student_uuid is required")

    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Students WHERE uuid = ?', (student_uuid,))
        student = await cursor.fetchone()
    if not student:
        raise HTTPException(status_code=401, detail="Student session unauthenticated")

    paper_structure = await _get_or_generate_paper(student_uuid)
    return {
        "ok": True,
        "paper": paper_structure,
        "duration_seconds": 3600,
        "questions": paper_structure["questions"]
    }

@router.post("/heartbeat")
async def student_heartbeat(request: HeartbeatRequest):
    now = int(time.time())
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('UPDATE Students SET updated_at = ? WHERE uuid = ?', (now, request.student_uuid))
        
        # Also persist state in cached_state_json if available
        state_digest = {
            "responses": request.responses,
            "remaining_seconds": request.remaining_seconds or request.time_remaining,
            "flags": request.flags,
            "status": request.status
        }
        try:
            await db.execute('UPDATE Students SET cached_state_json = ? WHERE uuid = ?', (json.dumps(state_digest), request.student_uuid))
        except Exception:
            pass
        await db.commit()
        
    await manager.broadcast({
        "type": "heartbeat", "student_uuid": request.student_uuid, "timestamp": now, "status": request.status
    })
    return {"ok": True, "status": "recorded", "server_time": now}

@router.post("/autosave")
async def student_autosave(request: HeartbeatRequest):
    return await student_heartbeat(request)

@router.post("/log-security-event")
async def log_security_event(request: SecurityEventRequest):
    event_type = request.get_event_type()
    detail = request.get_detail()
    severity = telemetry.evaluate_incident_severity(event_type, detail)
    now = int(time.time())
    
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Telemetry_Events (student_uuid, session_id, event_type, severity, detail, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)''', (request.student_uuid, request.session_id, event_type, severity, detail, now))
            
        if severity in ["HIGH", "CRITICAL"]:
            entry = f"{now}|{request.student_uuid}|SECURITY_ALERT_{event_type}|{severity}|{detail}"
            sig = audit.sign_audit_entry(entry)
            await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
                VALUES (?, ?, ?, ?, ?, ?)''', (now, request.student_uuid, f"SECURITY_ALERT_{event_type}", severity, detail, sig))
        await db.commit()
        
    await manager.broadcast({
        "type": "security_event", "student_uuid": request.student_uuid, 
        "event_type": event_type, "severity": severity, "timestamp": now
    })
    return {"ok": True, "status": "logged", "severity": severity}

@router.post("/submit")
async def submit_exam(request: SubmitRequest):
    answers = request.get_answers()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Prevent duplicate submissions
        cursor = await db.execute('SELECT * FROM Submissions WHERE student_uuid = ?', (request.student_uuid,))
        existing_sub = await cursor.fetchone()
        if existing_sub:
            sub_dict = dict(existing_sub)
            receipt = json.loads(sub_dict.get('receipt_json') or '{}')
            return {
                "ok": True,
                "status": "submitted",
                "student_uuid": request.student_uuid,
                "score": sub_dict['score'],
                "correct": receipt.get('correct', 0),
                "total": receipt.get('total', 0),
                "receipt_hash": sub_dict['receipt_hash'],
                "submitted_at": sub_dict['submitted_at'],
                "message": "Exam already submitted"
            }

        cursor = await db.execute('SELECT * FROM Generated_Papers WHERE student_uuid = ?', (request.student_uuid,))
        paper_record = await cursor.fetchone()

    if not paper_record:
        raise HTTPException(status_code=400, detail="No paper found for student")

    honeytoken_answers = json.loads(paper_record['honeytoken_answers_json'])

    total = len(honeytoken_answers)
    correct = sum(1 for q_id, true_ans in honeytoken_answers.items() if answers.get(str(q_id)) == true_ans)
    score = (correct / total * 100) if total > 0 else 0

    now = int(time.time())
    receipt = {
        "student_uuid": request.student_uuid,
        "submitted_at": now,
        "total_answered": len(answers),
        "score": score,
        "correct": correct,
        "total": total
    }
    receipt_hash = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Submissions (student_uuid, score, receipt_hash, receipt_json, submitted_at)
            VALUES (?, ?, ?, ?, ?)''', (request.student_uuid, score, receipt_hash, json.dumps(receipt), now))

        # Update Student session status to SUBMITTED
        await db.execute('UPDATE Students SET status = ?, updated_at = ? WHERE uuid = ?', ("SUBMITTED", now, request.student_uuid))

        entry = f"{now}|{request.student_uuid}|EXAM_SUBMITTED|INFO|Hash: {receipt_hash}"
        sig = audit.sign_audit_entry(entry)
        await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
            VALUES (?, ?, ?, ?, ?, ?)''', (now, request.student_uuid, "EXAM_SUBMITTED", "INFO", f"Hash: {receipt_hash}", sig))
        await db.commit()

    await manager.broadcast({"type": "exam_submit", "student_uuid": request.student_uuid, "timestamp": now})

    return {
        "ok": True,
        "status": "submitted",
        "student_uuid": request.student_uuid,
        "score": score,
        "correct": correct,
        "total": total,
        "receipt_hash": receipt_hash,
        "submitted_at": now
    }
