"use client";
import { useState } from "react";
import { api } from "@/lib/api";

// Project policy: open web vs scoped (only listed domains), Tor access, sharing.
export default function SettingsPanel({ project, onSaved }: { project: any; onSaved: (p: any) => void }) {
  const [mode, setMode] = useState(project.mode);
  const [domains, setDomains] = useState((project.allowed_domains || []).join("\n"));
  const [tor, setTor] = useState(project.allow_tor);
  const [msg, setMsg] = useState("");
  const owner = project.role === "owner";

  const save = async () => {
    try {
      onSaved(await api(`/projects/${project.id}`, { method: "PATCH",
        json: { mode, allow_tor: tor, allowed_domains: domains.split("\n").map((d: string) => d.trim()).filter(Boolean) } }));
      setMsg("Saved");
    } catch (e: any) { setMsg(e.message); }
  };
  const share = async (on: boolean) => {
    if (on) await api(`/projects/${project.id}/share`, { method: "POST" });
    else await api(`/projects/${project.id}/share`, { method: "DELETE" });
    onSaved(await api(`/projects/${project.id}`));
  };

  return (
    <div className="stack" style={{ maxWidth: 640 }}>
      <h2>Project settings</h2>
      {!owner && <p className="muted">Only the project owner can change these.</p>}
      <label>Fetch policy</label>
      <select value={mode} onChange={(e) => setMode(e.target.value)} disabled={!owner}>
        <option value="standard">Standard — any public website</option>
        <option value="scoped">Scoped — only the domains below (for work on assets you own or are authorised to test)</option>
      </select>
      <label>Allowed domains (one per line; subdomains included)</label>
      <textarea rows={4} value={domains} onChange={(e) => setDomains(e.target.value)} disabled={!owner} />
      <label className="row"><input type="checkbox" style={{ width: "auto" }} checked={tor} onChange={(e) => setTor(e.target.checked)} disabled={!owner} />
        Allow Tor (.onion search and fetch through the server's Tor proxy)</label>
      <button className="primary" onClick={save} disabled={!owner}>Save policy</button>
      {msg && <p className="muted">{msg}</p>}
      <h3>Sharing</h3>
      {project.share_token
        ? <><p className="muted">Read-only link (reports and notes only): <span className="mono">/api/shared/{project.share_token}</span></p>
            <button onClick={() => share(false)} disabled={!owner}>Stop sharing</button></>
        : <button onClick={() => share(true)} disabled={!owner}>Create read-only link</button>}
    </div>
  );
}
