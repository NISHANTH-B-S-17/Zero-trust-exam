from fastapi import APIRouter
from app.db import database

router = APIRouter()

@router.get("")
@router.get("/")
@router.get("/health")
async def health_check():
    try:
        await database.ensure_db_initialized()
    except Exception:
        pass
    return {"status": "ok", "service": "Nivasha Security Engine Backend"}
