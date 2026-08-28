from sqlalchemy.orm import Session
from nivasha.models.domain import User, RoleEnum, AuditLog
from fastapi import HTTPException, status

def log_action(db: Session, user_id: int, action: str, resource_type: str, resource_id: str = None):
    log = AuditLog(user_id=user_id, action=action, resource_type=resource_type, resource_id=str(resource_id) if resource_id else None)
    db.add(log)
    db.commit()

class AccessEngine:
    @staticmethod
    def verify_can_create_question(user: User):
        if user.role not in [RoleEnum.creator, RoleEnum.admin]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Minimum knowledge violation: Role cannot create questions")

    @staticmethod
    def verify_can_view_question(user: User, question_creator_id: int):
        # MVP Rules:
        # Creator can only view their own
        # Admin can view all (for MVP dashboard, though strictly a true zero trust might require justification)
        # Reviewer could be assigned, but MVP simplifies to: they can't view random questions yet.
        if user.role == RoleEnum.admin:
            return True
        if user.role == RoleEnum.creator and user.id == question_creator_id:
            return True
        
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Minimum knowledge violation: Not authorized to view this specific question.")

access_engine = AccessEngine()
