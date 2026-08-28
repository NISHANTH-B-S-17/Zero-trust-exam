from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, timezone
from nivasha.core.database import Base

class RoleEnum(str, enum.Enum):
    creator = "creator"
    reviewer = "reviewer"
    admin = "admin"
    controller = "controller"
    student = "student"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.student)
    # Hashed password omitted for MVP simplicity, assume basic auth/mocking
    
class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"))
    encrypted_content = Column(Text)
    topic = Column(String, index=True)
    
    creator = relationship("User")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)
    resource_type = Column(String)
    resource_id = Column(String, nullable=True)
    
    user = relationship("User")

class RiskEvent(Base):
    __tablename__ = "risk_events"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"))
    score_delta = Column(Integer)
    reason = Column(String)
    
    user = relationship("User")
