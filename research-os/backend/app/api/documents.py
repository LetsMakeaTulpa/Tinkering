"""Notes, docs and reports. Every save is a new revision (full history + diffs) and is indexed into project memory."""

import difflib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user, project_access
from ..db import get_db
from ..memory.chunker import chunk_text
from ..models import Chunk, Citation, Document, Revision, User

router = APIRouter()


class DocIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    kind: str = Field("note", pattern="^(note|doc|report|brief)$")
    content: str = ""


class DocSave(BaseModel):
    content: str
    title: str | None = None
    message: str = ""
    base_rev: int | None = None  # the revision the editor started from; rejects stale saves


def doc_out(d: Document, with_content=True) -> dict:
    out = {"id": d.id, "project_id": d.project_id, "kind": d.kind, "title": d.title, "current_rev": d.current_rev,
           "created_at": d.created_at, "updated_at": d.updated_at}
    if with_content:
        out["content"] = d.revisions[-1].content if d.revisions else ""
    return out


def _reindex(db: Session, doc: Document, content: str) -> None:
    db.query(Chunk).filter_by(document_id=doc.id).delete()
    for i, piece in enumerate(chunk_text(content)):
        db.add(Chunk(project_id=doc.project_id, document_id=doc.id, idx=i, text=piece))


def _doc(db: Session, did: str, user: User, need: str) -> Document:
    d = db.get(Document, did)
    if not d:
        raise HTTPException(404, "Document not found")
    project_access(db, d.project_id, user, need)
    return d


@router.get("/projects/{pid}/documents")
def list_docs(pid: str, kind: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user)
    q = db.query(Document).filter_by(project_id=pid)
    if kind:
        q = q.filter_by(kind=kind)
    return [doc_out(d, False) for d in q.order_by(Document.updated_at.desc()).all()]


@router.post("/projects/{pid}/documents")
def create_doc(pid: str, body: DocIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user, "editor")
    d = Document(project_id=pid, kind=body.kind, title=body.title, current_rev=1)
    db.add(d)
    db.flush()
    db.add(Revision(document_id=d.id, rev=1, content=body.content, author=f"user:{user.id}", message="created"))
    _reindex(db, d, body.content)
    db.commit()
    db.refresh(d)
    return doc_out(d)


@router.get("/documents/{did}")
def get_doc(did: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _doc(db, did, user, "viewer")
    out = doc_out(d)
    rev = d.revisions[-1] if d.revisions else None
    out["citations"] = [{"marker": c.marker, "source_id": c.source_id, "snapshot_id": c.snapshot_id,
                         "document_id": c.document_id, "quote": c.quote}
                        for c in db.query(Citation).filter_by(revision_id=rev.id).all()] if rev else []
    return out


@router.put("/documents/{did}")
def save_doc(did: str, body: DocSave, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _doc(db, did, user, "editor")
    if body.base_rev is not None and body.base_rev != d.current_rev:
        raise HTTPException(409, f"Document changed since revision {body.base_rev} (now {d.current_rev}). Reload first.")
    if d.revisions and d.revisions[-1].content == body.content and not body.title:
        return doc_out(d)
    d.current_rev += 1
    if body.title:
        d.title = body.title
    d.updated_at = datetime.now(timezone.utc)
    db.add(Revision(document_id=d.id, rev=d.current_rev, content=body.content, author=f"user:{user.id}",
                    message=body.message))
    _reindex(db, d, body.content)
    db.commit()
    db.refresh(d)
    return doc_out(d)


@router.delete("/documents/{did}")
def delete_doc(did: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_doc(db, did, user, "editor"))
    db.commit()
    return {"ok": True}


@router.get("/documents/{did}/revisions")
def revisions(did: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _doc(db, did, user, "viewer")
    return [{"rev": r.rev, "author": r.author, "message": r.message, "created_at": r.created_at,
             "task_run_id": r.task_run_id, "chars": len(r.content)} for r in reversed(d.revisions)]


@router.get("/documents/{did}/diff")
def diff(did: str, a: int, b: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _doc(db, did, user, "viewer")
    revs = {r.rev: r for r in d.revisions}
    if a not in revs or b not in revs:
        raise HTTPException(404, "Revision not found")
    lines = difflib.unified_diff(revs[a].content.splitlines(), revs[b].content.splitlines(),
                                 f"rev {a}", f"rev {b}", lineterm="")
    return {"a": a, "b": b, "diff": "\n".join(lines)}
