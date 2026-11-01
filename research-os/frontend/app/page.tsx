"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, getToken, setToken, when } from "@/lib/api";

type Project = { id: string; name: string; description: string; mode: string; role: string; created_at: string };

export default function Home() {
  const [token, setTok] = useState("");
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [name, setName] = useState("");
  const [err, setErr] = useState("");

  const load = () => api<Project[]>("/projects").then(setProjects).catch((e) => { setErr(e.message); setProjects(null); });
  useEffect(() => { setTok(getToken()); if (getToken()) load(); }, []);

  if (!projects) {
    return (
      <main className="wrap stack" style={{ maxWidth: 420 }}>
        <h1>Research OS</h1>
        <p className="muted">Paste the API token you set as ADMIN_TOKEN on the server.</p>
        <input type="password" value={token} onChange={(e) => setTok(e.target.value)} placeholder="API token" />
        <button className="primary" onClick={() => { setToken(token); setErr(""); load(); }}>Sign in</button>
        {err && <p className="err">{err}</p>}
      </main>
    );
  }
  return (
    <main className="wrap stack">
      <h1>Projects</h1>
      <form className="row" onSubmit={async (e) => {
        e.preventDefault();
        if (!name.trim()) return;
        await api("/projects", { method: "POST", json: { name } });
        setName(""); load();
      }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New project name" style={{ flex: 1 }} />
        <button className="primary">Create project</button>
      </form>
      {projects.length === 0 && <p className="muted">No projects yet.</p>}
      {projects.map((p) => (
        <Link key={p.id} href={`/projects/${p.id}`} className="card" style={{ textDecoration: "none", color: "inherit" }}>
          <strong>{p.name}</strong> <span className="chip">{p.role}</span>{p.mode === "scoped" && <span className="chip warn">scoped</span>}
          <div className="muted">Created {when(p.created_at)}</div>
        </Link>
      ))}
    </main>
  );
}
