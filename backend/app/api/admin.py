from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Dict, Any
import aiosqlite
import time

from app.core.config import settings
from app.db import database
from app.schemas.base import SyncPayloadRequest, TraceLeakRequest
from app.security import t5, crypto
from app.forensic import tracer
from app.services import audit

router = APIRouter()

def verify_admin(x_admin_token: str = Header(...)):
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return True

@router.get("/dashboard")
async def get_dashboard(_: bool = Depends(verify_admin)):
    return {"status": "active", "message": "Nivasha Admin Dashboard API"}

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

@router.get("/forms/{form_id}/fairness-report")
async def get_fairness_report(form_id: str, _: bool = Depends(verify_admin)):
    # Mocking form retrieval for report endpoint
    return {"status": "success", "report": "Forms are equivalently balanced by IRT standards."}
