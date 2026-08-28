from fastapi import FastAPI, Depends, HTTPException, Header, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List

from nivasha.core.database import get_db, engine, Base
from nivasha.models import domain, schemas
from nivasha.services.vault import vault
from nivasha.services.access import access_engine, log_action
from nivasha.services.risk import risk_engine

import os

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nivasha Zero Trust Exam Engine", version="0.1.0")

# Setup templates
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=template_dir)


# --- Mock Auth Dependency ---
def get_current_user(x_user_id: int = Header(..., description="Mock user ID for MVP"), db: Session = Depends(get_db)) -> domain.User:
    user = db.query(domain.User).filter(domain.User.id == x_user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user ID")
    return user

# --- Seed Data Endpoint (for Hackathon ease) ---
@app.post("/seed")
def seed_data(db: Session = Depends(get_db)):
    if db.query(domain.User).count() > 0:
        return {"msg": "Already seeded"}
    
    admin = domain.User(username="admin_user", role=domain.RoleEnum.admin)
    creator = domain.User(username="q_creator", role=domain.RoleEnum.creator)
    student = domain.User(username="student1", role=domain.RoleEnum.student)
    
    db.add_all([admin, creator, student])
    db.commit()
    return {"msg": "Seeded users. admin=1, creator=2, student=3"}

# --- API Endpoints ---
@app.post("/questions/", response_model=schemas.Question)
def create_question(q: schemas.QuestionCreate, current_user: domain.User = Depends(get_current_user), db: Session = Depends(get_db)):
    access_engine.verify_can_create_question(current_user)
    
    encrypted = vault.encrypt({"text": q.content})
    db_question = domain.Question(topic=q.topic, encrypted_content=encrypted, creator_id=current_user.id)
    
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    
    log_action(db, current_user.id, "CREATE", "Question", db_question.id)
    return db_question

@app.get("/questions/{q_id}", response_model=schemas.QuestionDecrypted)
def read_question(q_id: int, current_user: domain.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_question = db.query(domain.Question).filter(domain.Question.id == q_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
        
    access_engine.verify_can_view_question(current_user, db_question.creator_id)
    
    # Evaluate risk BEFORE decrypting
    risk_engine.evaluate_question_access(db, current_user.id, q_id)
    
    decrypted_data = vault.decrypt(db_question.encrypted_content)
    
    log_action(db, current_user.id, "VIEW", "Question", db_question.id)
    
    return schemas.QuestionDecrypted(
        id=db_question.id,
        topic=db_question.topic,
        creator_id=db_question.creator_id,
        content=decrypted_data.get("text", "Error: Missing content")
    )

@app.get("/users/{user_id}/risk", response_model=schemas.RiskScoreResponse)
def get_user_risk(user_id: int, current_user: domain.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != domain.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Admin only")
        
    score = risk_engine.calculate_current_score(db, user_id)
    level = risk_engine.get_risk_level(score)
    return schemas.RiskScoreResponse(user_id=user_id, current_score=score, risk_level=level)

# --- Frontend Dashboard Route ---
@app.get("/admin/dashboard", response_class=HTMLResponse)
def get_dashboard(request: Request, x_user_id: int = 1, db: Session = Depends(get_db)):
    # Using a fake header for the browser view for simplicity
    user = db.query(domain.User).filter(domain.User.id == x_user_id).first()
    if not user or user.role != domain.RoleEnum.admin:
        return HTMLResponse(content="<h1>403 Forbidden - Admin Only</h1>", status_code=403)
        
    users = db.query(domain.User).all()
    logs = db.query(domain.AuditLog).order_by(domain.AuditLog.timestamp.desc()).limit(10).all()
    questions = db.query(domain.Question).all()
    
    user_risks = []
    for u in users:
        score = risk_engine.calculate_current_score(db, u.id)
        user_risks.append({"user": u, "score": score, "level": risk_engine.get_risk_level(score)})

    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user_risks": user_risks,
        "logs": logs,
        "questions": questions
    })
