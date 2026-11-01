# Research OS: spec, architecture and roadmap

This document turns the original brief into an engineering plan. It covers what v0.1 does, how it's built, and what comes next and in what order.

## 1. Product in one paragraph

A workspace where each **project** holds everything about one line of research: the searches you ran, every page you read (archived and dated), your notes, the AI's reports, and a log of every model call. The AI acts as the **facilitator, analyst and archivist**. It plans searches, reads sources and writes reports, and every sentence it writes points back to an archived source you can open. It is a research tool with memory and provenance, not a chatbot.

## 2. Principles

1. **Provenance first.** Nothing enters a report without a path back to a source, the snapshot of it and the passage used.
2. **Archive, don't just link.** Pages change and disappear, so every fetch is stored as a hashed, dated snapshot.
3. **Providers are plugins.** Search engines, fetchers and models each sit behind one small interface. Adding one means adding one class.
4. **Smallest thing that proves the loop.** Build the core loop first; everything else is an extension.
5. **Policy built in from day one.** Network guard, per-project scope, roles and Tor opt-in all exist in v0.1.

## 3. Scope

| Phase | Status | Contents |
|---|---|---|
| **0.1 MVP (this commit)** | Built and tested | Projects/roles/sharing · 9 search providers + SearXNG onion engines · 7 fetch methods · archive with snapshots · notes with revisions/diffs · model router with fallback and call log · 6-agent research workflow with human approval · citations + critic · web UI · Docker Compose |
| 1 Hardening | Next | Alembic migrations · worker queue (arq + Redis) · Playwright fetcher for JS pages · rate limits and per-provider quotas · streaming run progress (SSE) |
| 2 Memory | | pgvector embeddings + Postgres full-text search · import chat exports (ChatGPT, Claude, Gemini, OpenRouter, Markdown/JSON) · entity extraction ("claims" table) · cross-project search |
| 3 Scholarly + history | | Crossref, arXiv, PubMed/Europe PMC, CORE adapters · citation graph (OpenAlex) · literature-review workflow · Wayback CDX timelines and page diffs over time · Common Crawl index |
| 4 OSINT + security research | | Domain/IP/certificate enrichment (crt.sh, Shodan, Censys, SecurityTrails, urlscan, VirusTotal) · import results from self-hosted tools (SpiderFoot, theHarvester, Recon-ng, Nmap XML, ZAP) · all of it behind scoped projects with asset allowlists and an audit log |
| 5 Collaboration | | Comments and annotations on sources and passages · real-time co-editing · SSO · per-project export (ZIP of Markdown + sources) |

## 4. Architecture

```
frontend/  Next.js (App Router, TypeScript) ── talks only to /api
backend/   FastAPI
  app/api/          HTTP routes (thin: validate → call a module → return JSON)
  app/auth.py       bearer tokens, roles: viewer < editor < owner
  app/netguard.py   URL policy, checked before every fetch and every redirect hop
  app/search/       base.py (SearchRequest, Hit, Provider) · providers.py · orchestrator.py (parallel + RRF merge)
  app/fetch/        fetcher.py (direct/tor/firecrawl/jina/apify/wayback) · extract.py (trafilatura, pypdf)
  app/archive.py    Source → Snapshot (hash-deduped) → Chunks
  app/memory/       chunker.py · retrieve.py (BM25-style keyword + optional embeddings)
  app/llm/          router.py (routes.yaml → fallback chain → ModelCall log) · routes.yaml
  app/workflows/    engine.py (durable step runner, pause/approve) · research.py (6 agents)
infra      Postgres (pgvector image) · SearXNG · Tor (SOCKS) · optional Ollama
```

**Why these choices.** FastAPI and SQLAlchemy keep the backend readable for beginners while scaling well. Postgres plus pgvector means one database instead of Postgres + Qdrant until you have millions of passages. SQLite works for local development and tests with the same code. The workflow engine is about 80 lines: each step's output is saved, so runs can pause for approval and skip finished steps on restart. A queue or Temporal can replace it later without touching the agents.

### The core loop

```
question ─▶ planner (model: plan) ─▶ [optional human edit of queries]
         ─▶ searcher: each query → enabled providers in parallel → merge (reciprocal rank fusion) → saved
         ─▶ fetcher: top N unseen URLs → netguard → fetch → clean Markdown → Snapshot + Chunks
              (pages that Exa/Firecrawl/Apify already returned in full are archived without refetching)
         ─▶ analyst: best passages from this run + earlier project memory → numbered <source> blocks
              → model writes an answer with [S#] after every factual sentence
         ─▶ critic: deterministic check (unknown markers, uncited paragraphs) → one model revision if needed
         ─▶ archiver: report saved as a Document revision + Citation rows (marker → snapshot → passage)
```

Web text goes to the model inside `<source>` tags, with an instruction to treat it as evidence, not as instructions. This reduces prompt injection from hostile pages but doesn't eliminate it. Phase 1 adds a check that flags pages containing instruction-like text.

## 5. Data model

| Table | Key columns | Purpose |
|---|---|---|
| users | email, token_hash | Accounts (tokens stored as SHA-256) |
| projects | mode (standard/scoped), allowed_domains, allow_tor, settings, share_token | Workspace and its policy |
| project_members | project_id, user_id, role | Access control |
| search_runs | query, params, provider_status, task_run_id | One search request and how each provider fared |
| search_results | url, canonical_url, providers[], rank, score, source_type, source_id | Merged, ranked hits |
| sources | canonical_url (unique per project), title, source_type, trust, tags | One URL in the archive |
| snapshots | fetched_at, fetcher, final_url, http_status, raw, content (Markdown), content_hash, meta, error | Each fetch, kept forever; failures are recorded too |
| chunks | snapshot_id or document_id, text, embedding | Retrieval units for memory |
| documents / revisions | kind, title, current_rev / rev, content, author (user or model), task_run_id | Notes and reports with full history |
| citations | revision_id, marker, source_id, snapshot_id, document_id, chunk_id, quote | Provenance of every [S#] |
| model_calls | task_type, provider, model, messages, response, tokens, latency, status, error | Every model call, including failed attempts |
| task_runs / task_steps | workflow, input, state, status / agent, output, timings | Multi-agent runs, step by step |

Phase 2 additions: `claims` (statement, confidence, supporting/contradicting citations), `entities` + `entity_mentions`, `imported_conversations` + `imported_messages`, `annotations`, and `audit_log` (required before phase 4).

## 6. API (v0.1)

All routes are under `/api`, with header `Authorization: Bearer <token>`. Interactive docs are at `/docs`.

| Method | Path | What it does |
|---|---|---|
| GET | /me · /providers · /models | Who am I; which search providers are configured; model routes and which providers have keys |
| POST | /users | Create a user (returns their token once) |
| GET/POST | /projects | List / create |
| GET/PATCH/DELETE | /projects/{id} | Read / change policy (owner) / delete |
| POST | /projects/{id}/members | Add or change a member's role |
| POST/DELETE | /projects/{id}/share | Create or revoke the read-only link |
| GET | /shared/{token} | Public read-only view (no auth) |
| POST | /projects/{id}/search | Run a search (providers, exact, site, filetype, after, before, category web/news/paper/onion, extra operators) |
| GET | /projects/{id}/searches · /searches/{id} | Search history and results |
| POST | /projects/{id}/fetch | Fetch and archive a URL (`method`: auto/direct/tor/firecrawl/jina/apify/wayback) |
| GET | /projects/{id}/sources · /sources/{id} · /snapshots/{id}?raw=1 | Browse the archive |
| PATCH | /sources/{id} | Set trust and tags |
| GET | /projects/{id}/memory?q= | Search project memory (web passages and notes) |
| GET/POST | /projects/{id}/documents | List / create notes |
| GET/PUT/DELETE | /documents/{id} | Read (with citations) / save a new revision (`base_rev` for conflict detection) / delete |
| GET | /documents/{id}/revisions · /documents/{id}/diff?a=&b= | History and unified diff |
| POST | /projects/{id}/llm | Direct model call through the router (`task_type`, optional `model`) |
| GET | /projects/{id}/model-calls | Model call log |
| POST | /projects/{id}/runs[?wait=true] | Start a workflow; `input`: question, providers, category, queries, require_approval, max_fetch, model_plan, model_write |
| GET | /runs/{id} · /projects/{id}/runs | Run status with every step's output |
| POST | /runs/{id}/approve | Resume a paused run, optionally with edits such as `{"plan": {"queries": [...]}}` |
| GET | /projects/{id}/timeline | Searches, fetches, runs and edits, newest first |

## 7. Models

`routes.yaml` maps task types (plan, research, synthesis, writing, extraction, validation, classify, coding) to an ordered list of `provider:model` entries. The router tries each in turn and logs every attempt.

- **Default:** `featherless:darkc0de/XORTRON-RICO-v3` for writing and analysis, and `featherless:darkc0de/XORTRON-AgentRICO` for planning and agent steps.
  - Both exist on Hugging Face. I couldn't confirm they're live on Featherless.
  - Featherless says it auto-onboards Hugging Face models with 100+ downloads. Confirm on featherless.ai/models.
- **Cost- and quality-aware routing (phase 1):** add `cost` and `quality` fields per model in routes.yaml, and have the router pick the cheapest model that meets a task's minimum quality.
- **Alternative:** if you'd rather not maintain adapters, LiteLLM can replace `llm/router.py`'s `_call`. The routing and logging stay the same.

## 8. Search and fetch providers

### Built in v0.1

| Provider | Kind | Notes |
|---|---|---|
| Exa | Neural search + full text | Main quality provider; returns page text so no refetch is needed |
| SearXNG | Self-hosted metasearch | SafeSearch off; the `onions` category uses Ahmia + Torch through Tor; also gives access to DuckDuckGo, Startpage, Qwant, Mojeek, Google Scholar, GitHub, Reddit and more as SearXNG engines |
| Tavily, Brave | Search APIs | Brave with `safesearch=off` |
| Firecrawl | Search + scrape | Also a fetcher for JS-heavy pages |
| Apify | Any Actor | Default `apify~rag-web-browser`; set `APIFY_SEARCH_ACTOR` / `APIFY_FETCH_ACTOR` to use other Actors |
| Perplexity | Answer engine | Its cited sources become results; its answer is kept in metadata |
| OpenAlex, Semantic Scholar | Scholarly | No key needed (Semantic Scholar is faster with one) |
| Jina Reader, Wayback Machine, Tor | Fetchers | Clean page text, historical snapshots, .onion |

### Your tool list, sorted by how it can plug in

**Has a usable API: add as adapters in phases 1–3.** You.com, Kagi (Search + FastGPT), Mojeek, Crossref, arXiv, PubMed / Europe PMC, CORE, Common Crawl index, Internet Archive (CDX/Wayback), GitHub search, Stack Exchange, Reddit, YouTube Data API, HathiTrust, Library of Congress, Europeana, Kaggle, Data.gov.

**Reachable through SearXNG today, no separate adapter needed.** DuckDuckGo, Startpage, Qwant, Mojeek, Yandex, Baidu, Google Scholar, GitHub, Stack Overflow, Reddit, YouTube, Ahmia, Torch.

**Web apps without a public search API, as far as I know.** Phind, ThinkAny, Komo, Felo, Devv, Duck.ai, Deepfind, Liner, Heuristica, WebPilot, Elicit, Consensus.
- Consensus and Elicit may offer API or MCP access on paid plans. Check before planning around them.
- **Morphic, Scira and Lepton Search are open source.** They're worth reading for UI ideas; their search back ends are mostly SearXNG, Exa or Tavily, which this app already covers.

**OSINT and security sources (phase 4, scoped projects only).**
- Have APIs: Shodan, Censys, ZoomEye, VirusTotal, Hybrid Analysis, urlscan, SecurityTrails, crt.sh, BuiltWith, Hunter.io, Have I Been Pwned.
- Self-hosted tools whose output we import rather than drive: SpiderFoot, theHarvester, Recon-ng, Sherlock, Nmap, OWASP ZAP, Burp.
- Exploitation and attack tools (Metasploit, SET, sqlmap, Aircrack-ng) stay outside the app. The app can archive their reports as project documents.

**Discontinued or changed.**
- Bing Search APIs were retired on 11 Aug 2025. I confirmed this from Microsoft's notice.
- I believe the following are also gone or no longer usable, but haven't checked: Gigablast (shut down), SecurityFocus (retired), Twint (archived, broken by X's API changes), Facebook Graph Search (removed in 2019).

## 9. Security and policy

- **Network guard.** Before every request and redirect, the guard checks:
  - The URL must be http(s).
  - The host must resolve only to public addresses. This blocks localhost, private networks, link-local addresses and cloud metadata.
  - Known gap: a DNS-rebinding window remains between the check and the connection. Phase 1 closes it by connecting to the checked IP.
- **Scoped projects.** Fetches are allowed only for `allowed_domains` and their subdomains. Third-party fetchers (Firecrawl, Jina, Apify) are disabled so target URLs aren't sent to outside services. This is the mode for security work on owned or authorised assets.
- **Tor.** Off by default and enabled per project by the owner. It is used only for .onion addresses. The proxy uses socks5h so names resolve inside Tor.
- **Roles.** Viewers read, editors run searches, fetches and edits, and owners change policy and sharing.
- **Secrets.** API keys live in server environment variables and never reach the browser. User tokens are stored hashed.
- **Before phase 4:** add an audit log of every outbound request (who, what, when, under which project policy) and per-project rate limits.

## 10. Roadmap to production

1. **Week 1–2: run it on real data.**
   - Deploy with Docker Compose and add real keys.
   - Run 20 real questions and fix provider mapping errors shown in `provider_status` and in the model-call log.
   - Confirm the XORTRON model IDs.
2. **Week 3–4: hardening (phase 1).**
   - Alembic migrations.
   - arq worker with Redis for runs and fetches.
   - Playwright fetcher.
   - Server-sent events for live run progress.
   - Retries with backoff per provider.
   - Close the DNS-rebinding gap.
3. **Month 2: memory (phase 2).**
   - pgvector and Postgres full-text search in `memory/retrieve.py`; the function signature is unchanged.
   - Chat-export importers.
   - Claims and entities tables.
   - Cross-project search.
4. **Month 3: scholarly and history (phase 3).**
   - Scholarly adapters and a literature-review workflow (screen → extract → synthesise).
   - Wayback timelines with snapshot diffs.
5. **Month 4+: OSINT, security and collaboration (phases 4–5).**
   - Audit log first, then enrichment adapters behind scoped projects.
   - Comments and annotations, then SSO.

Production checklist:
- HTTPS (Caddy or Traefik in front)
- Daily Postgres backups
- Object storage (S3 or MinIO) for raw HTML and PDFs once the database grows
- Error tracking (Sentry)
- A per-project monthly budget for paid providers

## 11. Libraries and repositories worth building from

| Need | Use | Why |
|---|---|---|
| API / DB | FastAPI, SQLAlchemy 2, Alembic, pgvector | Already in use; mature and well documented |
| Page extraction | trafilatura (in use), Playwright, crawl4ai, docling or unstructured | Best open-source main-text extraction; JS rendering; PDFs and Office files with layout |
| Self-hosted crawl | Firecrawl (open source), SearXNG (in use) | Avoid per-call costs and limits |
| Model access | LiteLLM (optional), Ollama | One interface to 100+ providers; local models |
| Structured output | Pydantic + Instructor | Reliable JSON from models in planner and extraction steps |
| Workflows | arq (simple), Temporal (durable, heavy), LangGraph (if you want graph-style agents) | Pick the smallest that fits; the step interface stays the same |
| Reference projects | Perplexica, GPT-Researcher, Morphic, Scira, Open WebUI | Open-source research and search apps whose prompts, UI patterns and provider code are worth reading |
| OSINT (phase 4) | SpiderFoot, theHarvester, Recon-ng | Mature tools; import their output instead of rewriting them |
