"""Saves fetched content as Source + Snapshot + Chunks. Identical content is not stored twice."""

import hashlib

from sqlalchemy.orm import Session

from .memory.chunker import chunk_text
from .models import Chunk, Snapshot, Source
from .search.base import canonical_url


def archive_content(db: Session, project_id: str, url: str, title: str, content: str, *, fetcher: str,
                    final_url: str | None = None, raw: str = "", http_status: int | None = None,
                    content_type: str = "text/markdown", source_type: str = "web", meta: dict | None = None,
                    error: str | None = None) -> tuple[Source, Snapshot]:
    cu = canonical_url(url)
    src = db.query(Source).filter_by(project_id=project_id, canonical_url=cu).first()
    if not src:
        src = Source(project_id=project_id, url=url, canonical_url=cu, title=title or url, source_type=source_type)
        db.add(src)
        db.flush()
    elif title and src.title in ("", src.url):
        src.title = title
    digest = hashlib.sha256(content.encode()).hexdigest()
    same = db.query(Snapshot).filter_by(source_id=src.id, content_hash=digest).first()
    if same and not error:
        return src, same  # unchanged since last fetch
    snap = Snapshot(source_id=src.id, fetcher=fetcher, final_url=final_url or url, http_status=http_status,
                    content_type=content_type, raw=raw, content=content, content_hash=digest, meta=meta or {}, error=error)
    db.add(snap)
    db.flush()
    for i, piece in enumerate(chunk_text(content)):
        db.add(Chunk(project_id=project_id, snapshot_id=snap.id, source_id=src.id, idx=i, text=piece))
    return src, snap
