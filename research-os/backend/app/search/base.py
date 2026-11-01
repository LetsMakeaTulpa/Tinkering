"""The contract every search provider follows. Add a provider = write one class with `search()`."""

from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid", "msclkid"}


@dataclass
class SearchRequest:
    query: str
    exact: bool = False            # wrap the query in quotes
    site: str | None = None        # restrict to a domain
    filetype: str | None = None    # pdf, docx, …
    after: str | None = None       # YYYY-MM-DD
    before: str | None = None      # YYYY-MM-DD
    category: str = "web"          # web | onion | paper | news
    limit: int = 10
    extra: str = ""                # raw dork text appended as-is (e.g. 'intitle:"index of" -github')


@dataclass
class Hit:
    """Normalized search result — the same shape no matter which provider produced it."""

    title: str
    url: str
    snippet: str
    provider: str
    rank: int                      # position within this provider's list (1 = top)
    source_type: str = "web"
    published_at: str | None = None
    score: float | None = None     # provider's own score, if any
    content: str | None = None     # full page text when the provider returns it (Exa, Firecrawl, Apify)
    meta: dict = field(default_factory=dict)


class Provider:
    name: str = "base"
    categories: set[str] = {"web"}
    supports_operators: bool = True  # understands site:, filetype:, quotes

    def enabled(self) -> bool:
        return True

    async def search(self, req: SearchRequest, client) -> list[Hit]:
        raise NotImplementedError


def render_query(req: SearchRequest, operators: bool = True) -> str:
    """Turn structured options into a query string ("dorks") for providers that parse operators."""
    q = f'"{req.query}"' if req.exact and not req.query.startswith('"') else req.query
    if operators:
        if req.site:
            q += f" site:{req.site}"
        if req.filetype:
            q += f" filetype:{req.filetype}"
        if req.after:
            q += f" after:{req.after}"
        if req.before:
            q += f" before:{req.before}"
    if req.extra:
        q += " " + req.extra
    return q.strip()


def canonical_url(url: str) -> str:
    """Same page → same string, so results from different providers merge."""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if p.port and p.port not in (80, 443):
        host += f":{p.port}"
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in TRACKING))
    path = p.path.rstrip("/") or "/"
    scheme = "https" if p.scheme in ("http", "https") else p.scheme
    return urlunsplit((scheme, host, path, query, ""))
