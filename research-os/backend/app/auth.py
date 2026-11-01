"""Bearer-token auth + per-project roles. Kept small on purpose; swap for OAuth/SSO later without touching routes."""

import hashlib
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import Project, ProjectMember, User

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return "ros_" + secrets.token_urlsafe(32)


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Missing bearer token")
    user = db.query(User).filter_by(token_hash=hash_token(token)).first()
    if not user:
        raise HTTPException(401, "Invalid token")
    return user


def project_access(db: Session, project_id: str, user: User, need: str = "viewer") -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    m = db.get(ProjectMember, (project_id, user.id))
    if not m or ROLE_RANK[m.role] < ROLE_RANK[need]:
        raise HTTPException(403, f"Needs {need} access to this project")
    return project


def ensure_admin(db: Session, email: str, token: str) -> None:
    if not token:
        return
    h = hash_token(token)
    if not db.query(User).filter_by(token_hash=h).first():
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            existing.token_hash = h
        else:
            db.add(User(email=email, token_hash=h))
        db.commit()
