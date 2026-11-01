import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user, hash_token, new_token, project_access
from ..db import get_db
from ..models import Document, Project, ProjectMember, User

router = APIRouter()


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    mode: str = Field("standard", pattern="^(standard|scoped)$")
    allowed_domains: list[str] = []
    allow_tor: bool = False
    settings: dict = {}


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    mode: str | None = Field(None, pattern="^(standard|scoped)$")
    allowed_domains: list[str] | None = None
    allow_tor: bool | None = None
    settings: dict | None = None


def project_out(p: Project, role: str | None = None) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description, "mode": p.mode,
            "allowed_domains": p.allowed_domains, "allow_tor": p.allow_tor, "settings": p.settings,
            "shared": bool(p.share_token), "share_token": p.share_token if role == "owner" else None,
            "role": role, "created_at": p.created_at}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email}


@router.post("/users")
def create_user(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Any signed-in user can invite someone; the new user's token is shown once."""
    email = (body.get("email") or "").strip().lower()
    if not email or db.query(User).filter_by(email=email).first():
        raise HTTPException(400, "Email missing or already registered")
    token = new_token()
    db.add(User(email=email, token_hash=hash_token(token)))
    db.commit()
    return {"email": email, "token": token}


@router.get("/projects")
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(Project, ProjectMember.role).join(ProjectMember, ProjectMember.project_id == Project.id)
            .filter(ProjectMember.user_id == user.id).order_by(Project.created_at.desc()).all())
    return [project_out(p, role) for p, role in rows]


@router.post("/projects")
def create_project(body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.mode == "scoped" and not body.allowed_domains:
        raise HTTPException(400, "A scoped project needs at least one allowed domain")
    p = Project(**body.model_dump(), created_by=user.id)
    db.add(p)
    db.flush()
    db.add(ProjectMember(project_id=p.id, user_id=user.id, role="owner"))
    db.commit()
    return project_out(p, "owner")


@router.get("/projects/{pid}")
def get_project(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_access(db, pid, user)
    return project_out(p, db.get(ProjectMember, (pid, user.id)).role)


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_access(db, pid, user, "owner")  # policy changes are owner-only
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    if p.mode == "scoped" and not p.allowed_domains:
        raise HTTPException(400, "A scoped project needs at least one allowed domain")
    db.commit()
    return project_out(p, "owner")


@router.delete("/projects/{pid}")
def delete_project(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(project_access(db, pid, user, "owner"))
    db.commit()
    return {"ok": True}


@router.post("/projects/{pid}/members")
def add_member(pid: str, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user, "owner")
    role = body.get("role", "viewer")
    if role not in ("viewer", "editor", "owner"):
        raise HTTPException(400, "role must be viewer, editor or owner")
    target = db.query(User).filter_by(email=(body.get("email") or "").lower()).first()
    if not target:
        raise HTTPException(404, "No user with that email — create them with POST /users first")
    m = db.get(ProjectMember, (pid, target.id)) or ProjectMember(project_id=pid, user_id=target.id)
    m.role = role
    db.add(m)
    db.commit()
    return {"email": target.email, "role": role}


@router.post("/projects/{pid}/share")
def share(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_access(db, pid, user, "owner")
    p.share_token = secrets.token_urlsafe(18)
    db.commit()
    return {"share_token": p.share_token}


@router.delete("/projects/{pid}/share")
def unshare(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user, "owner").share_token = None
    db.commit()
    return {"ok": True}


@router.get("/shared/{token}")
def shared_view(token: str, db: Session = Depends(get_db)):
    """Public read-only view: reports and notes with their current text. No sources' raw content, no settings."""
    p = db.query(Project).filter_by(share_token=token).first()
    if not p:
        raise HTTPException(404, "Not found")
    docs = db.query(Document).filter_by(project_id=p.id).order_by(Document.updated_at.desc()).all()
    return {"name": p.name, "description": p.description,
            "documents": [{"id": d.id, "title": d.title, "kind": d.kind, "updated_at": d.updated_at,
                           "content": d.revisions[-1].content if d.revisions else ""} for d in docs]}
