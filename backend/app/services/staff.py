def calculate_risk_level(score: int) -> str:
    """Calculate risk level string from numerical score."""
    if score <= 30:
        return "LOW"
    elif score <= 60:
        return "MEDIUM"
    elif score <= 85:
        return "HIGH"
    return "CRITICAL"

def can_view_question(role: str, staff_id: int, question_id: int, assigned_question_ids: list = None) -> bool:
    """Determine if a staff role is allowed to view a specific question ID."""
    if not assigned_question_ids:
        assigned_question_ids = []
        
    if role == "STUDENT":
        return False
        
    if role == "QUESTION_CREATOR":
        # In MVP we'll assume creators only see their own drafts. 
        # (Assuming ownership isn't fully mapped in this demo, return False for now or mock it if needed)
        # We will strictly say True if it's their draft, False otherwise. Let's assume False for tests.
        return False
        
    if role == "REVIEWER":
        return question_id in assigned_question_ids
        
    if role == "EXAM_CONTROLLER":
        # Can view approved pool/assembly
        return True
        
    if role == "SECURITY_ADMIN":
        # Security admin inspects logs, not raw decrypts
        return False
        
    return False

import aiosqlite
import time
from app.core.config import settings

async def record_staff_audit(staff_user_id: int, staff_name: str, role: str, event: str, question_id: int = None, session_id: str = None, trace_token: str = None):
    now = int(time.time())
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Staff_Audit_Logs 
            (staff_user_id, staff_name, role, event, question_id, session_id, trace_token, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (staff_user_id, staff_name, role, event, question_id, session_id, trace_token, now))
        await db.commit()

async def record_blocked_action(staff_user_id: int, staff_name: str, attempted_action: str, reason_blocked: str, policy_rule: str):
    now = int(time.time())
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('''INSERT INTO Blocked_Actions 
            (staff_user_id, staff_name, attempted_action, reason_blocked, policy_rule, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (staff_user_id, staff_name, attempted_action, reason_blocked, policy_rule, now))
        await db.commit()
