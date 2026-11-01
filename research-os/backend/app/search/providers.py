"""Search provider adapters. Each one maps the provider's API onto `Hit`.

API shapes were checked against each provider's docs in Nov 2026; providers change their APIs, so if one
starts returning errors, its `provider_status` entry on the search run will say why.
"""

from ..config import settings
from .base import Hit, Provider, SearchRequest, render_query


class Exa(Provider):
    name = "exa"
    categories = {"web", "news", "paper"}
    supports_operators = False

    def enabled(self):
        return bool(settings.exa_api_key)

    async def search(self, req, client):
        body = {"query": req.query, "type": "auto", "numResults": req.limit,
                "contents": {"text": {"maxCharacters": 20000}, "highlights": True}}
        if req.site:
            body["includeDomains"] = [req.site]
        if req.after:
            body["startPublishedDate"] = req.after
        if req.before:
            body["endPublishedDate"] = req.before
        if req.category == "news":
            body["category"] = "news"
        elif req.category == "paper":
            body["category"] = "research paper"
        r = await client.post("https://api.exa.ai/search", json=body, headers={"x-api-key": settings.exa_api_key})
        r.raise_for_status()
        out = []
        for i, x in enumerate(r.json().get("results", []), 1):
            snippet = " … ".join(x.get("highlights") or []) or (x.get("text") or "")[:300]
            out.append(Hit(x.get("title") or x["url"], x["url"], snippet, self.name, i,
                           "paper" if req.category == "paper" else "web", x.get("publishedDate"), x.get("score"),
                           x.get("text"), {"author": x.get("author")}))
        return out


class SearXNG(Provider):
    """Your own metasearch instance: no tracking, safesearch off, and the 'onions' category (Ahmia, Torch)
    when the instance routes through Tor. Needs `json` enabled in the instance's search.formats."""

    name = "searxng"
    categories = {"web", "news", "onion", "paper"}

    def enabled(self):
        return bool(settings.searxng_url)

    async def search(self, req, client):
        cat = {"web": "general", "onion": "onions", "paper": "science", "news": "news"}[req.category]
        params = {"q": render_query(req), "format": "json", "safesearch": 0, "categories": cat}
        r = await client.get(settings.searxng_url.rstrip("/") + "/search", params=params,
                             timeout=60 if req.category == "onion" else 20)
        r.raise_for_status()
        data = r.json()
        out = []
        for i, x in enumerate(data.get("results", [])[: req.limit * 2], 1):
            st = "onion" if ".onion" in (x.get("url") or "") else ("paper" if req.category == "paper" else "web")
            out.append(Hit(x.get("title") or x["url"], x["url"], x.get("content") or "", self.name, i, st,
                           x.get("publishedDate"), x.get("score"), None, {"engines": x.get("engines", [])}))
        return out


class Tavily(Provider):
    name = "tavily"
    categories = {"web", "news"}

    def enabled(self):
        return bool(settings.tavily_api_key)

    async def search(self, req, client):
        body = {"query": render_query(req, operators=False), "max_results": req.limit, "search_depth": "advanced",
                "topic": "news" if req.category == "news" else "general"}
        if req.site:
            body["include_domains"] = [req.site]
        if req.after:
            body["start_date"] = req.after
        if req.before:
            body["end_date"] = req.before
        r = await client.post("https://api.tavily.com/search", json=body,
                              headers={"Authorization": f"Bearer {settings.tavily_api_key}"})
        r.raise_for_status()
        return [Hit(x.get("title") or x["url"], x["url"], x.get("content") or "", self.name, i, "web",
                    x.get("published_date"), x.get("score"))
                for i, x in enumerate(r.json().get("results", []), 1)]


class Brave(Provider):
    name = "brave"

    def enabled(self):
        return bool(settings.brave_api_key)

    async def search(self, req, client):
        r = await client.get("https://api.search.brave.com/res/v1/web/search",
                             params={"q": render_query(req), "count": min(req.limit, 20), "safesearch": "off"},
                             headers={"X-Subscription-Token": settings.brave_api_key, "Accept": "application/json"})
        r.raise_for_status()
        res = (r.json().get("web") or {}).get("results", [])
        return [Hit(x.get("title") or x["url"], x["url"], x.get("description") or "", self.name, i, "web",
                    x.get("page_age") or x.get("age")) for i, x in enumerate(res, 1)]


class Firecrawl(Provider):
    name = "firecrawl"

    def enabled(self):
        return bool(settings.firecrawl_api_key)

    async def search(self, req, client):
        body = {"query": render_query(req), "limit": req.limit,
                "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True}}
        r = await client.post("https://api.firecrawl.dev/v2/search", json=body, timeout=90,
                              headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"})
        r.raise_for_status()
        data = r.json().get("data")
        items = data.get("web", []) if isinstance(data, dict) else (data or [])  # v2 groups by type; v1 was a list
        out = []
        for i, x in enumerate(items, 1):
            md = x.get("metadata") or {}
            url = x.get("url") or md.get("sourceURL") or md.get("url")
            if url:
                out.append(Hit(x.get("title") or md.get("title") or url, url, x.get("description") or "", self.name, i,
                               "web", None, None, x.get("markdown")))
        return out


class Apify(Provider):
    """Runs an Apify Actor synchronously (default: apify~rag-web-browser, which searches Google and returns
    page markdown). Swap APIFY_SEARCH_ACTOR for any Actor that takes {query, maxResults}."""

    name = "apify"

    def enabled(self):
        return bool(settings.apify_token)

    async def search(self, req, client):
        url = f"https://api.apify.com/v2/acts/{settings.apify_search_actor}/run-sync-get-dataset-items"
        r = await client.post(url, params={"token": settings.apify_token, "timeout": 120}, timeout=150,
                              json={"query": render_query(req), "maxResults": req.limit, "outputFormats": ["markdown"]})
        r.raise_for_status()
        out = []
        for i, x in enumerate(r.json(), 1):
            sr, md = x.get("searchResult") or {}, x.get("metadata") or {}
            url = sr.get("url") or md.get("url") or x.get("url")
            if url:
                out.append(Hit(sr.get("title") or md.get("title") or url, url,
                               sr.get("description") or md.get("description") or "", self.name, i, "web",
                               None, None, x.get("markdown") or x.get("text")))
        return out


class OpenAlex(Provider):
    """Scholarly works (free, no key). Example of a non-web provider plugging into the same interface."""

    name = "openalex"
    categories = {"paper"}
    supports_operators = False

    async def search(self, req, client):
        params = {"search": req.query, "per-page": req.limit}
        if settings.openalex_mailto:
            params["mailto"] = settings.openalex_mailto
        filters = []
        if req.after:
            filters.append(f"from_publication_date:{req.after}")
        if req.before:
            filters.append(f"to_publication_date:{req.before}")
        if filters:
            params["filter"] = ",".join(filters)
        r = await client.get("https://api.openalex.org/works", params=params)
        r.raise_for_status()
        out = []
        for i, w in enumerate(r.json().get("results", []), 1):
            loc = w.get("primary_location") or {}
            url = loc.get("landing_page_url") or w.get("doi") or w.get("id")
            out.append(Hit(w.get("display_name") or url, url, _abstract(w.get("abstract_inverted_index")), self.name, i,
                           "paper", w.get("publication_date"), None, None,
                           {"doi": w.get("doi"), "openalex_id": w.get("id"), "cited_by": w.get("cited_by_count")}))
        return out


class Perplexity(Provider):
    """Answer engine: we keep its cited sources as hits (and its answer text in meta) so every claim stays traceable."""

    name = "perplexity"
    categories = {"web", "news", "paper"}
    supports_operators = False

    def enabled(self):
        return bool(settings.perplexity_api_key)

    async def search(self, req, client):
        body = {"model": settings.perplexity_model, "messages": [{"role": "user", "content": render_query(req, False)}]}
        if req.site:
            body["search_domain_filter"] = [req.site]
        r = await client.post("https://api.perplexity.ai/chat/completions", json=body, timeout=90,
                              headers={"Authorization": f"Bearer {settings.perplexity_api_key}"})
        r.raise_for_status()
        data = r.json()
        answer = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        results = data.get("search_results") or [{"url": u, "title": u} for u in data.get("citations", [])]
        return [Hit(x.get("title") or x["url"], x["url"], x.get("snippet") or "", self.name, i, "web", x.get("date"),
                    None, None, {"answer": answer[:2000]} if i == 1 else {}) for i, x in enumerate(results, 1)]


class SemanticScholar(Provider):
    name = "semanticscholar"
    categories = {"paper"}
    supports_operators = False

    async def search(self, req, client):
        params = {"query": req.query, "limit": req.limit,
                  "fields": "title,url,abstract,year,publicationDate,externalIds,citationCount,openAccessPdf"}
        if req.after or req.before:
            params["publicationDateOrYear"] = f"{req.after or ''}:{req.before or ''}"
        headers = {"x-api-key": settings.semantic_scholar_api_key} if settings.semantic_scholar_api_key else {}
        r = await client.get("https://api.semanticscholar.org/graph/v1/paper/search", params=params, headers=headers)
        r.raise_for_status()
        out = []
        for i, p in enumerate(r.json().get("data", []), 1):
            pdf = (p.get("openAccessPdf") or {}).get("url")
            out.append(Hit(p.get("title") or p["url"], pdf or p["url"], (p.get("abstract") or "")[:600], self.name, i,
                           "paper", p.get("publicationDate") or str(p.get("year") or ""), None, None,
                           {"doi": (p.get("externalIds") or {}).get("DOI"), "cited_by": p.get("citationCount"),
                            "s2_url": p["url"]}))
        return out


def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words = sorted((pos, word) for word, positions in inv.items() for pos in positions)
    return " ".join(w for _, w in words)[:600]


REGISTRY: dict[str, Provider] = {p.name: p for p in (Exa(), SearXNG(), Tavily(), Brave(), Firecrawl(), Apify(), Perplexity(), OpenAlex(), SemanticScholar())}


def available() -> list[dict]:
    return [{"name": p.name, "enabled": p.enabled(), "categories": sorted(p.categories)} for p in REGISTRY.values()]
