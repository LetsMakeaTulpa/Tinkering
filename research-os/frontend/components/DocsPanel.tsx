"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, when } from "@/lib/api";

// Notes and reports: Markdown editor with preview, full revision history and diffs.
export default function DocsPanel({ pid }: { pid: string }) {
  const [docs, setDocs] = useState<any[]>([]);
  const [doc, setDoc] = useState<any>(null);
  const [text, setText] = useState("");
  const [preview, setPreview] = useState(false);
  const [revs, setRevs] = useState<any[]>([]);
  const [diff, setDiff] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => api(`/projects/${pid}/documents`).then(setDocs);
  useEffect(() => { load(); }, [pid]);
  const open = async (id: string) => {
    const d = await api(`/documents/${id}`);
    setDoc(d); setText(d.content); setDiff(""); setMsg("");
    setRevs(await api(`/documents/${id}/revisions`));
  };
  const create = async () => {
    const title = window.prompt("Title for the new note");
    if (!title) return;
    const d = await api(`/projects/${pid}/documents`, { method: "POST", json: { title, content: "" } });
    await load(); open(d.id);
  };
  const save = async () => {
    try {
      await api(`/documents/${doc.id}`, { method: "PUT", json: { content: text, base_rev: doc.current_rev } });
      await open(doc.id); load(); setMsg("Saved");
    } catch (e: any) { setMsg(e.message); }
  };

  return (
    <div className="split">
      <div className="stack">
        <button className="primary" onClick={create}>New note</button>
        <div className="list">
          {docs.map((d) => (
            <button key={d.id} className={doc?.id === d.id ? "on" : ""} onClick={() => open(d.id)}>
              {d.title}<div className="muted">{d.kind} · rev {d.current_rev}</div>
            </button>
          ))}
        </div>
      </div>
      {doc && (
        <div className="stack">
          <div className="row">
            <strong style={{ flex: 1 }}>{doc.title}</strong>
            <button onClick={() => setPreview(!preview)}>{preview ? "Edit" : "Preview"}</button>
            <button className="primary" onClick={save} disabled={text === doc.content}>Save revision</button>
          </div>
          {msg && <p className="muted">{msg}</p>}
          {preview ? <div className="card md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown></div>
                   : <textarea rows={24} value={text} onChange={(e) => setText(e.target.value)} />}
          <details>
            <summary className="muted">History ({revs.length} revisions)</summary>
            {revs.map((r, i) => (
              <div key={r.rev} className="row muted">
                rev {r.rev} · {r.author} · {when(r.created_at)} {r.message && `· ${r.message}`}
                {i < revs.length - 1 && <button onClick={async () => setDiff((await api(`/documents/${doc.id}/diff?a=${revs[i + 1].rev}&b=${r.rev}`)).diff)}>diff</button>}
              </div>
            ))}
            {diff && <pre className="diff card">{diff}</pre>}
          </details>
        </div>
      )}
    </div>
  );
}
