from pydantic import BaseModel
from typing import Dict, List, Optional

# --- Admin Schemas ---
class SyncPayloadRequest(BaseModel):
    envelope_hex: str
    
class TraceLeakRequest(BaseModel):
    leaked_text: str
    candidate_uuids: Optional[List[str]] = None

# --- Student Schemas ---
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
