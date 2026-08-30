from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db import database
from app.api import health, admin, student, ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    await database.seed_demo_data()
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
        "http://localhost:8080",
        "http://localhost:8081",
        "https://zero-trust-exam.vercel.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["x-admin-token", "Content-Type", "Authorization"],
    expose_headers=["x-admin-token"],
)

app.include_router(health.router, prefix=settings.API_V1_STR, tags=["health"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])
app.include_router(student.router, prefix=f"{settings.API_V1_STR}/student", tags=["student"])
app.include_router(ws.router, prefix="/ws/admin", tags=["telemetry"])
