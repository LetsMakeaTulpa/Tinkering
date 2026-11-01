"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, when } from "@/lib/api";

// Ask a question → the six agents run → a cited report lands in Documents.
export default function ResearchPanel({ pid }: { pid: string }) {
  const [question, setQuestion] = useState("");
  const [approval, setApproval] = useState(false);
  const [run, setRun] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [queries, setQueries] = useState("");
  const [err, setErr] = useState("");

  const loadHistory = () => api(`/projects/${pid}/runs`).then(setHistory);
  useEffect(() => { loadHistory(); }, [pid]);

  // Poll the run while agents are working.
  useEffect(() => {
    if (!run || !["pending", "running"].includes(run.status)) return;
    const t = setTimeout(() => api(`/runs/${run.id}`).then(setRun), 1500);
    return () => clearTimeout(t);
  }, [run]);
  useEffect(() => {
    if (run?.status === "awaiting_approval") setQueries((run.state.plan?.queries || []).join("\n"));
    if (run?.status === "done" && run.state.document_id) {
      api(`/documents/${run.state.document_id}`).then(setReport);
      loadHistory();
    }
  }, [run?.status]);

  const start = async () => {
    setErr(""); setReport(null);
    try {
      setRun(await api(`/projects/${pid}/runs`, { method: "POST", json: { input: { question, require_approval: approval } } }));
    } catch (e: any) { setErr(e.message); }
  };
  const approve = async () => {
    const plan = { ...run.state.plan, queries: queries.split("\n").map((q) => q.trim()).filter(Boolean) };
    setRun(await api(`/runs/${run.id}/approve`, { method: "POST", json: { plan } }));
  };

  return (
    <div className="stack">
      <h2>Research</h2>
      <textarea rows={3} value={question} onChange={(e) => setQuestion(e.target.value)}
                placeholder="What do you want to find out?" style={{ fontFamily: "var(--font)", fontSize: 15 }} />
      <div className="row">
        <button className="primary" disabled={!question.trim() || ["pending", "running"].includes(run?.status)} onClick={start}>Run research</button>
        <label className="row muted"><input type="checkbox" style={{ width: "auto" }} checked={approval} onChange={(e) => setApproval(e.target.checked)} /> Let me review the search plan first</label>
      </div>
      {err && <p className="err">{err}</p>}
      {run && (
        <div className="card stack">
          <div className="steps">
            {["planner", "searcher", "fetcher", "analyst", "critic", "archiver"].map((a) => {
              const s = run.steps.find((x: any) => x.agent === a);
              return <span key={a} className={`step ${s?.status || ""}`}>{a}</span>;
            })}
            <span className="muted">{run.status}</span>
          </div>
          {run.error && <pre className="err mono">{run.error}</pre>}
          {run.status === "awaiting_approval" && (
            <div className="stack">
              <label className="muted">Planned queries — edit, one per line, then continue:</label>
              <textarea rows={5} value={queries} onChange={(e) => setQueries(e.target.value)} />
              <button className="primary" onClick={approve}>Approve and continue</button>
            </div>
          )}
          {run.state.issues?.length > 0 && <p className="muted">Critic notes: {run.state.issues.join(" · ")}</p>}
        </div>
      )}
      {report && (
        <div className="card md">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.content}</ReactMarkdown>
          <details><summary className="muted">Citation evidence ({report.citations.length})</summary>
            {report.citations.map((c: any) => <p key={c.marker} className="mono"><b>[{c.marker}]</b> {c.quote}…</p>)}
          </details>
        </div>
      )}
      {history.length > 0 && <h3>Earlier runs</h3>}
      {history.map((h) => (
        <button key={h.id} className="card" style={{ textAlign: "left" }} onClick={() => api(`/runs/${h.id}`).then(setRun)}>
          {h.question} <span className="chip">{h.status}</span> <span className="muted">{when(h.created_at)}</span>
        </button>
      ))}
    </div>
  );
}
