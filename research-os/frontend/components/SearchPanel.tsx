"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// Direct search: pick providers + operators, see merged/deduped results, archive any result with one click.
export default function SearchPanel({ pid, project }: { pid: string; project: any }) {
  const [providers, setProviders] = useState<any[]>([]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [f, setF] = useState({ query: "", category: "web", site: "", filetype: "", after: "", before: "", extra: "", exact: false });
  const [run, setRun] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [fetching, setFetching] = useState<Record<string, string>>({});

  useEffect(() => {
    api<any[]>("/providers").then((p) => { setProviders(p); setChosen(p.filter((x) => x.enabled && x.categories.includes("web")).map((x) => x.name)); });
  }, []);

  const go = async () => {
    setBusy(true); setErr("");
    try {
      const body: any = { ...f, providers: chosen };
      for (const k of ["site", "filetype", "after", "before"]) if (!body[k]) delete body[k];
      setRun(await api(`/projects/${pid}/search`, { method: "POST", json: body }));
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  const archive = async (url: string) => {
    setFetching((s) => ({ ...s, [url]: "fetching…" }));
    const r = await api(`/projects/${pid}/fetch`, { method: "POST", json: { url } });
    setFetching((s) => ({ ...s, [url]: r.snapshot.error ? `failed: ${r.snapshot.error}` : `archived (${r.snapshot.chars} chars, ${r.snapshot.fetcher})` }));
  };
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  return (
    <div className="stack">
      <h2>Search</h2>
      <div className="row">
        <input value={f.query} onChange={set("query")} onKeyDown={(e) => e.key === "Enter" && go()} placeholder="Query" style={{ flex: 1 }} />
        <select value={f.category} onChange={set("category")} style={{ width: 130 }}>
          <option value="web">Web</option><option value="news">News</option><option value="paper">Papers</option>
          <option value="onion" disabled={!project.allow_tor}>Onion (Tor)</option>
        </select>
        <button className="primary" disabled={busy || !f.query} onClick={go}>{busy ? "Searching…" : "Search"}</button>
      </div>
      <div className="row">
        <input value={f.site} onChange={set("site")} placeholder="site: domain" style={{ width: 170 }} />
        <input value={f.filetype} onChange={set("filetype")} placeholder="filetype" style={{ width: 100 }} />
        <input type="date" value={f.after} onChange={set("after")} style={{ width: 150 }} title="After" />
        <input type="date" value={f.before} onChange={set("before")} style={{ width: 150 }} title="Before" />
        <input value={f.extra} onChange={set("extra")} placeholder='extra dorks, e.g. intitle:"index of"' style={{ flex: 1, minWidth: 200 }} />
        <label className="row muted"><input type="checkbox" style={{ width: "auto" }} checked={f.exact} onChange={set("exact")} /> exact phrase</label>
      </div>
      <div className="row">
        {providers.map((p) => (
          <label key={p.name} className="row muted" title={p.enabled ? p.categories.join(", ") : "not configured — add its API key on the server"}>
            <input type="checkbox" style={{ width: "auto" }} disabled={!p.enabled} checked={chosen.includes(p.name)}
                   onChange={(e) => setChosen(e.target.checked ? [...chosen, p.name] : chosen.filter((n) => n !== p.name))} />
            {p.name}
          </label>
        ))}
      </div>
      {err && <p className="err">{err}</p>}
      {run && (
        <>
          <p className="muted">{Object.entries(run.provider_status).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
          {run.results.map((r: any) => (
            <div key={r.id} className="card">
              <a href={r.url} target="_blank" rel="noreferrer"><strong>{r.title}</strong></a>
              <div className="mono muted">{r.url}</div>
              <p>{r.snippet}</p>
              <div className="row">
                {r.providers.map((p: string) => <span key={p} className="chip">{p}</span>)}
                {r.source_type !== "web" && <span className="chip warn">{r.source_type}</span>}
                <span className="muted">score {r.score}</span>
                {r.source_id ? <span className="muted">already archived</span>
                  : <button onClick={() => archive(r.url)} disabled={!!fetching[r.url]}>Archive page</button>}
                {fetching[r.url] && <span className="muted">{fetching[r.url]}</span>}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
