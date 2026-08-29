from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

# --- Admin Schemas ---
class SyncPayloadRequest(BaseModel):
    envelope_hex: str
    
class TraceLeakRequest(BaseModel):
    leaked_text: str
    candidate_uuids: Optional[List[str]] = None

# --- Student Schemas ---
class AuthRequest(BaseModel):
    identifier: Optional[str] = None
    roll_number: Optional[str] = None
    roll_no: Optional[str] = None
    uuid: Optional[str] = None

    def get_identifier(self) -> str:
        return self.identifier or self.roll_number or self.roll_no or self.uuid or ""
    
class FetchPaperRequest(BaseModel):
    student_uuid: Optional[str] = None
    uuid: Optional[str] = None

class HeartbeatRequest(BaseModel):
    student_uuid: str
    session_id: Optional[str] = "default-session"
    exam_id: Optional[str] = "exam-001"
    active_question_id: Optional[int] = 0
    current_question: Optional[int] = 0
    responses: Optional[dict] = {}
    time_remaining: Optional[int] = 3600
    remaining_seconds: Optional[int] = 3600
    visited: Optional[List[int]] = []
    marked_for_review: Optional[List[int]] = []
    flags: Optional[dict] = {}
    security_events: Optional[List[dict]] = []
    autosave_digest: Optional[str] = None
    status: Optional[str] = "active"
    
class SecurityEventRequest(BaseModel):
    student_uuid: str
    session_id: Optional[str] = "default-session"
    event_type: Optional[str] = None
    type: Optional[str] = None
    detail: Optional[str] = None
    timestamp: Optional[Any] = None
    question_idx: Optional[int] = 0

    def get_event_type(self) -> str:
        return self.event_type or self.type or "unknown_event"

    def get_detail(self) -> str:
        return self.detail or f"Event {self.get_event_type()} at question {self.question_idx}"
    
class SubmitRequest(BaseModel):
    student_uuid: str
    answers: Optional[Dict[str, Any]] = None
    responses: Optional[Dict[str, Any]] = None
    remaining_seconds: Optional[int] = 0
    auto_submit: Optional[bool] = False

    def get_answers(self) -> Dict[str, Any]:
        return self.answers if self.answers is not None else (self.responses or {})

