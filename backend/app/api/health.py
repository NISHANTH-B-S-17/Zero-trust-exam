from fastapi import APIRouter
from app.db import database

router = APIRouter()

@router.get("", operation_id="health_check_v1")
@router.get("/health", operation_id="health_check_v1_health")
async def health_check():
    try:
        await database.ensure_db_initialized()
    except Exception:
        pass
    return {"status": "ok", "service": "Nivasha Security Engine Backend"}
