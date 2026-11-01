"""Find the most relevant stored passages in a project (web snapshots and your own documents).

Keyword scoring (BM25-style) always works. If EMBEDDING_MODEL is set, semantic similarity is blended in.
Phase 2 swaps the Python loops for Postgres full-text search + pgvector; the function signature stays the same.
"""

import math
import re
from collections import Counter

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..llm.router import _openai_compatible
from ..models import Chunk

WORD = re.compile(r"[\w\-]{2,}", re.UNICODE)
STOP = set("the a an and or of to in on for is are was were be by with as at from that this it its into than then".split())


def terms(text: str) -> list[str]:
    return [w for w in (m.lower() for m in WORD.findall(text)) if w not in STOP]


async def embed(texts: list[str]) -> list[list[float]] | None:
    if not settings.embedding_model:
        return None
    provider, _, model = settings.embedding_model.partition(":")
    base, key = _openai_compatible(provider) or (None, None)
    if not base:
        return None
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{base.rstrip('/')}/embeddings", json={"model": model, "input": texts},
                         headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def search_memory(db: Session, project_id: str, query: str, k: int = 8,
                        source_ids: list[str] | None = None) -> list[tuple[Chunk, float]]:
    q_terms = list(dict.fromkeys(terms(query)))[:12]
    if not q_terms:
        return []
    qry = db.query(Chunk).filter(Chunk.project_id == project_id)
    if source_ids is not None:
        qry = qry.filter(Chunk.source_id.in_(source_ids))
    qry = qry.filter(or_(*[Chunk.text.ilike(f"%{t}%") for t in q_terms]))
    cands = qry.limit(2000).all()
    if not cands:
        return []
    n = len(cands)
    docs = [Counter(terms(c.text)) for c in cands]
    avg = sum(sum(d.values()) for d in docs) / n or 1
    df = {t: sum(1 for d in docs if t in d) for t in q_terms}
    scored = []
    for c, d in zip(cands, docs):
        length = sum(d.values()) or 1
        s = 0.0
        for t in q_terms:
            tf = d.get(t, 0)
            if tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / avg))
        scored.append([c, s])
    top = sorted(scored, key=lambda x: x[1], reverse=True)[: k * 4]
    try:
        qv = await embed([query])
    except httpx.HTTPError:
        qv = None
    if qv:
        missing = [x[0] for x in top if not x[0].embedding]
        if missing:
            vecs = await embed([c.text for c in missing])
            for c, v in zip(missing, vecs or []):
                c.embedding = v
            db.commit()
        best = max(x[1] for x in top) or 1
        for x in top:
            x[1] = 0.5 * (x[1] / best) + 0.5 * _cos(qv[0], x[0].embedding or [])
        top.sort(key=lambda x: x[1], reverse=True)
    return [(c, round(s, 4)) for c, s in top[:k]]
