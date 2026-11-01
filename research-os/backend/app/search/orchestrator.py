"""Runs several providers at once, merges their lists, removes duplicates, ranks, and saves everything."""

import asyncio

import httpx
from sqlalchemy.orm import Session

from ..archive import archive_content
from ..config import settings
from ..models import Project, SearchResult, SearchRun
from .base import Hit, SearchRequest, canonical_url
from .providers import REGISTRY

RRF_K = 60  # reciprocal-rank-fusion constant; higher = flatter blend between providers


def pick_providers(project: Project, requested: list[str] | None, category: str) -> list[str]:
    names = requested or project.settings.get("providers") or settings.default_providers
    if category == "paper" and not requested:
        names = list(dict.fromkeys([*names, "openalex"]))
    return [n for n in names if n in REGISTRY and REGISTRY[n].enabled() and category in REGISTRY[n].categories]


async def _one(name: str, req: SearchRequest, client) -> tuple[str, list[Hit] | Exception]:
    try:
        return name, await REGISTRY[name].search(req, client)
    except Exception as e:  # one provider failing must not sink the whole search
        return name, e


def merge(results: dict[str, list[Hit]], weights: dict[str, float] | None = None) -> list[dict]:
    """Reciprocal rank fusion: a URL ranked high by several providers beats one ranked high by a single provider."""
    weights = weights or {}
    merged: dict[str, dict] = {}
    for provider, hits in results.items():
        w = weights.get(provider, 1.0)
        for h in hits:
            key = canonical_url(h.url)
            m = merged.setdefault(key, {"canonical_url": key, "url": h.url, "title": h.title, "snippet": h.snippet,
                                        "providers": [], "score": 0.0, "source_type": h.source_type,
                                        "published_at": h.published_at, "meta": {}, "content": None,
                                        "content_provider": None})
            m["providers"].append(provider)
            m["score"] += w / (RRF_K + h.rank)
            if len(h.snippet) > len(m["snippet"]):
                m["snippet"] = h.snippet
            m["published_at"] = m["published_at"] or h.published_at
            m["meta"].update({f"{provider}_{k}": v for k, v in h.meta.items() if v is not None})
            if h.content and not m["content"]:
                m["content"], m["content_provider"] = h.content, provider
    return sorted(merged.values(), key=lambda m: m["score"], reverse=True)


async def run_search(db: Session, project: Project, req: SearchRequest, providers: list[str] | None = None,
                     user_id: str | None = None, task_run_id: str | None = None) -> SearchRun:
    names = pick_providers(project, providers, req.category)
    run = SearchRun(project_id=project.id, query=req.query, params={**req.__dict__, "providers": names},
                    created_by=user_id, task_run_id=task_run_id)
    if not names:
        run.provider_status = {"_": "no enabled provider for this category — add an API key or SEARXNG_URL"}
        db.add(run)
        db.commit()
        return run
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        pairs = await asyncio.gather(*(_one(n, req, client) for n in names))
    ok = {n: r for n, r in pairs if not isinstance(r, Exception)}
    run.provider_status = {n: (f"{len(r)} results" if not isinstance(r, Exception) else f"error: {r}") for n, r in pairs}
    db.add(run)
    db.flush()
    for rank, m in enumerate(merge(ok, project.settings.get("provider_weights"))[: req.limit * 2], 1):
        res = SearchResult(run_id=run.id, project_id=project.id, title=m["title"], url=m["url"],
                           canonical_url=m["canonical_url"], snippet=m["snippet"], providers=m["providers"], rank=rank,
                           score=round(m["score"], 6), source_type=m["source_type"], published_at=m["published_at"],
                           meta=m["meta"])
        if m["content"]:  # provider already gave us the page text: archive it now, with provenance
            src, _ = archive_content(db, project.id, m["url"], m["title"], m["content"], fetcher=m["content_provider"],
                                     source_type=m["source_type"], meta={"via_search_run": run.id})
            res.source_id = src.id
        db.add(res)
    db.commit()
    return run
