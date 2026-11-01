"""Search, fetch/archive, memory, models and research runs."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user, project_access
from ..db import SessionLocal, get_db
from ..fetch.fetcher import fetch_and_archive
from ..llm.router import LLMError, complete, load_routes, provider_ready
from ..memory.retrieve import search_memory
from ..models import ModelCall, Revision, SearchRun, Snapshot, Source, TaskRun, User
from ..search.base import SearchRequest
from ..search.orchestrator import run_search
from ..search.providers import available
from ..workflows.engine import WORKFLOWS, approve, run_workflow

router = APIRouter()
_tasks: set[asyncio.Task] = set()  # keep references so background runs aren't garbage-collected


# ---------- search ----------

class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    providers: list[str] | None = None
    exact: bool = False
    site: str | None = None
    filetype: str | None = None
    after: str | None = None
    before: str | None = None
    category: str = Field("web", pattern="^(web|news|paper|onion)$")
    limit: int = Field(10, ge=1, le=50)
    extra: str = ""


def run_out(run: SearchRun) -> dict:
    return {"id": run.id, "query": run.query, "params": run.params, "provider_status": run.provider_status,
            "created_at": run.created_at, "task_run_id": run.task_run_id,
            "results": [{"id": r.id, "rank": r.rank, "title": r.title, "url": r.url, "snippet": r.snippet,
                         "providers": r.providers, "score": r.score, "source_type": r.source_type,
                         "published_at": r.published_at, "source_id": r.source_id, "meta": r.meta}
                        for r in run.results]}


@router.get("/providers")
def providers(user: User = Depends(current_user)):
    return available()


@router.post("/projects/{pid}/search")
async def search(pid: str, body: SearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_access(db, pid, user, "editor")
    req = SearchRequest(**body.model_dump(exclude={"providers"}))
    if req.category == "onion" and not p.allow_tor:
        raise HTTPException(400, "Enable Tor for this project to search onion services")
    run = await run_search(db, p, req, body.providers, user.id)
    db.refresh(run)
    return run_out(run)


@router.get("/projects/{pid}/searches")
def searches(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user)
    runs = db.query(SearchRun).filter_by(project_id=pid).order_by(SearchRun.created_at.desc()).limit(100).all()
    return [{"id": r.id, "query": r.query, "provider_status": r.provider_status, "created_at": r.created_at,
             "count": len(r.results)} for r in runs]


@router.get("/searches/{rid}")
def get_search(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    run = db.get(SearchRun, rid) or _404()
    project_access(db, run.project_id, user)
    return run_out(run)


# ---------- fetch / sources ----------

class FetchIn(BaseModel):
    url: str
    method: str = Field("auto", pattern="^(auto|direct|tor|firecrawl|jina|apify|wayback)$")
    wayback_ts: str = ""


def snap_out(s: Snapshot, content=True) -> dict:
    out = {"id": s.id, "fetched_at": s.fetched_at, "fetcher": s.fetcher, "final_url": s.final_url,
           "http_status": s.http_status, "content_type": s.content_type, "content_hash": s.content_hash,
           "meta": s.meta, "error": s.error, "chars": len(s.content)}
    if content:
        out["content"] = s.content
    return out


@router.post("/projects/{pid}/fetch")
async def fetch(pid: str, body: FetchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_access(db, pid, user, "editor")
    src, snap = await fetch_and_archive(db, p, body.url, body.method, body.wayback_ts)
    return {"source_id": src.id, "snapshot": snap_out(snap, content=False)}


@router.get("/projects/{pid}/sources")
def sources(pid: str, q: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user)
    qry = db.query(Source).filter_by(project_id=pid)
    if q:
        qry = qry.filter(Source.title.ilike(f"%{q}%") | Source.url.ilike(f"%{q}%"))
    out = []
    for s in qry.order_by(Source.first_seen.desc()).limit(500).all():
        latest = s.snapshots[0] if s.snapshots else None
        out.append({"id": s.id, "url": s.url, "title": s.title, "source_type": s.source_type, "trust": s.trust,
                    "tags": s.tags, "first_seen": s.first_seen, "snapshots": len(s.snapshots),
                    "latest": snap_out(latest, False) if latest else None})
    return out


@router.get("/sources/{sid}")
def source(sid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(Source, sid) or _404()
    project_access(db, s.project_id, user)
    return {"id": s.id, "url": s.url, "title": s.title, "source_type": s.source_type, "trust": s.trust,
            "tags": s.tags, "snapshots": [snap_out(x, content=(i == 0)) for i, x in enumerate(s.snapshots)]}


@router.patch("/sources/{sid}")
def patch_source(sid: str, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(Source, sid) or _404()
    project_access(db, s.project_id, user, "editor")
    if "trust" in body:
        s.trust = body["trust"]
    if "tags" in body:
        s.tags = body["tags"]
    db.commit()
    return {"ok": True}


@router.get("/snapshots/{snap_id}")
def snapshot(snap_id: str, raw: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(Snapshot, snap_id) or _404()
    project_access(db, db.get(Source, s.source_id).project_id, user)
    out = snap_out(s)
    if raw:
        out["raw"] = s.raw
    return out


@router.get("/projects/{pid}/memory")
async def memory(pid: str, q: str, k: int = 10, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user)
    return [{"chunk_id": c.id, "score": s, "text": c.text, "source_id": c.source_id, "snapshot_id": c.snapshot_id,
             "document_id": c.document_id} for c, s in await search_memory(db, pid, q, k)]


# ---------- models ----------

class AskIn(BaseModel):
    messages: list[dict]
    task_type: str = "synthesis"
    model: str | None = None  # "provider:model" to bypass routing
    temperature: float | None = None
    max_tokens: int | None = None


@router.get("/models")
def models(user: User = Depends(current_user)):
    routes = load_routes()
    refs = {r for lst in [routes.get("default", [])] + list(routes.get("routes", {}).values()) for r in lst}
    return {"routes": routes, "providers": {p: provider_ready(p) for p in
                                            ("featherless", "openrouter", "openai", "ollama", "anthropic")},
            "models": sorted(refs)}


@router.post("/projects/{pid}/llm")
async def llm(pid: str, body: AskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user, "editor")
    params = {k: v for k, v in {"temperature": body.temperature, "max_tokens": body.max_tokens}.items() if v is not None}
    try:
        r = await complete(db, body.task_type, body.messages, project_id=pid, model=body.model, **params)
    except LLMError as e:
        raise HTTPException(502, str(e)) from None
    return {"text": r.text, "provider": r.provider, "model": r.model, "call_id": r.call_id}


@router.get("/projects/{pid}/model-calls")
def model_calls(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user)
    calls = db.query(ModelCall).filter_by(project_id=pid).order_by(ModelCall.created_at.desc()).limit(200).all()
    return [{"id": c.id, "task_type": c.task_type, "provider": c.provider, "model": c.model, "status": c.status,
             "error": c.error, "latency_ms": c.latency_ms, "prompt_tokens": c.prompt_tokens,
             "completion_tokens": c.completion_tokens, "task_run_id": c.task_run_id, "created_at": c.created_at}
            for c in calls]


# ---------- research runs (multi-agent workflows) ----------

class RunIn(BaseModel):
    workflow: str = "research"
    input: dict  # research: {question, providers?, category?, queries?, require_approval?, max_fetch?, model_plan?, model_write?}


def task_out(r: TaskRun) -> dict:
    return {"id": r.id, "workflow": r.workflow, "status": r.status, "input": r.input, "state": r.state,
            "error": r.error, "created_at": r.created_at,
            "steps": [{"idx": s.idx, "agent": s.agent, "status": s.status, "output": s.output, "error": s.error,
                       "started_at": s.started_at, "ended_at": s.ended_at} for s in r.steps]}


async def _run_in_background(run_id: str):
    db = SessionLocal()
    try:
        await run_workflow(db, run_id)
    finally:
        db.close()


def _start(run_id: str):
    t = asyncio.create_task(_run_in_background(run_id))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


@router.post("/projects/{pid}/runs")
async def start_run(pid: str, body: RunIn, wait: bool = False, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    project_access(db, pid, user, "editor")
    if body.workflow not in WORKFLOWS:
        raise HTTPException(400, f"Unknown workflow. Available: {', '.join(WORKFLOWS)}")
    if body.workflow == "research" and not (body.input.get("question") or "").strip():
        raise HTTPException(400, "input.question is required")
    run = TaskRun(project_id=pid, workflow=body.workflow, input=body.input, created_by=user.id)
    db.add(run)
    db.commit()
    if wait:
        await run_workflow(db, run.id)
        db.refresh(run)
    else:
        _start(run.id)
    return task_out(run)


@router.get("/runs/{rid}")
def get_run(rid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(TaskRun, rid) or _404()
    project_access(db, r.project_id, user)
    return task_out(r)


@router.post("/runs/{rid}/approve")
async def approve_run(rid: str, body: dict | None = None, wait: bool = False, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Continue a paused run. Body may carry edits, e.g. {"plan": {"queries": [...], "category": "web"}}."""
    r = db.get(TaskRun, rid) or _404()
    project_access(db, r.project_id, user, "editor")
    if r.status != "awaiting_approval":
        raise HTTPException(409, f"Run is {r.status}, not awaiting approval")
    approve(db, r, body or {})
    if wait:
        await run_workflow(db, r.id)
        db.refresh(r)
    else:
        _start(r.id)
    return task_out(r)


@router.get("/projects/{pid}/runs")
def runs(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_access(db, pid, user)
    rows = db.query(TaskRun).filter_by(project_id=pid).order_by(TaskRun.created_at.desc()).limit(100).all()
    return [{"id": r.id, "workflow": r.workflow, "status": r.status, "question": r.input.get("question"),
             "created_at": r.created_at, "document_id": r.state.get("document_id")} for r in rows]


@router.get("/projects/{pid}/timeline")
def timeline(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything that happened in the project, newest first."""
    project_access(db, pid, user)
    ev = [{"at": r.created_at, "type": "search", "id": r.id, "label": r.query}
          for r in db.query(SearchRun).filter_by(project_id=pid).all()]
    ev += [{"at": s.fetched_at, "type": "fetch", "id": s.id, "label": f"{src.title or src.url} ({s.fetcher})"}
           for src in db.query(Source).filter_by(project_id=pid).all() for s in src.snapshots]
    ev += [{"at": r.created_at, "type": "run", "id": r.id, "label": f"{r.workflow}: {r.input.get('question', '')} [{r.status}]"}
           for r in db.query(TaskRun).filter_by(project_id=pid).all()]
    from ..models import Document  # local import keeps the router module light

    for d in db.query(Document).filter_by(project_id=pid).all():
        ev += [{"at": rv.created_at, "type": "edit", "id": d.id, "label": f"{d.title} rev {rv.rev} by {rv.author}"}
               for rv in db.query(Revision).filter_by(document_id=d.id).all()]
    return sorted(ev, key=lambda e: e["at"], reverse=True)[:300]


def _404():
    raise HTTPException(404, "Not found")

