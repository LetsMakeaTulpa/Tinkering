"use client";
import { useEffect, useState } from "react";
import { api, when } from "@/lib/api";

export default function TimelinePanel({ pid }: { pid: string }) {
  const [events, setEvents] = useState<any[]>([]);
  const [calls, setCalls] = useState<any[]>([]);
  useEffect(() => { api(`/projects/${pid}/timeline`).then(setEvents); api(`/projects/${pid}/model-calls`).then(setCalls); }, [pid]);
  return (
    <div className="stack">
      <h2>Timeline</h2>
      {events.map((e, i) => <div key={i} className="row"><span className="chip">{e.type}</span>{e.label}<span className="muted">{when(e.at)}</span></div>)}
      <h3>Model calls</h3>
      {calls.map((c) => (
        <div key={c.id} className="row muted">
          <span className={c.status === "ok" ? "chip" : "chip warn"}>{c.task_type}</span>{c.provider}:{c.model}
          · {c.latency_ms} ms · {c.prompt_tokens ?? "?"}→{c.completion_tokens ?? "?"} tokens {c.error && <span className="err">{c.error}</span>}
        </div>
      ))}
    </div>
  );
}
