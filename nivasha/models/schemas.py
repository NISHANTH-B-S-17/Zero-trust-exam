from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from nivasha.models.domain import RoleEnum

# --- User Models ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    role: RoleEnum

class User(UserBase):
    id: int
    role: RoleEnum
    
    model_config = ConfigDict(from_attributes=True)

# --- Question Models ---
class QuestionBase(BaseModel):
    topic: str

class QuestionCreate(QuestionBase):
    content: str # Raw text from client

class Question(QuestionBase):
    id: int
    creator_id: int
    # Note: intentionally omitting encrypted_content from the standard API response to avoid leaks
    
    model_config = ConfigDict(from_attributes=True)

class QuestionDecrypted(Question):
    content: str # Decrypted text

# --- Audit & Risk Models ---
class AuditLogBase(BaseModel):
    action: str
    resource_type: str
    resource_id: Optional[str] = None

class AuditLog(AuditLogBase):
    id: int
    timestamp: datetime
    user_id: int
    
    model_config = ConfigDict(from_attributes=True)

class RiskScoreResponse(BaseModel):
    user_id: int
    current_score: int
    risk_level: str
