"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, when } from "@/lib/api";

// The project's archive: every fetched page, every snapshot over time, with how and when it was fetched.
export default function SourcesPanel({ pid }: { pid: string }) {
  const [list, setList] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<any>(null);
  const [url, setUrl] = useState("");
  const [method, setMethod] = useState("auto");
  const [msg, setMsg] = useState("");

  const load = () => api(`/projects/${pid}/sources?q=${encodeURIComponent(q)}`).then(setList);
  useEffect(() => { load(); }, [pid, q]);
  const open = (id: string) => api(`/sources/${id}`).then(setSel);
  const add = async () => {
    setMsg("Fetching…");
    const r = await api(`/projects/${pid}/fetch`, { method: "POST", json: { url, method } });
    setMsg(r.snapshot.error ? `Failed: ${r.snapshot.error}` : `Archived ${r.snapshot.chars} characters via ${r.snapshot.fetcher}`);
    load(); open(r.source_id);
  };

  return (
    <div className="stack">
      <h2>Sources</h2>
      <div className="row">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://… or http://….onion" style={{ flex: 1 }} />
        <select value={method} onChange={(e) => setMethod(e.target.value)} style={{ width: 140 }}>
          {["auto", "direct", "tor", "firecrawl", "jina", "apify", "wayback"].map((m) => <option key={m}>{m}</option>)}
        </select>
        <button className="primary" disabled={!url} onClick={add}>Fetch & archive</button>
      </div>
      {msg && <p className="muted">{msg}</p>}
      <div className="split">
        <div className="stack">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter sources" />
          <div className="list">
            {list.map((s) => (
              <button key={s.id} className={sel?.id === s.id ? "on" : ""} onClick={() => open(s.id)}>
                {s.title || s.url}<div className="muted">{s.snapshots} snapshot(s){s.latest?.error ? " · last fetch failed" : ""}</div>
              </button>
            ))}
          </div>
        </div>
        {sel && (
          <div className="card stack">
            <a href={sel.url} target="_blank" rel="noreferrer"><strong>{sel.title}</strong></a>
            <div className="mono muted">{sel.url}</div>
            {sel.snapshots.map((s: any, i: number) => (
              <div key={s.id} className="muted">
                {i === 0 ? "Latest" : "Earlier"}: {when(s.fetched_at)} · {s.fetcher} · HTTP {s.http_status ?? "–"} · {s.chars} chars
                · <span className="mono">sha256 {s.content_hash.slice(0, 12)}</span>{s.error && <span className="err"> · {s.error}</span>}
              </div>
            ))}
            {sel.snapshots[0]?.content && <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{sel.snapshots[0].content.slice(0, 60000)}</ReactMarkdown></div>}
          </div>
        )}
      </div>
    </div>
  );
}
