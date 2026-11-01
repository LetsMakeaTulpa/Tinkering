import json

import httpx
import pytest
import respx

from app.netguard import Blocked, check_url
from app.search.base import Hit, canonical_url
from app.search.orchestrator import merge
from app.workflows.research import check_citations

ARTICLE = "<html><head><title>Bees and pollination</title></head><body><article>" + "".join(
    f"<p>Honeybees pollinate roughly a third of crops in this study region, paragraph {i}. "
    "Wild bees matter as much as managed hives for many fruit crops.</p>" for i in range(8)) + "</article></body></html>"


def fake_llm(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    system = body["messages"][0]["content"]
    if "You plan web research" in system:
        text = json.dumps({"queries": ["bee pollination share of crops", "wild bees vs honeybees"], "category": "web"})
    else:
        text = ("Bees pollinate about a third of crops in the region [S1]. Wild bees matter as much as hives for "
                "fruit [S2].\n\nSources agree on the main point [S1][S2].")
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}],
                                     "usage": {"prompt_tokens": 10, "completion_tokens": 20}})


def mock_world(router: respx.Router):
    router.post("https://api.exa.ai/search").respond(json={"results": [
        {"title": "Bee study", "url": "https://bees.example/study?utm_source=x", "text": ARTICLE.replace("<", " <"),
         "highlights": ["a third of crops"], "score": 0.9},
        {"title": "Pollinators", "url": "https://pollen.example/wild", "highlights": ["wild bees"]}]})
    router.get("http://searxng.test/search").respond(json={"results": [
        {"title": "Bee study (www)", "url": "https://www.bees.example/study", "content": "dup of exa #1"},
        {"title": "Pollinators", "url": "https://pollen.example/wild/", "content": "wild bees and fruit"}]})
    router.get("https://pollen.example/wild").respond(200, text=ARTICLE, headers={"content-type": "text/html"})
    router.post("https://api.featherless.ai/v1/chat/completions").mock(side_effect=fake_llm)


# ---------- unit ----------

def test_netguard():
    assert check_url("https://bees.example/x") == "direct"
    for bad in ("file:///etc/passwd", "http://localhost:8000/", "http://internal.test/admin"):
        with pytest.raises(Blocked):
            check_url(bad)
    with pytest.raises(Blocked):
        check_url("http://abc.onion/")  # Tor not enabled
    assert check_url("http://abc.onion/", allow_tor=True, tor_proxy="socks5h://tor:9050") == "tor"
    with pytest.raises(Blocked):
        check_url("https://other.example/", mode="scoped", allowed_domains=["mine.example"])
    assert check_url("https://api.mine.example/", mode="scoped", allowed_domains=["mine.example"]) == "direct"


def test_canonical_and_merge():
    assert canonical_url("http://www.A.com/x/?utm_source=t&b=2&a=1#frag") == "https://a.com/x?a=1&b=2"
    merged = merge({"exa": [Hit("A", "https://a.com/x", "s", "exa", 1), Hit("B", "https://b.com", "s", "exa", 2)],
                    "searxng": [Hit("B", "https://www.b.com/", "longer snippet", "searxng", 1)]})
    assert merged[0]["canonical_url"] == "https://b.com/"  # found by both providers → ranked first
    assert merged[0]["providers"] == ["exa", "searxng"] and merged[0]["snippet"] == "longer snippet"


def test_citation_checker():
    assert check_citations("Fact [S1].", {"S1": {}}) == []
    issues = check_citations("Fact [S9].\n\n" + "x" * 130, {"S1": {}})
    assert "S9" in issues[0] and issues[1].startswith("Uncited")


# ---------- API ----------

def new_project(client, **kw):
    r = client.post("/api/projects", json={"name": "Bees", **kw})
    assert r.status_code == 200, r.text
    return r.json()["id"]


@respx.mock(assert_all_mocked=True)
def test_research_loop_end_to_end(client, respx_mock):
    mock_world(respx_mock)
    pid = new_project(client)
    r = client.post(f"/api/projects/{pid}/runs?wait=true", json={"input": {"question": "How much do bees pollinate?"}})
    run = r.json()
    assert run["status"] == "done", run
    assert [s["agent"] for s in run["steps"]] == ["planner", "searcher", "fetcher", "analyst", "critic", "archiver"]

    searches = client.get(f"/api/projects/{pid}/searches").json()
    assert len(searches) == 2  # one per planned query
    results = client.get(f"/api/searches/{searches[0]['id']}").json()["results"]
    assert len(results) == 2  # 4 raw hits → 2 after dedupe
    assert all(set(x["providers"]) == {"exa", "searxng"} for x in results)

    sources = client.get(f"/api/projects/{pid}/sources").json()
    fetchers = {s["latest"]["fetcher"] for s in sources}
    assert fetchers == {"exa", "direct"}  # Exa's text archived as-is; the other page fetched directly

    doc = client.get(f"/api/documents/{run['state']['document_id']}").json()
    assert doc["kind"] == "report" and "## Sources" in doc["content"]
    assert {c["marker"] for c in doc["citations"]} == {"S1", "S2"}
    assert all(c["snapshot_id"] and c["quote"] for c in doc["citations"])

    calls = client.get(f"/api/projects/{pid}/model-calls").json()
    assert {c["task_type"] for c in calls} == {"plan", "synthesis"}
    assert all(c["model"].startswith("darkc0de/XORTRON") for c in calls)
    assert client.get(f"/api/projects/{pid}/timeline").json()


@respx.mock(assert_all_mocked=True)
def test_human_approval_pause_and_edit(client, respx_mock):
    mock_world(respx_mock)
    pid = new_project(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"input": {"question": "bees?", "require_approval": True}}).json()
    assert run["status"] == "awaiting_approval" and run["state"]["plan"]["queries"]
    run = client.post(f"/api/runs/{run['id']}/approve?wait=true",
                      json={"plan": {"queries": ["only this query"], "category": "web"}}).json()
    assert run["status"] == "done"
    assert [s["query"] for s in client.get(f"/api/projects/{pid}/searches").json()] == ["only this query"]


def test_documents_history_diff_and_conflict(client):
    pid = new_project(client)
    d = client.post(f"/api/projects/{pid}/documents", json={"title": "Notes", "content": "line one"}).json()
    client.put(f"/api/documents/{d['id']}", json={"content": "line one\nline two", "base_rev": 1})
    stale = client.put(f"/api/documents/{d['id']}", json={"content": "x", "base_rev": 1})
    assert stale.status_code == 409
    assert [r["rev"] for r in client.get(f"/api/documents/{d['id']}/revisions").json()] == [2, 1]
    assert "+line two" in client.get(f"/api/documents/{d['id']}/diff?a=1&b=2").json()["diff"]
    hits = client.get(f"/api/projects/{pid}/memory?q=line two").json()
    assert hits and hits[0]["document_id"] == d["id"]  # notes are part of project memory


def test_permissions_and_sharing(client):
    pid = new_project(client)
    tok = client.post("/api/users", json={"email": "viewer@x.test"}).json()["token"]
    client.post(f"/api/projects/{pid}/members", json={"email": "viewer@x.test", "role": "viewer"})
    v = {"Authorization": f"Bearer {tok}"}
    assert client.get(f"/api/projects/{pid}", headers=v).status_code == 200
    assert client.post(f"/api/projects/{pid}/documents", json={"title": "n"}, headers=v).status_code == 403
    assert client.get("/api/projects", headers={"Authorization": "Bearer nope"}).status_code == 401
    share = client.post(f"/api/projects/{pid}/share").json()["share_token"]
    assert client.get(f"/api/shared/{share}", headers={"Authorization": ""}).json()["name"] == "Bees"


def test_scoped_project_blocks_outside_fetch(client):
    pid = new_project(client, mode="scoped", allowed_domains=["mine.example"])
    r = client.post(f"/api/projects/{pid}/fetch", json={"url": "https://elsewhere.example/"}).json()
    assert "outside this project's allowed domains" in r["snapshot"]["error"]
    assert client.post(f"/api/projects/{pid}/fetch", json={"url": "http://internal.test/"}).json()["snapshot"]["error"]
