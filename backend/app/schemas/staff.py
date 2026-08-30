from pydantic import BaseModel
from typing import List, Optional

class PolicyStatus(BaseModel):
    role_based_access_control: bool = True
    assignment_based_reviewer_access: bool = True
    staff_question_views_logged: bool = True
    risk_scoring_active: bool = True
    raw_paper_exposure_minimized: bool = True
    forensic_lead_wording_enforced: bool = True

class StaffUserResponse(BaseModel):
    id: int
    name: str
    role: str
    status: str
    risk_score: int
    last_seen: int

class ReviewerAssignmentResponse(BaseModel):
    id: int
    reviewer_id: int
    reviewer_name: str
    question_ids: str
    access_status: str
    last_viewed: int
    risk_score: int

class RiskEventResponse(BaseModel):
    id: int
    staff_user_id: int
    staff_name: str
    role: str
    risk_score: int
    risk_level: str
    trigger_reason: str
    action_taken: str
    timestamp: int

class BlockedActionResponse(BaseModel):
    id: int
    staff_user_id: int
    staff_name: str
    attempted_action: str
    reason_blocked: str
    policy_rule: str
    timestamp: int

class StaffAuditLogResponse(BaseModel):
    id: int
    staff_user_id: int
    staff_name: str
    role: str
    event: str
    question_id: Optional[int]
    session_id: Optional[str]
    trace_token: Optional[str]
    timestamp: int

class StaffSecurityOverviewResponse(BaseModel):
    roles_overview: List[StaffUserResponse]
    reviewer_assignments: List[ReviewerAssignmentResponse]
    risk_alerts: List[RiskEventResponse]
    blocked_actions: List[BlockedActionResponse]
    staff_audit_trail: List[StaffAuditLogResponse]
    policy_status: PolicyStatus
