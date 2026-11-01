"""All settings come from environment variables so the same code runs locally, in Docker and in production."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


@dataclass
class Settings:
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./data/research.db")
    data_dir: Path = Path(os.environ.get("DATA_DIR", "./data"))
    # Bootstrap admin: the first user is created from this token on startup.
    admin_token: str = os.environ.get("ADMIN_TOKEN", "")
    admin_email: str = os.environ.get("ADMIN_EMAIL", "admin@localhost")
    cors_origins: list[str] = field(default_factory=lambda: _list("CORS_ORIGINS", "http://localhost:3000"))

    # Search providers (a provider is enabled when its key/URL is set)
    exa_api_key: str = os.environ.get("EXA_API_KEY", "")
    tavily_api_key: str = os.environ.get("TAVILY_API_KEY", "")
    brave_api_key: str = os.environ.get("BRAVE_API_KEY", "")
    firecrawl_api_key: str = os.environ.get("FIRECRAWL_API_KEY", "")
    apify_token: str = os.environ.get("APIFY_TOKEN", "")
    apify_search_actor: str = os.environ.get("APIFY_SEARCH_ACTOR", "apify~rag-web-browser")
    apify_fetch_actor: str = os.environ.get("APIFY_FETCH_ACTOR", "apify~rag-web-browser")
    perplexity_api_key: str = os.environ.get("PERPLEXITY_API_KEY", "")
    perplexity_model: str = os.environ.get("PERPLEXITY_MODEL", "sonar")
    semantic_scholar_api_key: str = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    searxng_url: str = os.environ.get("SEARXNG_URL", "")  # e.g. http://searxng:8080
    jina_api_key: str = os.environ.get("JINA_API_KEY", "")
    openalex_mailto: str = os.environ.get("OPENALEX_MAILTO", "")
    default_providers: list[str] = field(default_factory=lambda: _list("DEFAULT_SEARCH_PROVIDERS", "exa,searxng"))

    # Tor: SOCKS proxy used for .onion fetches (socks5h so DNS resolves inside Tor)
    tor_proxy: str = os.environ.get("TOR_PROXY", "")  # e.g. socks5h://tor:9050

    # Models (OpenAI-compatible providers share one adapter)
    featherless_api_key: str = os.environ.get("FEATHERLESS_API_KEY", "")
    featherless_base_url: str = os.environ.get("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "")  # e.g. http://ollama:11434/v1
    routes_file: Path = Path(os.environ.get("MODEL_ROUTES_FILE", Path(__file__).parent / "llm" / "routes.yaml"))
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "")  # "provider:model"; empty = keyword search only

    fetch_timeout: float = float(os.environ.get("FETCH_TIMEOUT", "30"))
    max_fetch_bytes: int = int(os.environ.get("MAX_FETCH_BYTES", str(15 * 1024 * 1024)))


settings = Settings()
