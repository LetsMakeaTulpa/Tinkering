import os
import socket
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["DATA_DIR"] = _tmp
os.environ["ADMIN_TOKEN"] = "admin-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

PUBLIC_IP = "93.184.215.14"


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Tests never touch real DNS: test hostnames resolve to a public IP, 'internal.test' to a private one."""
    def resolve(host, port, *a, **k):
        ip = "10.0.0.5" if host == "internal.test" else ("127.0.0.1" if host == "localhost" else PUBLIC_IP)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
    monkeypatch.setattr(socket, "getaddrinfo", resolve)


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "exa_api_key", "exa-key")
    monkeypatch.setattr(settings, "searxng_url", "http://searxng.test")
    monkeypatch.setattr(settings, "featherless_api_key", "fl-key")
    monkeypatch.setattr(settings, "default_providers", ["exa", "searxng"])
    for k in ("tavily_api_key", "brave_api_key", "firecrawl_api_key", "apify_token", "perplexity_api_key"):
        monkeypatch.setattr(settings, k, "")


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer admin-token"
        yield c
