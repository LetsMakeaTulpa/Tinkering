# Research OS

A project-based research workspace. You ask a question; a team of small AI agents searches the web (including SearXNG and Tor onion search), reads the pages, and writes a report where every claim points back to the exact archived page it came from. Notes, sources and reports all live in the project, so later research builds on earlier research.

The default model is **XORTRON RICO v3** on Featherless, with **XORTRON-AgentRICO** for planning. Both are set in `backend/app/llm/routes.yaml`.

The full product spec, data model, API list and roadmap are in [docs/SPEC.md](docs/SPEC.md).

## What works today (v0.1)

| Area | What you can do |
|---|---|
| Projects | Create projects; invite people as viewer, editor or owner; share a read-only link to the reports and notes |
| Search | Search Exa, SearXNG (with Tor onion engines), Tavily, Brave, Firecrawl, Apify, Perplexity, OpenAlex and Semantic Scholar in parallel; results are merged, de-duplicated and ranked; supports exact-phrase, site, filetype, date range and free-form search operators |
| Fetch & archive | Fetch any page directly, through Tor (.onion), Firecrawl, Jina, Apify, or the Wayback Machine. The archive keeps every fetch as a dated, hashed snapshot of clean Markdown plus the raw HTML |
| Research runs | Six agents run in order: planner → searcher → fetcher → analyst → critic → archiver. You can review and edit the search plan before it runs |
| Citations | Reports use `[S1]`-style markers linked to the exact snapshot and passage. The critic step flags markers that don't match a source and paragraphs with no citation |
| Notes | Markdown editor with full revision history, diffs, and protection against overwriting someone else's newer save. Notes are searchable project memory and can be cited in reports |
| Models | Routing by task type with fallback; Featherless, OpenRouter, OpenAI, Ollama and Anthropic are supported. Every call is logged with its prompt, reply, token counts and timing |
| Safety rails | The fetcher can't reach localhost, private networks or cloud-metadata addresses (checked on every redirect). "Scoped" projects can fetch only the domains you allow. Tor is off by default and turned on per project |

## Run it

### With Docker (recommended)

```bash
cd research-os
cp .env.example .env        # then set ADMIN_TOKEN, FEATHERLESS_API_KEY, and any search keys you have
docker compose up --build
```

Open <http://localhost:3000> and sign in with your `ADMIN_TOKEN`. Docker Compose starts Postgres, SearXNG, Tor, the API and the web app. The API docs are at <http://localhost:8000/docs>.

### Without Docker (for development)

```bash
# backend
cd research-os/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
ADMIN_TOKEN=dev FEATHERLESS_API_KEY=... EXA_API_KEY=... .venv/bin/uvicorn app.main:app --reload
# uses SQLite in ./data unless you set DATABASE_URL

# frontend (second terminal)
cd research-os/frontend && npm install && npm run dev
```

### Tests

```bash
cd research-os/backend && .venv/bin/python -m pytest -q
```

The tests run the whole research loop offline against fake providers and a fake model.

## How it fits together

```
 Browser (Next.js)                         FastAPI backend
 ┌──────────────┐   /api    ┌───────────────────────────────────────────────────────────┐
 │ Research     │ ───────▶ │ api/            routes: projects, documents, research      │
 │ Search       │           │ workflows/      planner→searcher→fetcher→analyst→critic→   │
 │ Sources      │           │                 archiver (each step saved, can pause)      │
 │ Documents    │           │ search/         provider registry → parallel → merge/rank  │
 │ Timeline     │           │ fetch/          netguard → direct | tor | firecrawl |      │
 │ Settings     │           │                 jina | apify | wayback → clean Markdown    │
 └──────────────┘           │ memory/         chunks + keyword/semantic retrieval        │
                            │ llm/            routes.yaml → model fallback → call log    │
                            └───────┬─────────────────────┬──────────────┬───────────────┘
                                    │                     │              │
                               Postgres            SearXNG ──▶ Tor   Featherless / others
```

To add a search provider, write one class in `backend/app/search/providers.py` and add it to `REGISTRY`. To change which model does what, edit `routes.yaml`. To add a workflow, register a list of steps with `workflow("name", [...])`.

## Things to know

- **Model IDs:** the XORTRON models exist on Hugging Face as `darkc0de/XORTRON-RICO-v3` and `darkc0de/XORTRON-AgentRICO`. I couldn't confirm they're live on Featherless from here. If a call fails with "model not found", check featherless.ai/models and update `routes.yaml`. Every failed call is logged on the Timeline tab.
- **Untested against the real services:** the provider adapters follow each provider's current docs, but I could only test them against fake responses. The first real run will show any mismatches in each search's provider status line.
- **Onion search** needs Tor turned on for the project (Settings tab) and the Docker `tor` service. Onion engines are slow; allow 30 seconds or more.
- **Background runs** execute inside the API process. If the API restarts mid-run, the run stops there. Re-running is safe because saved steps are skipped. Phase 2 moves runs to a separate worker.
