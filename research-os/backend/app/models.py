"""Database tables. Every piece of research keeps its provenance: who/what produced it, from where, and when.

Reading order for newcomers:
  Project → SearchRun → SearchResult → Source → Snapshot → Chunk   (what the web said)
  Document → Revision → Citation                                     (what we wrote, and what backs it)
  ModelCall, TaskRun, TaskStep                                       (what the AI did and why)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 of the API token
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    # Policy: "standard" (open web) or "scoped" (fetches limited to allowed_domains — use for owned-asset/security work)
    mode: Mapped[str] = mapped_column(String(20), default="standard")
    allowed_domains: Mapped[list] = mapped_column(JSON, default=list)
    allow_tor: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)  # default providers, model overrides, …
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProjectMember(Base):
    __tablename__ = "project_members"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(10))  # owner | editor | viewer


class SearchRun(Base):
    __tablename__ = "search_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(Text)
    params: Mapped[dict] = mapped_column(JSON, default=dict)  # operators, dates, providers requested
    provider_status: Mapped[dict] = mapped_column(JSON, default=dict)  # provider -> "ok"/error text/result count
    task_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    results: Mapped[list["SearchResult"]] = relationship(order_by="SearchResult.rank", cascade="all, delete-orphan")


class SearchResult(Base):
    __tablename__ = "search_results"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("search_runs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text, index=True)
    snippet: Mapped[str] = mapped_column(Text, default="")
    providers: Mapped[list] = mapped_column(JSON, default=list)  # every provider that returned this URL
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(String(20), default="web")  # web | paper | onion | news
    published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    source_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # set once fetched


class Source(Base):
    """One URL in a project's archive. Each fetch adds a Snapshot, so history is kept."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("project_id", "canonical_url"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(20), default="web")
    trust: Mapped[float | None] = mapped_column(Float, nullable=True)  # set by user or a critic agent
    tags: Mapped[list] = mapped_column(JSON, default=list)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    snapshots: Mapped[list["Snapshot"]] = relationship(order_by="Snapshot.fetched_at.desc()", cascade="all, delete-orphan")


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    fetcher: Mapped[str] = mapped_column(String(20))  # direct | tor | firecrawl | jina | apify | provider
    final_url: Mapped[str] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str] = mapped_column(String(100), default="")
    raw: Mapped[str] = mapped_column(Text, default="")  # original HTML/text (binary stored as extracted text only)
    content: Mapped[str] = mapped_column(Text, default="")  # cleaned markdown the LLM reads
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # author, published date, language, …
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Chunk(Base):
    """Retrieval unit. Chunks point at a snapshot (web) or a document revision (notes/files)."""

    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    idx: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)  # swap for pgvector in phase 2


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="note")  # note | doc | report | brief
    title: Mapped[str] = mapped_column(String(300))
    current_rev: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    revisions: Mapped[list["Revision"]] = relationship(order_by="Revision.rev", cascade="all, delete-orphan")


class Revision(Base):
    __tablename__ = "revisions"
    __table_args__ = (UniqueConstraint("document_id", "rev"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    rev: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(100))  # "user:<id>" or "model:<model id>"
    message: Mapped[str] = mapped_column(Text, default="")
    task_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Citation(Base):
    """Links a marker like [S3] in a document revision to the exact snapshot (and passage) it came from."""

    __tablename__ = "citations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("revisions.id", ondelete="CASCADE"), index=True)
    marker: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # web source …
    snapshot_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # … or one of your own documents
    chunk_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quote: Mapped[str] = mapped_column(Text, default="")


class ModelCall(Base):
    __tablename__ = "model_calls"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    task_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(200))
    messages: Mapped[list] = mapped_column(JSON)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    response: Mapped[str] = mapped_column(Text, default="")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10))  # ok | error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TaskRun(Base):
    __tablename__ = "task_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    workflow: Mapped[str] = mapped_column(String(50))
    input: Mapped[dict] = mapped_column(JSON)
    state: Mapped[dict] = mapped_column(JSON, default=dict)  # data passed between steps
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|awaiting_approval|done|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    steps: Mapped[list["TaskStep"]] = relationship(order_by="TaskStep.idx", cascade="all, delete-orphan")


class TaskStep(Base):
    __tablename__ = "task_steps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(30))  # planner | searcher | fetcher | analyst | critic | archiver
    status: Mapped[str] = mapped_column(String(20), default="pending")
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
