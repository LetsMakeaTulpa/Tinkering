// Thin client for the FastAPI backend. The API token lives in localStorage (single-user MVP).
export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export function getToken(): string {
  try { return localStorage.getItem("ros_token") || ""; } catch { return ""; }
}
export function setToken(t: string) {
  try { localStorage.setItem("ros_token", t); } catch {}
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = opts;
  const headers: Record<string, string> = { ...(rest.headers as Record<string, string>) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(API + path, { ...rest, headers, body: json !== undefined ? JSON.stringify(json) : rest.body });
  const data = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(typeof data === "object" && data?.detail ? JSON.stringify(data.detail) : `${r.status}`);
  return data as T;
}

export const when = (s: string) => new Date(s.endsWith("Z") || s.includes("+") ? s : s + "Z").toLocaleString();
