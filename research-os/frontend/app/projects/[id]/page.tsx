"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import ResearchPanel from "@/components/ResearchPanel";
import SearchPanel from "@/components/SearchPanel";
import SourcesPanel from "@/components/SourcesPanel";
import DocsPanel from "@/components/DocsPanel";
import TimelinePanel from "@/components/TimelinePanel";
import SettingsPanel from "@/components/SettingsPanel";

const TABS = ["Research", "Search", "Sources", "Documents", "Timeline", "Settings"] as const;

export default function Workspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Research");
  const [project, setProject] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api(`/projects/${id}`).then(setProject).catch((e) => setErr(e.message)); }, [id]);

  if (err) return <main className="wrap err">{err} — <Link href="/">back</Link></main>;
  if (!project) return <main className="wrap muted">Loading…</main>;
  return (
    <div className="shell">
      <nav className="rail">
        <h1><Link href="/">←</Link> {project.name}</h1>
        {TABS.map((t) => <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}
      </nav>
      <main className="pane">
        {tab === "Research" && <ResearchPanel pid={id} />}
        {tab === "Search" && <SearchPanel pid={id} project={project} />}
        {tab === "Sources" && <SourcesPanel pid={id} />}
        {tab === "Documents" && <DocsPanel pid={id} />}
        {tab === "Timeline" && <TimelinePanel pid={id} />}
        {tab === "Settings" && <SettingsPanel project={project} onSaved={setProject} />}
      </main>
    </div>
  );
}
