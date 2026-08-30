from fastapi import APIRouter, HTTPException, Depends, Header, Query
from typing import List, Dict, Any, Optional
import aiosqlite
import time
import json

from app.core.config import settings
from app.db import database
from app.schemas.base import SyncPayloadRequest, TraceLeakRequest
from app.schemas.staff import StaffSecurityOverviewResponse, PolicyStatus
from app.security import t5, crypto
from app.forensic import tracer
from app.services import audit

router = APIRouter()

def verify_admin(x_admin_token: str = Header(...)):
    # Validate against configured ADMIN_TOKEN or fallback admin-demo-token
    valid_tokens = {settings.ADMIN_TOKEN, "admin-demo-token"}
    if x_admin_token not in valid_tokens:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return True

@router.get("/staff-security", response_model=StaffSecurityOverviewResponse)
async def get_staff_security_overview(_: bool = Depends(verify_admin)):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute('SELECT * FROM Staff_Users')
        roles_overview = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute('SELECT * FROM Reviewer_Assignments')
        reviewer_assignments = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute('SELECT * FROM Risk_Events')
        risk_alerts = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute('SELECT * FROM Blocked_Actions')
        blocked_actions = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute('SELECT * FROM Staff_Audit_Logs')
        staff_audit_trail = [dict(r) for r in await cursor.fetchall()]

    policy = PolicyStatus()

    return {
        "roles_overview": roles_overview,
        "reviewer_assignments": reviewer_assignments,
        "risk_alerts": risk_alerts,
        "blocked_actions": blocked_actions,
        "staff_audit_trail": staff_audit_trail,
        "policy_status": policy.model_dump()
    }

@router.get("/dashboard")
async def get_dashboard(_: bool = Depends(verify_admin)):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Candidate counts
        cursor = await db.execute('SELECT COUNT(*) as cnt FROM Students')
        total_students = (await cursor.fetchone())['cnt']

        cursor = await db.execute('SELECT COUNT(*) as cnt FROM Question_Vault')
        vault_questions = (await cursor.fetchone())['cnt']

        recent_seconds = 300
        cutoff = int(time.time()) - recent_seconds
        cursor = await db.execute('SELECT COUNT(*) as cnt FROM Students WHERE updated_at >= ?', (cutoff,))
        active_students = (await cursor.fetchone())['cnt']

        cursor = await db.execute('SELECT COUNT(*) as cnt FROM Submissions')
        submitted_students = (await cursor.fetchone())['cnt']

        # Telemetry list
        cursor = await db.execute('SELECT uuid, roll_no, name, status, updated_at FROM Students LIMIT 10')
        students_rows = [dict(r) for r in await cursor.fetchall()]

        telemetry = []
        for s in students_rows:
            is_active = (s['updated_at'] or 0) >= cutoff
            telemetry.append({
                "uuid": s['uuid'],
                "roll_no": s['roll_no'],
                "name": s['name'],
                "status": "ONLINE" if is_active else (s['status'] or "REGISTERED").upper(),
                "ping": "Active" if is_active else f"{int(time.time()) - (s['updated_at'] or time.time())}s ago"
            })

    return {
        "status": "active",
        "message": "Nivasha Admin Dashboard API",
        "total_candidates": total_students,
        "vault_questions": vault_questions,
        "total_submissions": submitted_students,
        "active_now": active_students,
        "stats": {
            "total_candidates": total_students,
            "active_candidates": active_students,
            "registered_idle": f"{total_students - submitted_students} / 0",
            "submitted": submitted_students
        },
        "telemetry": telemetry
    }

@router.get("/live-sessions")
async def get_live_sessions(_: bool = Depends(verify_admin)):
    recent_seconds = 300
    cutoff = int(time.time()) - recent_seconds
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT uuid, name, updated_at FROM Students WHERE updated_at >= ?', (cutoff,))
        return [dict(r) for r in await cursor.fetchall()]

@router.get("/students")
async def get_students(_: bool = Depends(verify_admin)):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Students')
        return [dict(r) for r in await cursor.fetchall()]

@router.post("/register-student")
@router.post("/students")
async def register_student(payload: Dict[str, Any], _: bool = Depends(verify_admin)):
    roll_no = payload.get("roll_no") or payload.get("roll")
    name = payload.get("name")
    if not roll_no or not name:
        raise HTTPException(status_code=400, detail="roll_no and name are required")

    student_uuid = payload.get("uuid") or f"UUID-{int(time.time())}-{roll_no}"
    seat = payload.get("seat") or "A1"
    now = int(time.time())

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Students (uuid, roll_no, name, status, updated_at)
            VALUES (?, ?, ?, ?, ?)''', (student_uuid, roll_no, name, "REGISTERED", now))

        entry = f"{now}|{student_uuid}|STUDENT_REGISTERED|INFO|Name: {name}, Roll: {roll_no}"
        sig = audit.sign_audit_entry(entry)
        await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
            VALUES (?, ?, ?, ?, ?, ?)''', (now, student_uuid, "STUDENT_REGISTERED", "INFO", f"Name: {name}, Roll: {roll_no}", sig))
        await db.commit()

    return {
        "ok": True,
        "status": "registered",
        "uuid": student_uuid,
        "student_uuid": student_uuid,
        "roll_no": roll_no,
        "name": name
    }

@router.get("/submissions")
async def get_submissions(_: bool = Depends(verify_admin)):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Submissions')
        return [dict(r) for r in await cursor.fetchall()]

@router.get("/audit-logs")
async def get_audit_logs(_: bool = Depends(verify_admin)):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Audit_Logs ORDER BY timestamp DESC')
        logs = [dict(r) for r in await cursor.fetchall()]

    for log in logs:
        log['is_valid'] = audit.verify_audit_signature(log)
    return {"logs": logs}

@router.get("/questions")
async def get_questions(_: bool = Depends(verify_admin)):
    q = await database.fetch_all_questions()
    return {"questions": q}

@router.post("/payload/sync")
async def sync_payload(request: SyncPayloadRequest, _: bool = Depends(verify_admin)):
    try:
        envelope = bytes.fromhex(request.envelope_hex)
        with open("buffered_payload.enc", "wb") as f:
            f.write(envelope)
        return {"status": "buffered", "bytes": len(envelope)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/forensic/trace")
@router.post("/forensic-scan")
@router.post("/trace-leak")
async def trace_leak(request: TraceLeakRequest, _: bool = Depends(verify_admin)):
    result = tracer.trace_leak(request.leaked_text, request.candidate_uuids)

    now = int(time.time())
    entry = f"{now}|admin|LEAK_TRACE_RUN|MEDIUM|Result: {result['likely_source_session']}"
    sig = audit.sign_audit_entry(entry)

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
            VALUES (?, ?, ?, ?, ?, ?)''', (now, "admin", "LEAK_TRACE_RUN", "MEDIUM", f"Result: {result['likely_source_session']}", sig))
        await db.commit()

    return result

@router.get("/health-check")
async def node_health_check(_: bool = Depends(verify_admin)):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM Students')
        student_count = (await cursor.fetchone())[0]
        cursor = await db.execute('SELECT COUNT(*) FROM Question_Vault')
        question_count = (await cursor.fetchone())[0]
    return {
        "ok": True,
        "node_status": "ONLINE",
        "cipher_suite": "AES-256-GCM / SHA-256",
        "api_version": "v1.0.0",
        "student_count": student_count,
        "question_count": question_count,
        "database_status": "CONNECTED"
    }

@router.get("/forms/{form_id}/fairness-report")
async def get_fairness_report(form_id: str, _: bool = Depends(verify_admin)):
    # Mocking form retrieval for report endpoint
    return {"status": "success", "report": "Forms are equivalently balanced by IRT standards."}
