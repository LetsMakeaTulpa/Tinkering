"""Fetch a URL with the best available method, guard it, extract it, archive it.

Methods:  direct (httpx + trafilatura) · tor (.onion, via SOCKS) · firecrawl / jina / apify (JS-heavy or
bot-protected pages) · wayback (historical snapshot). `auto` = tor for .onion, otherwise direct, falling back
to firecrawl → jina → apify when the direct fetch fails or comes back nearly empty.
"""

from urllib.parse import quote, urljoin

import httpx
from sqlalchemy.orm import Session

from ..archive import archive_content
from ..config import settings
from ..models import Project
from ..netguard import Blocked, check_url, is_onion
from .extract import extract

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def _guard(project: Project, url: str) -> str:
    return check_url(url, mode=project.mode, allowed_domains=project.allowed_domains, allow_tor=project.allow_tor,
                     tor_proxy=settings.tor_proxy)


async def _direct(project: Project, url: str, via: str) -> dict:
    proxy = settings.tor_proxy if via == "tor" else None
    async with httpx.AsyncClient(timeout=settings.fetch_timeout, proxy=proxy, follow_redirects=False,
                                 headers={"User-Agent": UA}) as client:
        current = url
        for _ in range(6):  # follow redirects by hand so every hop passes the guard
            async with client.stream("GET", current) as r:
                if r.is_redirect and r.headers.get("location"):
                    current = urljoin(current, r.headers["location"])
                    _guard(project, current)
                    continue
                body = b""
                async for part in r.aiter_bytes():
                    body += part
                    if len(body) > settings.max_fetch_bytes:
                        raise ValueError(f"page larger than {settings.max_fetch_bytes} bytes")
                ct = r.headers.get("content-type", "")
                title, md, meta = extract(body, ct, current)
                raw = "" if meta.get("format") == "pdf" else body.decode("utf-8", errors="replace")
                return {"title": title, "content": md, "raw": raw, "final_url": current, "status": r.status_code,
                        "content_type": ct, "meta": meta, "fetcher": via}
        raise ValueError("too many redirects")


async def _firecrawl(url: str) -> dict:
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post("https://api.firecrawl.dev/v2/scrape", json={"url": url, "formats": ["markdown"]},
                         headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"})
        r.raise_for_status()
        d = r.json().get("data", {})
        md = d.get("metadata", {})
        return {"title": md.get("title", ""), "content": d.get("markdown", ""), "final_url": md.get("sourceURL", url),
                "status": md.get("statusCode"), "content_type": "text/markdown", "meta": md, "fetcher": "firecrawl"}


async def _jina(url: str) -> dict:
    headers = {"Accept": "application/json"}
    if settings.jina_api_key:
        headers["Authorization"] = f"Bearer {settings.jina_api_key}"
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.get("https://r.jina.ai/" + url, headers=headers)
        r.raise_for_status()
        d = r.json().get("data", {})
        return {"title": d.get("title", ""), "content": d.get("content", ""), "final_url": d.get("url", url),
                "status": 200, "content_type": "text/markdown", "meta": {}, "fetcher": "jina"}


async def _apify(url: str) -> dict:
    async with httpx.AsyncClient(timeout=150) as c:
        r = await c.post(f"https://api.apify.com/v2/acts/{settings.apify_fetch_actor}/run-sync-get-dataset-items",
                         params={"token": settings.apify_token, "timeout": 120},
                         json={"query": url, "maxResults": 1, "outputFormats": ["markdown"]})
        r.raise_for_status()
        items = r.json()
        if not items:
            raise ValueError("apify returned nothing")
        x = items[0]
        md = x.get("metadata") or {}
        return {"title": md.get("title", ""), "content": x.get("markdown") or x.get("text") or "",
                "final_url": md.get("url", url), "status": (x.get("crawl") or {}).get("httpStatusCode"),
                "content_type": "text/markdown", "meta": md, "fetcher": "apify"}


async def wayback_url(url: str, timestamp: str = "") -> str | None:
    """Closest Internet Archive snapshot URL (timestamp YYYYMMDD[hhmmss]; empty = latest)."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get("https://archive.org/wayback/available", params={"url": url, "timestamp": timestamp})
        r.raise_for_status()
        closest = (r.json().get("archived_snapshots") or {}).get("closest") or {}
        return closest.get("url") if closest.get("available") else None


async def fetch_and_archive(db: Session, project: Project, url: str, method: str = "auto", wayback_ts: str = ""):
    """Returns (source, snapshot). Failures are archived too (snapshot.error) so the attempt is on record."""
    try:
        via = _guard(project, url)
        if method == "wayback":
            snap_url = await wayback_url(url, wayback_ts)
            if not snap_url:
                raise ValueError("no Wayback Machine snapshot for this URL")
            _guard(project, snap_url)
            result = await _direct(project, snap_url, "direct")
            result["fetcher"], result["meta"]["wayback_url"] = "wayback", snap_url
        elif method in ("auto", "direct", "tor"):
            try:
                result = await _direct(project, url, via)
                if method == "auto" and via == "direct" and project.mode != "scoped" and len(result["content"].strip()) < 200:
                    result = await _fallback(url) or result  # likely a JS-rendered page
            except (httpx.HTTPError, ValueError):
                if method != "auto" or via == "tor" or project.mode == "scoped":
                    raise
                result = await _fallback(url)
                if not result:
                    raise
        else:
            if project.mode == "scoped" or is_onion(url):
                raise Blocked("third-party fetchers are disabled for scoped projects and onion addresses")
            result = await {"firecrawl": _firecrawl, "jina": _jina, "apify": _apify}[method](url)
    except Exception as e:  # noqa: BLE001 — record any failure with the source
        src, snap = archive_content(db, project.id, url, "", "", fetcher=method, error=f"{type(e).__name__}: {e}",
                                    content_type="")
        db.commit()
        return src, snap
    src, snap = archive_content(db, project.id, url, result["title"], result["content"], fetcher=result["fetcher"],
                                final_url=result["final_url"], raw=result.get("raw", ""), http_status=result["status"],
                                content_type=result["content_type"],
                                source_type="onion" if is_onion(url) else "web", meta=result["meta"])
    db.commit()
    return src, snap


async def _fallback(url: str) -> dict | None:
    for enabled, fn in ((settings.firecrawl_api_key, _firecrawl), (True, _jina), (settings.apify_token, _apify)):
        if enabled:
            try:
                r = await fn(url)
                if r["content"].strip():
                    return r
            except Exception:  # noqa: BLE001 — try the next fetcher
                continue
    return None
