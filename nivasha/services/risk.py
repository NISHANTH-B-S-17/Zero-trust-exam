from sqlalchemy.orm import Session
from nivasha.models.domain import RiskEvent
from datetime import datetime, timezone, timedelta

class RiskEngine:
    @staticmethod
    def calculate_current_score(db: Session, user_id: int) -> int:
        """
        Calculates score by summing events. 
        In a real scenario, this would have time-decay.
        """
        events = db.query(RiskEvent).filter(RiskEvent.user_id == user_id).all()
        total_score = sum(e.score_delta for e in events)
        
        # Cap between 0 and 100
        return max(0, min(100, total_score))

    @staticmethod
    def get_risk_level(score: int) -> str:
        if score <= 30: return "Low"
        if score <= 60: return "Medium"
        if score <= 85: return "High"
        return "Critical"

    @staticmethod
    def evaluate_question_access(db: Session, user_id: int, question_id: int):
        """Rule: Viewing a question adds a small baseline risk. Viewing outside hours adds more."""
        current_hour = datetime.now(timezone.utc).hour
        
        # Assuming normal hours are 8am to 6pm (8 to 18) UTC for MVP
        is_after_hours = current_hour < 8 or current_hour >= 18
        
        delta = 0
        reason = ""
        if is_after_hours:
            delta = 10
            reason = f"After-hours access to question {question_id}"
        else:
            delta = 1
            reason = f"Routine access to question {question_id}"
            
        if delta > 0:
            event = RiskEvent(user_id=user_id, score_delta=delta, reason=reason)
            db.add(event)
            db.commit()

risk_engine = RiskEngine()
