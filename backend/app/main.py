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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(health.router, prefix=f"{settings.API_V1_STR}/health")
app.include_router(health.router, prefix="/health")
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin")
app.include_router(student.router, prefix=f"{settings.API_V1_STR}/student")
app.include_router(ws.router, prefix="/ws/admin")
