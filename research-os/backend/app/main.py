"""Research OS API. Run: uvicorn app.main:app --reload   ·   Docs: http://localhost:8000/docs"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import workflows  # noqa: F401
from .api import documents, projects, research
from .auth import ensure_admin
from .config import settings
from .db import SessionLocal, init_db
from .workflows import research as _research_workflow  # noqa: F401  (registers the "research" workflow)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as db:
        ensure_admin(db, settings.admin_email, settings.admin_token)
    yield


app = FastAPI(title="Research OS", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
for r in (projects.router, documents.router, research.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
