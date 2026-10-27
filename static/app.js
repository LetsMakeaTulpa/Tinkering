/* Featherless Chat — frontend. Plain JS, no build step. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "text") n.textContent = v;
    else if (v !== undefined && v !== null && v !== false) n.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null) n.append(k.nodeType ? k : document.createTextNode(k));
  return n;
};
const uid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);
const isTouch = matchMedia("(pointer: coarse)").matches;

const PARAMS = [
  // key, label, step, hint
  ["temperature", "Temperature", 0.05, "0 = focused, 1+ = creative"],
  ["top_p", "Top P", 0.01, "nucleus sampling, 0–1"],
  ["top_k", "Top K", 1, "-1 or empty = off"],
  ["min_p", "Min P", 0.01, "0–1"],
  ["max_tokens", "Max tokens", 1, "length of the reply"],
  ["repetition_penalty", "Repetition penalty", 0.01, "1 = off"],
  ["presence_penalty", "Presence penalty", 0.1, "-2 to 2"],
  ["frequency_penalty", "Frequency penalty", 0.1, "-2 to 2"],
  ["seed", "Seed", 1, "same seed → repeatable output"],
];

const S = {
  settings: {},
  chats: [],
  presets: [],
  models: null,
  tab: "chats",
  q: "",
  chat: null,
  pending: [],
  streams: new Map(), // chat object -> AbortController
};

// ------------------------------------------------------------------ api

async function api(path, opts = {}) {
  const o = { ...opts, headers: { ...(opts.headers || {}) } };
  if (o.body && !(o.body instanceof FormData) && typeof o.body !== "string") {
    o.body = JSON.stringify(o.body);
    o.headers["Content-Type"] = "application/json";
  }
  const r = await fetch(path, o);
  if (r.status === 401) { showLogin(); throw new Error("Please log in"); }
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.error) || `${r.status} ${r.statusText}`);
  return data;
}

function toast(msg, ms = 2200) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied"); }
  catch { toast("Copy failed — long-press to select instead"); }
}

// ------------------------------------------------------------------ boot / auth

function showLogin() {
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  $("#login-pw").focus();
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/login", { method: "POST", body: { password: $("#login-pw").value } });
    $("#login").classList.add("hidden");
    init();
  } catch (err) { $("#login-err").textContent = err.message; }
});

async function boot() {
  const me = await api("/api/me");
  if (!me.authed) return showLogin();
  init();
}

async function init() {
  $("#app").classList.remove("hidden");
  [S.settings, S.presets] = await Promise.all([api("/api/settings"), api("/api/presets")]);
  applySettings();
  await loadChats();
  newChat();
  // Text shared into the app from Android's share sheet arrives as ?text=…&url=…
  const qp = new URLSearchParams(location.search);
  const shared = [qp.get("title"), qp.get("text"), qp.get("url")].filter(Boolean).join("\n");
  if (shared) { input.value = shared; autosize(); updateSendBtn(); history.replaceState(null, "", "/"); }
  if (!S.settings.api_key_set) {
    openSettings();
    toast("Add your Featherless API key to get started", 4000);
  }
}

// ------------------------------------------------------------------ settings / theme

function applySettings() {
  const s = S.settings;
  const root = document.documentElement;
  let theme = s.theme || "system";
  if (theme === "system") theme = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  root.dataset.theme = theme;
  $("#hljs-theme").href = `/static/vendor/hljs-${theme === "light" ? "light" : "dark"}.css`;
  root.style.setProperty("--accent", s.accent || "#7c5cff");
  root.style.setProperty("--font-size", (s.font_size || 15) + "px");
  root.style.setProperty("--chat-width", (s.chat_width || 820) + "px");
  if (s.font_family) root.style.setProperty("--font", s.font_family);
  else root.style.removeProperty("--font");
  $("#custom-css").textContent = s.custom_css || "";
  $('meta[name="theme-color"]').content = getComputedStyle(root).getPropertyValue("--bg").trim();
  $("#empty-title").textContent = s.greeting || "How can I help?";
}

async function saveSettings(patch) {
  S.settings = await api("/api/settings", { method: "PUT", body: patch });
  applySettings();
}

// ------------------------------------------------------------------ sidebar / chat list

async function loadChats() {
  if (S.tab === "presets") return renderSidebar();
  const qs = new URLSearchParams({ archived: S.tab === "archived" ? "1" : "0" });
  if (S.q) qs.set("q", S.q);
  S.chats = await api("/api/chats?" + qs);
  renderSidebar();
}

function dayGroup(ts) {
  const d = new Date(ts * 1000), now = new Date();
  const days = Math.floor((new Date(now.toDateString()) - new Date(d.toDateString())) / 864e5);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Previous 7 days";
  if (days < 30) return "Previous 30 days";
  return d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function renderSidebar() {
  const list = $("#chat-list");
  list.innerHTML = "";
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === S.tab));
  if (S.tab === "presets") return renderPresetList(list);
  if (!S.chats.length) {
    list.append(el("p", { class: "muted", style: "padding:12px", text: S.q ? "No matches." : S.tab === "archived" ? "Nothing archived." : "No chats yet." }));
    return;
  }
  let group = null;
  for (const c of S.chats) {
    const g = c.pinned ? "Pinned" : (c.folder || dayGroup(c.updated_at));
    if (g !== group) { group = g; list.append(el("div", { class: "group-label", text: g })); }
    const item = el("div", { class: "chat-item" + (S.chat && S.chat.id === c.id ? " active" : ""), onclick: () => openChat(c.id) },
      el("span", { class: "t", text: c.title || "Untitled" }),
      c.shared ? el("span", { class: "badge", title: "Shared", text: "🔗" }) : null,
      el("button", { class: "icon-btn", title: "Actions", onclick: (e) => { e.stopPropagation(); chatMenu(c, e.currentTarget); } }, "⋯"),
    );
    list.append(item);
  }
}

function renderPresetList(list) {
  list.append(el("div", { style: "padding:4px 2px 8px" }, el("button", { class: "btn block", onclick: () => editPreset() }, "＋ New preset")));
  if (!S.presets.length) list.append(el("p", { class: "muted", style: "padding:0 12px", text: "Presets bundle a system prompt, model and sampling settings — like custom GPTs / Claude projects." }));
  for (const p of S.presets) {
    list.append(el("div", { class: "preset-item" },
      el("span", { class: "t", title: "Start chat with this preset", text: p.name, onclick: () => { newChat(p); closeSidebarMobile(); } }),
      el("button", { class: "icon-btn", title: "Edit", onclick: () => editPreset(p) }, "✎"),
    ));
  }
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => { S.tab = t.dataset.tab; loadChats(); }));
let searchT;
$("#search").addEventListener("input", (e) => {
  clearTimeout(searchT);
  searchT = setTimeout(() => { S.q = e.target.value.trim(); if (S.tab === "presets") S.tab = "chats"; loadChats(); }, 250);
});

function toggleSidebar() {
  const app = $("#app");
  if (innerWidth <= 760) {
    const open = !app.classList.contains("side-open");
    app.classList.toggle("side-open", open);
    if (open) history.pushState({ layer: "side" }, "");
  } else app.classList.toggle("side-collapsed");
}
function closeSidebarMobile() { $("#app").classList.remove("side-open"); }
$("#toggle-sidebar").addEventListener("click", toggleSidebar);
$("#scrim").addEventListener("click", closeSidebarMobile);
$("#new-chat").addEventListener("click", () => { newChat(); closeSidebarMobile(); });

// ------------------------------------------------------------------ popup menu

function popMenu(anchor, items) {
  const m = $("#menu");
  m.innerHTML = "";
  for (const it of items) {
    if (!it) continue;
    m.append(el("button", { class: it.danger ? "danger" : "", onclick: () => { hideMenu(); it.fn(); } }, it.label));
  }
  m.classList.remove("hidden");
  const r = anchor.getBoundingClientRect();
  const w = m.offsetWidth, h = m.offsetHeight;
  m.style.left = Math.max(8, Math.min(r.right - w, innerWidth - w - 8)) + "px";
  m.style.top = (r.bottom + h + 8 > innerHeight ? Math.max(8, r.top - h - 4) : r.bottom + 4) + "px";
}
function hideMenu() { $("#menu").classList.add("hidden"); }
document.addEventListener("click", (e) => { if (!e.target.closest("#menu") && !e.target.closest(".icon-btn")) hideMenu(); });

function chatMenu(c, anchor) {
  popMenu(anchor, [
    { label: "✎ Rename", fn: () => renameChat(c) },
    { label: c.pinned ? "📌 Unpin" : "📌 Pin", fn: () => patchChat(c.id, { pinned: !c.pinned }) },
    { label: "📁 Move to folder…", fn: () => moveToFolder(c) },
    { label: c.archived ? "↩ Unarchive" : "🗄 Archive", fn: () => patchChat(c.id, { archived: !c.archived }) },
    { label: "🔗 Share…", fn: () => shareChat(c) },
    { label: "⬇ Export Markdown", fn: () => location.assign(`/api/chats/${c.id}/export?format=md`) },
    { label: "⬇ Export JSON", fn: () => location.assign(`/api/chats/${c.id}/export?format=json`) },
    { label: "🗑 Delete", danger: true, fn: () => deleteChat(c) },
  ]);
}

async function patchChat(id, patch) {
  const updated = await api(`/api/chats/${id}`, { method: "PATCH", body: patch });
  if (S.chat && S.chat.id === id) Object.assign(S.chat, { title: updated.title, pinned: updated.pinned, archived: updated.archived, folder: updated.folder, shared: updated.shared });
  await loadChats();
}

async function renameChat(c) {
  const t = prompt("Rename chat", c.title);
  if (t && t.trim()) await patchChat(c.id, { title: t.trim() });
}
async function moveToFolder(c) {
  const f = prompt("Folder name (empty to remove from folder)", c.folder || "");
  if (f !== null) await patchChat(c.id, { folder: f.trim() });
}
async function deleteChat(c) {
  if (!confirm(`Delete "${c.title}"? This can't be undone.`)) return;
  await api(`/api/chats/${c.id}`, { method: "DELETE" });
  if (S.chat && S.chat.id === c.id) newChat();
  await loadChats();
}

async function shareChat(c) {
  const id = c.id;
  const render = async (url) => {
    const body = el("div");
    if (url) {
      const input = el("input", { value: url, readonly: true, onclick: (e) => e.target.select() });
      body.append(
        el("p", { class: "muted", text: "Anyone with this link can read this chat (read-only). It updates as the chat changes." }), input,
        el("div", { class: "modal-actions" },
          el("button", { class: "btn danger", onclick: async () => { await api(`/api/chats/${id}/share`, { method: "DELETE" }); await loadChats(); render(null); } }, "Revoke link"),
          navigator.share ? el("button", { class: "btn", onclick: () => navigator.share({ title: c.title, url }).catch(() => {}) }, "Share…") : null,
          el("button", { class: "btn primary", onclick: () => copyText(url) }, "Copy link"),
        ));
    } else {
      body.append(
        el("p", { class: "muted", text: "Create a public read-only link to this chat. Your API key, settings and other chats stay private." }),
        el("div", { class: "modal-actions" }, el("button", { class: "btn primary", onclick: async () => { const r = await api(`/api/chats/${id}/share`, { method: "POST" }); await loadChats(); render(r.url); } }, "Create link")));
    }
    openModal("Share chat", body);
  };
  render(c.share_token ? `${location.origin}/s/${c.share_token}` : null);
}

$("#chat-menu-btn").addEventListener("click", (e) => {
  if (!S.chat.id) return toast("Send a message first");
  const c = S.chats.find((x) => x.id === S.chat.id) || S.chat;
  chatMenu(c, e.currentTarget);
});

// ------------------------------------------------------------------ chats

function defaults() {
  const s = S.settings;
  return {
    model: s.default_model || s.last_model || null,
    system_prompt: s.default_system_prompt || "",
    params: { ...(s.default_params || {}) },
  };
}

function newChat(preset) {
  S.chat = { title: "New chat", messages: [], ...defaults() };
  if (preset) {
    S.chat.system_prompt = preset.system_prompt || "";
    S.chat.params = { ...(preset.params || {}) };
    if (preset.model) S.chat.model = preset.model;
    S.chat.title = preset.name;
    S.chat.presetName = preset.name;
  }
  S.pending = [];
  renderAll();
  $("#input").focus();
}

async function openChat(id) {
  closeSidebarMobile();
  // Reuse the live object if this chat is still streaming in the background.
  for (const c of S.streams.keys()) if (c.id === id) { S.chat = c; renderAll(); return; }
  S.chat = await api(`/api/chats/${id}`);
  S.pending = [];
  renderAll();
}

async function saveChat(chat) {
  const body = {
    title: chat.title, model: chat.model, system_prompt: chat.system_prompt,
    params: chat.params, messages: chat.messages.map(stripTransient),
  };
  if (!chat.id) {
    const created = await api("/api/chats", { method: "POST", body });
    chat.id = created.id;
  } else {
    await api(`/api/chats/${chat.id}`, { method: "PATCH", body });
  }
  loadChats();
}
function stripTransient(m) { const { streaming, ...rest } = m; return rest; }

function renderAll() {
  renderSidebar();
  renderHeader();
  renderMessages();
  renderAttachments();
  updateSendBtn();
}

function renderHeader() {
  $("#model-name").textContent = S.chat.model ? S.chat.model.split("/").pop() : "Choose a model";
  $("#model-btn").title = S.chat.model || "Choose model";
  document.title = S.chat.id ? `${S.chat.title} · Featherless Chat` : "Featherless Chat";
}

// ------------------------------------------------------------------ rendering messages

marked.setOptions({ gfm: true, breaks: true });

function splitThink(text, reasoning) {
  // Reasoning models stream either a separate `reasoning` field or inline <think>…</think>.
  let think = reasoning || "";
  let answer = text || "";
  const m = answer.match(/^\s*<think>([\s\S]*?)(<\/think>|$)/);
  if (m) {
    think = (think ? think + "\n" : "") + m[1];
    answer = m[2] ? answer.slice(m[0].length) : "";
  }
  return { think: think.trim(), answer, thinkingOpen: !!m && !m[2] };
}

function mdToEl(text) {
  const div = el("div", { class: "md" });
  div.innerHTML = DOMPurify.sanitize(marked.parse(text || ""));
  div.querySelectorAll("pre > code").forEach((code) => {
    const lang = (code.className.match(/language-([\w+#-]+)/) || [])[1] || "";
    try { hljs.highlightElement(code); } catch {}
    const pre = code.parentElement;
    pre.prepend(el("div", { class: "code-head" }, el("span", { text: lang || "code" }),
      el("button", { onclick: () => copyText(code.textContent) }, "Copy")));
  });
  div.querySelectorAll("a").forEach((a) => { a.target = "_blank"; a.rel = "noopener"; });
  return div;
}

function attachmentChips(atts) {
  if (!atts || !atts.length) return null;
  const row = el("div", { class: "att-row" });
  for (const a of atts) {
    if (a.kind === "image") row.append(el("a", { href: `/api/files/${a.id}`, target: "_blank" }, el("img", { src: `/api/files/${a.id}`, alt: a.name, loading: "lazy" })));
    else row.append(el("span", { class: "chip" }, el("a", { href: `/api/files/${a.id}?dl=1` }, "📄 ", el("span", { text: a.name }))));
  }
  return row;
}

function renderMessages() {
  const box = $("#messages");
  box.querySelectorAll(".msg").forEach((n) => n.remove());
  const empty = $("#empty");
  empty.classList.toggle("hidden", S.chat.messages.length > 0);
  if (!S.chat.messages.length) renderEmpty();
  S.chat.messages.forEach((m, i) => box.append(renderMsg(m, i)));
  box.scrollTop = box.scrollHeight;
}

function renderEmpty() {
  $("#empty-sub").textContent = S.chat.presetName
    ? `Preset: ${S.chat.presetName}`
    : S.chat.model ? `Chatting with ${S.chat.model}` : "Pick a model, attach files, and start chatting.";
  const chips = $("#empty-presets");
  chips.innerHTML = "";
  if (!S.chat.presetName) for (const p of S.presets.slice(0, 8)) chips.append(el("button", { class: "btn sm", onclick: () => newChat(p) }, p.name));
}

function renderMsg(m, i) {
  const node = el("div", { class: `msg ${m.role}${m.error ? " error" : ""}`, "data-i": i });
  fillMsg(node, m, i);
  return node;
}

function fillMsg(node, m, i) {
  node.innerHTML = "";
  if (m.role === "user") {
    const chips = attachmentChips(m.attachments);
    if (chips) node.append(chips);
    if (m.content) node.append(el("div", { class: "bubble", text: m.content }));
  } else {
    if (S.settings.show_model_name !== false && m.model) node.append(el("div", { class: "who", text: m.model.split("/").pop() }));
    const bubble = el("div", { class: "bubble" });
    const { think, answer, thinkingOpen } = splitThink(m.content, m.reasoning);
    if (think && S.settings.show_reasoning !== false) {
      const d = el("details", { class: "think" }, el("summary", { text: thinkingOpen && m.streaming ? "Thinking…" : "Reasoning" }), el("div", { class: "md", text: think }));
      if (thinkingOpen && m.streaming) d.open = true;
      bubble.append(d);
    }
    const md = mdToEl(answer);
    if (m.streaming) md.classList.add("cursor");
    bubble.append(md);
    node.append(bubble);
  }
  if (!m.streaming) node.append(msgActions(m, i));
}

function msgActions(m, i) {
  const a = el("div", { class: "actions" });
  const btn = (label, title, fn) => el("button", { class: "icon-btn", title, onclick: fn }, label);
  if (m.versions && m.versions.length > 1) {
    a.append(el("span", { class: "versions" },
      btn("‹", "Previous version", () => switchVersion(i, -1)),
      `${m.v + 1}/${m.versions.length}`,
      btn("›", "Next version", () => switchVersion(i, 1))));
  }
  a.append(btn("⧉", "Copy", () => copyText(splitThink(m.content).answer)));
  if (m.role === "user") a.append(btn("✎", "Edit & resend", () => editMsg(i)));
  if (m.role === "assistant") a.append(btn("↻", "Regenerate", () => regenerate(i)));
  a.append(btn("⑂", "Fork chat from here", () => forkFrom(i)));
  a.append(btn("🗑", "Delete message", () => deleteMsg(i)));
  return a;
}

function msgNode(chat, i) {
  if (S.chat !== chat) return null;
  return $(`#messages .msg[data-i="${i}"]`);
}

// ------------------------------------------------------------------ message actions

function switchVersion(i, d) {
  const m = S.chat.messages[i];
  m.v = (m.v + d + m.versions.length) % m.versions.length;
  Object.assign(m, m.versions[m.v]);
  renderMessages();
  saveChat(S.chat);
}

function editMsg(i) {
  if (S.streams.has(S.chat)) return toast("Wait for the reply to finish");
  const m = S.chat.messages[i];
  const node = msgNode(S.chat, i);
  const ta = el("textarea", {}, m.content);
  ta.value = m.content;
  node.innerHTML = "";
  node.append(el("div", { class: "edit-box", style: "width:100%" }, ta,
    el("div", { class: "row" },
      el("button", { class: "btn", onclick: () => renderMessages() }, "Cancel"),
      el("button", { class: "btn primary", onclick: () => {
        m.content = ta.value;
        S.chat.messages.splice(i + 1);
        renderMessages();
        complete(S.chat);
      } }, "Save & send"))));
  ta.focus();
}

function regenerate(i) {
  if (S.streams.has(S.chat)) return toast("Wait for the reply to finish");
  const chat = S.chat;
  const m = chat.messages[i];
  if (i < chat.messages.length - 1 && !confirm("Regenerating removes the messages after this one. Continue?")) return;
  chat.messages.splice(i + 1);
  if (!m.versions) { m.versions = [{ content: m.content, reasoning: m.reasoning, model: m.model }]; m.v = 0; }
  complete(chat, { target: m });
}

function deleteMsg(i) {
  if (S.streams.has(S.chat)) return toast("Wait for the reply to finish");
  S.chat.messages.splice(i, 1);
  renderMessages();
  if (S.chat.id) saveChat(S.chat);
}

async function forkFrom(i) {
  const src = S.chat;
  const fork = {
    title: `${src.title} (fork)`, model: src.model, system_prompt: src.system_prompt,
    params: { ...src.params }, messages: structuredClone(src.messages.slice(0, i + 1).map(stripTransient)),
  };
  await saveChat(fork);
  S.chat = fork;
  renderAll();
  toast("Forked into a new chat");
}

// ------------------------------------------------------------------ attachments

$("#attach-btn").addEventListener("click", () => $("#file-input").click());
$("#file-input").addEventListener("change", (e) => { uploadFiles([...e.target.files]); e.target.value = ""; });
$("#input").addEventListener("paste", (e) => {
  const files = [...(e.clipboardData?.files || [])];
  if (files.length) { e.preventDefault(); uploadFiles(files); }
});
const main = $(".main");
main.addEventListener("dragover", (e) => { if (e.dataTransfer?.types?.includes("Files")) { e.preventDefault(); $("#drop-hint").classList.remove("hidden"); } });
main.addEventListener("dragleave", (e) => { if (!main.contains(e.relatedTarget)) $("#drop-hint").classList.add("hidden"); });
main.addEventListener("drop", (e) => {
  e.preventDefault();
  $("#drop-hint").classList.add("hidden");
  uploadFiles([...(e.dataTransfer?.files || [])]);
});

async function uploadFiles(files) {
  if (!files.length) return;
  const placeholders = files.map((f) => ({ tmp: uid(), name: f.name, uploading: true }));
  S.pending.push(...placeholders);
  renderAttachments(); updateSendBtn();
  const fd = new FormData();
  files.forEach((f) => fd.append("file", f, f.name));
  try {
    const res = await api("/api/files", { method: "POST", body: fd });
    S.pending = S.pending.filter((p) => !placeholders.includes(p)).concat(res);
    const binary = res.filter((r) => r.kind === "binary").map((r) => r.name);
    if (binary.length) toast(`Can't read ${binary.join(", ")} as text — the model will only see the file name/type.`, 5000);
  } catch (err) {
    S.pending = S.pending.filter((p) => !placeholders.includes(p));
    toast("Upload failed: " + err.message, 4000);
  }
  renderAttachments(); updateSendBtn();
}

function renderAttachments() {
  const box = $("#attachments");
  box.innerHTML = "";
  for (const a of S.pending) {
    const label = a.uploading ? `⏳ ${a.name}` : `${a.kind === "image" ? "🖼" : a.kind === "text" ? "📄" : "📦"} ${a.name}`;
    const info = a.kind === "text" ? `${a.chars.toLocaleString()} chars` : a.kind === "image" ? "image" : a.kind === "binary" ? "binary — not readable" : "";
    box.append(el("span", { class: "chip", title: info },
      el("span", { text: label }),
      a.uploading ? null : el("button", { title: "Remove", onclick: () => { S.pending = S.pending.filter((p) => p !== a); renderAttachments(); updateSendBtn(); } }, "✕")));
  }
}

// ------------------------------------------------------------------ composer / sending

const input = $("#input");
function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, innerHeight * 0.4) + "px"; }
input.addEventListener("input", () => { autosize(); updateSendBtn(); });
input.addEventListener("keydown", (e) => {
  const enterSends = S.settings.enter_sends ?? !isTouch;
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing && enterSends) { e.preventDefault(); onSend(); }
});
$("#send-btn").addEventListener("click", onSend);

function updateSendBtn() {
  const b = $("#send-btn");
  const streaming = S.chat && S.streams.has(S.chat);
  b.classList.toggle("stop", !!streaming);
  b.textContent = streaming ? "■" : "➤";
  b.title = streaming ? "Stop" : "Send";
  b.disabled = !streaming && (S.pending.some((p) => p.uploading) || (!input.value.trim() && !S.pending.length));
}

function onSend() {
  const chat = S.chat;
  if (S.streams.has(chat)) { S.streams.get(chat).abort(); return; }
  const text = input.value.trim();
  if (!text && !S.pending.length) return;
  if (S.pending.some((p) => p.uploading)) return;
  if (!chat.model) { openModelPicker(); return toast("Choose a model first"); }
  chat.messages.push({ id: uid(), role: "user", content: text, attachments: S.pending.map(({ id, name, mime, size, kind }) => ({ id, name, mime, size, kind })) });
  input.value = ""; autosize();
  S.pending = [];
  renderAttachments();
  renderMessages();
  complete(chat);
}

function contextMessages(chat, upto) {
  let msgs = chat.messages.slice(0, upto).filter((m) => !m.error);
  const n = parseInt(chat.params?.context_messages, 10);
  if (n > 0) msgs = msgs.slice(-n);
  return msgs.map((m) => ({ role: m.role, content: m.content, attachments: m.attachments }));
}

async function complete(chat, { target } = {}) {
  let m = target;
  if (m) {
    m.versions.push({ content: "", reasoning: "", model: chat.model });
    m.v = m.versions.length - 1;
    Object.assign(m, { content: "", reasoning: "", model: chat.model, error: false });
  } else {
    m = { id: uid(), role: "assistant", content: "", reasoning: "", model: chat.model };
    chat.messages.push(m);
  }
  const idx = chat.messages.indexOf(m);
  m.streaming = true;
  const ctrl = new AbortController();
  S.streams.set(chat, ctrl);
  if (S.chat === chat) { renderMessages(); updateSendBtn(); }
  saveChat(chat).catch(() => {}); // persist the user message right away

  let pendingRender = false;
  const paint = () => {
    if (pendingRender) return;
    pendingRender = true;
    requestAnimationFrame(() => {
      pendingRender = false;
      const node = msgNode(chat, idx);
      if (!node) return;
      const box = $("#messages");
      const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
      fillMsg(node, m, idx);
      if (atBottom) box.scrollTop = box.scrollHeight;
    });
  };

  const started = performance.now();
  let usage = null;
  try {
    const r = await fetch("/api/complete", {
      method: "POST", signal: ctrl.signal, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: chat.model, system_prompt: chat.system_prompt, params: chat.params, messages: contextMessages(chat, idx) }),
    });
    if (!r.ok) {
      let msg = `${r.status}`;
      try { msg = (await r.json()).error || msg; } catch {}
      throw new Error(msg);
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    outer: while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") break outer;
        let j;
        try { j = JSON.parse(data); } catch { continue; }
        if (j.error) throw new Error(j.error.message || JSON.stringify(j.error));
        if (j.usage) usage = j.usage;
        const d = j.choices?.[0]?.delta || {};
        if (d.content) m.content += d.content;
        const rc = d.reasoning_content ?? d.reasoning;
        if (rc) m.reasoning += rc;
        if (d.content || rc) paint();
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      if (!m.content) { m.content = "⚠️ " + err.message; m.error = true; }
      else m.content += `\n\n⚠️ ${err.message}`;
    }
  } finally {
    m.streaming = false;
    if (m.versions) m.versions[m.v] = { content: m.content, reasoning: m.reasoning, model: m.model };
    S.streams.delete(chat);
    const secs = ((performance.now() - started) / 1000).toFixed(1);
    if (S.chat === chat) {
      renderMessages(); updateSendBtn();
      $("#status").textContent = usage ? `${usage.completion_tokens ?? "?"} tokens · ${secs}s` : `${secs}s`;
    }
    await saveChat(chat).catch((e) => toast("Save failed: " + e.message));
    maybeTitle(chat);
  }
}

async function maybeTitle(chat) {
  if (chat.titled || chat.messages.length < 2) return;
  const first = chat.messages.find((m) => m.role === "user");
  const reply = chat.messages.find((m) => m.role === "assistant" && !m.error);
  if (!first || !reply) return;
  if (chat.title !== "New chat" && chat.title !== chat.presetName) { chat.titled = true; return; }
  chat.titled = true;
  let title = (first.content || first.attachments?.[0]?.name || "New chat").replace(/\s+/g, " ").slice(0, 60);
  if (S.settings.auto_title === "ai") {
    try {
      const r = await api("/api/complete", { method: "POST", body: {
        model: S.settings.title_model || chat.model, stream: false, params: { max_tokens: 300, temperature: 0.3 },
        messages: [{ role: "user", content: `Write a short title (max 6 words) for a conversation that starts with:\n\n"${(first.content || "").slice(0, 1500)}"\n\nReply with only the title, no quotes.` }],
      } });
      const t = splitThink(r.choices?.[0]?.message?.content || "").answer.trim().replace(/^["'#*\s]+|["'*\s.]+$/g, "");
      if (t) title = t.slice(0, 80);
    } catch {}
  }
  chat.title = title;
  if (chat.id) await api(`/api/chats/${chat.id}`, { method: "PATCH", body: { title } });
  if (S.chat === chat) renderHeader();
  loadChats();
}

// ------------------------------------------------------------------ modal helpers

function openModal(title, body) {
  $("#modal-title").textContent = title;
  const b = $("#modal-body");
  b.innerHTML = "";
  b.append(body);
  if ($("#modal").classList.contains("hidden")) history.pushState({ layer: "modal" }, "");
  $("#modal").classList.remove("hidden");
}
function closeModal() { $("#modal").classList.add("hidden"); }
$("#modal-close").addEventListener("click", closeModal);
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeModal(); hideMenu(); } });
// Android back button closes the open modal / drawer instead of leaving the app.
addEventListener("popstate", () => {
  if (!$("#modal").classList.contains("hidden")) closeModal();
  else closeSidebarMobile();
});

const field = (label, node, hint) => el("div", {}, el("label", { text: label }), node, hint ? el("p", { class: "hint", text: hint }) : null);

// ------------------------------------------------------------------ model picker

$("#model-btn").addEventListener("click", openModelPicker);

async function openModelPicker() {
  const body = el("div");
  const search = el("input", { type: "search", placeholder: "Search models (e.g. llama, qwen, 70b)…" });
  const list = el("div", { class: "model-list" }, el("p", { class: "muted", text: "Loading models…" }));
  const custom = el("input", { placeholder: "…or type an exact model id" });
  body.append(search, list, field("Custom model id", custom),
    el("div", { class: "modal-actions" },
      el("button", { class: "btn", onclick: async () => { S.models = null; openModelPicker(); try { S.models = await api("/api/models?refresh=1"); draw(); } catch {} } }, "Refresh list"),
      el("button", { class: "btn primary", onclick: () => custom.value.trim() && pick(custom.value.trim()) }, "Use custom id")));
  openModal("Choose model", body);
  search.focus();

  const favs = () => new Set(S.settings.favorite_models || []);
  const pick = (id) => {
    S.chat.model = id;
    renderHeader();
    if (!S.chat.messages.length) renderEmpty();
    if (S.chat.id) saveChat(S.chat);
    saveSettings({ last_model: id });
    closeModal();
  };
  const draw = () => {
    if (!S.models) return;
    const q = search.value.toLowerCase().split(/\s+/).filter(Boolean);
    const f = favs();
    const items = S.models.filter((m) => q.every((w) => m.id.toLowerCase().includes(w)));
    items.sort((a, b) => (f.has(b.id) - f.has(a.id)));
    list.innerHTML = "";
    if (!items.length) list.append(el("p", { class: "muted", text: "No models match." }));
    for (const m of items.slice(0, 300)) {
      const star = el("button", { class: "star" + (f.has(m.id) ? " on" : ""), title: "Favorite", onclick: async (e) => {
        e.stopPropagation();
        const s = favs();
        s.has(m.id) ? s.delete(m.id) : s.add(m.id);
        await saveSettings({ favorite_models: [...s] });
        draw();
      } }, "★");
      list.append(el("div", { class: "model-row" + (m.id === S.chat.model ? " sel" : ""), onclick: () => pick(m.id) },
        star, el("span", { class: "id", text: m.id }),
        el("span", { class: "ctx", text: [m.model_class, m.context_length ? `${Math.round(m.context_length / 1024)}k ctx` : ""].filter(Boolean).join(" · ") })));
    }
    if (items.length > 300) list.append(el("p", { class: "muted", text: `${items.length - 300} more — refine your search.` }));
  };
  search.addEventListener("input", draw);
  try {
    S.models = S.models || await api("/api/models");
    draw();
  } catch (err) {
    list.innerHTML = "";
    list.append(el("p", { class: "err", text: err.message }));
  }
}

// ------------------------------------------------------------------ params editor (shared)

function paramsEditor(params) {
  const wrap = el("div", { class: "grid2" });
  const inputs = {};
  for (const [k, label, step, hint] of PARAMS) {
    inputs[k] = el("input", { type: "number", step, placeholder: "default", value: params[k] ?? "" });
    wrap.append(field(label, inputs[k], hint));
  }
  inputs.context_messages = el("input", { type: "number", step: 1, min: 0, placeholder: "all", value: params.context_messages ?? "" });
  wrap.append(field("Context: last N messages", inputs.context_messages, "limit history sent to the model"));
  const stop = el("textarea", { rows: 2, placeholder: "one stop sequence per line" });
  stop.value = Array.isArray(params.stop) ? params.stop.join("\n") : params.stop || "";
  const extra = el("textarea", { rows: 3, placeholder: '{"response_format": {"type": "json_object"}}', style: "font-family: var(--mono)" });
  extra.value = params.extra || "";
  const node = el("div", {}, wrap, field("Stop sequences", stop), field("Extra request JSON (advanced)", extra, "merged into the API request as-is"));
  const read = () => {
    const out = {};
    for (const k of Object.keys(inputs)) if (inputs[k].value !== "") out[k] = Number(inputs[k].value);
    if (stop.value.trim()) out.stop = stop.value.split("\n").filter(Boolean);
    if (extra.value.trim()) {
      try { JSON.parse(extra.value); out.extra = extra.value.trim(); }
      catch { throw new Error("Extra request JSON is not valid JSON"); }
    }
    return out;
  };
  return { node, read };
}

// ------------------------------------------------------------------ chat settings

$("#chat-settings-btn").addEventListener("click", openChatSettings);

function openChatSettings() {
  const c = S.chat;
  const body = el("div");
  const title = el("input", { value: c.title });
  const sys = el("textarea", { rows: 6, placeholder: "You are a helpful assistant…" });
  sys.value = c.system_prompt || "";
  const presetSel = el("select", {}, el("option", { value: "" }, "— apply a preset —"), S.presets.map((p) => el("option", { value: p.id }, p.name)));
  let pe = paramsEditor(c.params || {});
  const peBox = el("div", {}, pe.node);
  presetSel.addEventListener("change", () => {
    const p = S.presets.find((x) => x.id === presetSel.value);
    if (!p) return;
    sys.value = p.system_prompt || "";
    pe = paramsEditor(p.params || {});
    peBox.innerHTML = ""; peBox.append(pe.node);
    if (p.model) { c.model = p.model; renderHeader(); }
  });
  const collect = () => ({ system_prompt: sys.value, params: pe.read() });
  body.append(
    field("Title", title),
    ...(S.presets.length ? [field("Preset", presetSel)] : []),
    field("System prompt", sys, "Instructions the model sees before every conversation turn."),
    el("h4", { class: "section-h", text: "Sampling" }),
    el("p", { class: "hint", text: "Leave blank to use the model's default." }),
    peBox,
    el("div", { class: "modal-actions" },
      el("button", { class: "btn", onclick: async () => {
        try { const v = collect(); await saveSettings({ default_system_prompt: v.system_prompt, default_params: v.params, default_model: c.model }); toast("Saved as defaults for new chats"); } catch (e) { toast(e.message); }
      } }, "Make default"),
      el("button", { class: "btn", onclick: () => { try { editPreset({ ...collect(), model: c.model, name: "" }); } catch (e) { toast(e.message); } } }, "Save as preset"),
      el("button", { class: "btn primary", onclick: async () => {
        try {
          Object.assign(c, collect());
          if (title.value.trim()) { c.title = title.value.trim(); c.titled = true; }
          if (c.id) await saveChat(c);
          renderHeader(); closeModal(); toast("Chat settings saved");
        } catch (e) { toast(e.message); }
      } }, "Save")));
  openModal("Chat settings", body);
}

// ------------------------------------------------------------------ presets

function editPreset(p) {
  const isNew = !p || !p.id;
  p = p || {};
  const body = el("div");
  const name = el("input", { value: p.name || "", placeholder: "e.g. Code reviewer, Story writer" });
  const model = el("input", { value: p.model || "", placeholder: "model id (optional)" });
  const sys = el("textarea", { rows: 8 });
  sys.value = p.system_prompt || "";
  const pe = paramsEditor(p.params || {});
  body.append(field("Name", name), field("Model", model, "Leave empty to keep whatever model is selected."), field("System prompt", sys),
    el("h4", { class: "section-h", text: "Sampling" }), pe.node,
    el("div", { class: "modal-actions" },
      isNew ? null : el("button", { class: "btn danger", onclick: async () => {
        if (!confirm(`Delete preset "${p.name}"?`)) return;
        await api(`/api/presets/${p.id}`, { method: "DELETE" });
        S.presets = await api("/api/presets"); renderSidebar(); closeModal();
      } }, "Delete"),
      el("button", { class: "btn primary", onclick: async () => {
        try {
          const data = { name: name.value.trim() || "Untitled", model: model.value.trim() || null, system_prompt: sys.value, params: pe.read() };
          await api(isNew ? "/api/presets" : `/api/presets/${p.id}`, { method: isNew ? "POST" : "PUT", body: data });
          S.presets = await api("/api/presets"); renderSidebar(); closeModal(); toast("Preset saved");
          if (!S.chat.messages.length) renderEmpty();
        } catch (e) { toast(e.message); }
      } }, "Save")));
  openModal(isNew ? "New preset" : "Edit preset", body);
}

// ------------------------------------------------------------------ app settings

$("#open-settings").addEventListener("click", () => { closeSidebarMobile(); openSettings(); });

function openSettings() {
  const s = S.settings;
  const body = el("div");
  const key = el("input", { type: "password", placeholder: s.api_key_set ? `saved (${s.api_key_hint}) — type to replace` : "rc_…", autocomplete: "off" });
  const base = el("input", { value: s.base_url || "" });
  const theme = el("select", {}, ["system", "dark", "light"].map((t) => el("option", { value: t, selected: (s.theme || "system") === t }, t)));
  const accent = el("input", { type: "color", value: s.accent || "#7c5cff", style: "height:40px;padding:4px" });
  const font = el("input", { type: "number", min: 11, max: 24, value: s.font_size || 15 });
  const width = el("input", { type: "number", min: 500, max: 2000, step: 20, value: s.chat_width || 820 });
  const fontFam = el("input", { value: s.font_family || "", placeholder: "system default, e.g. Georgia, serif" });
  const greeting = el("input", { value: s.greeting || "", placeholder: "How can I help?" });
  const enter = el("select", {}, [["", "Default (desktop: Enter, phone: button)"], ["true", "Enter sends"], ["false", "Enter = new line"]].map(([v, l]) => el("option", { value: v, selected: String(s.enter_sends ?? "") === v }, l)));
  const autoTitle = el("select", {}, [["first", "First words of the message"], ["ai", "Ask the model for a title"]].map(([v, l]) => el("option", { value: v, selected: (s.auto_title || "first") === v }, l)));
  const titleModel = el("input", { value: s.title_model || "", placeholder: "same as chat (or a small, fast model id)" });
  const showReason = el("input", { type: "checkbox", checked: s.show_reasoning !== false });
  const showModel = el("input", { type: "checkbox", checked: s.show_model_name !== false });
  const maxChars = el("input", { type: "number", step: 1000, value: s.max_file_chars || 200000 });
  const css = el("textarea", { rows: 5, placeholder: ".msg.user .bubble { border-radius: 4px; }", style: "font-family: var(--mono)" });
  css.value = s.custom_css || "";
  const importInput = el("input", { type: "file", accept: "application/json", hidden: true, onchange: async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const r = await api("/api/import", { method: "POST", body: await f.text() , headers: { "Content-Type": "application/json" } });
      S.presets = await api("/api/presets"); await loadChats(); toast(`Imported ${r.imported} chat(s)`);
    } catch (err) { toast("Import failed: " + err.message, 4000); }
  } });

  body.append(
    el("h4", { class: "section-h", text: "Connection" }),
    field("Featherless API key", key, "Stored on your server, never sent back to the browser. Get one at featherless.ai → Account → API keys."),
    field("API base URL", base, "Any OpenAI-compatible endpoint works (Featherless, OpenRouter, a local llama.cpp/vLLM…)."),
    el("h4", { class: "section-h", text: "Appearance" }),
    el("div", { class: "grid2" }, field("Theme", theme), field("Accent color", accent), field("Font size (px)", font), field("Chat width (px)", width)),
    field("Font family", fontFam), field("Empty-chat greeting", greeting),
    el("label", { class: "check" }, showReason, "Show model reasoning / <think> blocks"),
    el("label", { class: "check" }, showModel, "Show model name above replies"),
    field("Custom CSS", css, "Restyle anything. Applied live after saving."),
    el("h4", { class: "section-h", text: "Behaviour" }),
    el("div", { class: "grid2" }, field("Enter key", enter), field("Chat titles", autoTitle)),
    field("Title model", titleModel),
    field("Max characters per attached file", maxChars, "Longer files are truncated so they fit the model's context."),
    el("h4", { class: "section-h", text: "Data" }),
    el("div", { class: "modal-actions", style: "justify-content:flex-start" },
      el("button", { class: "btn", onclick: () => location.assign("/api/export") }, "⬇ Back up everything"),
      el("button", { class: "btn", onclick: () => importInput.click() }, "⬆ Import backup / chat"), importInput,
      el("button", { class: "btn", onclick: async () => { await api("/api/logout", { method: "POST" }); location.reload(); } }, "Log out")),
    el("div", { class: "modal-actions" },
      el("button", { class: "btn primary", onclick: async () => {
        const patch = {
          base_url: base.value.trim(), theme: theme.value, accent: accent.value, font_size: Number(font.value) || 15,
          chat_width: Number(width.value) || 820, font_family: fontFam.value.trim(), greeting: greeting.value.trim(),
          enter_sends: enter.value === "" ? null : enter.value === "true", auto_title: autoTitle.value, title_model: titleModel.value.trim(),
          show_reasoning: showReason.checked, show_model_name: showModel.checked, max_file_chars: Number(maxChars.value) || 200000,
          custom_css: css.value,
        };
        if (key.value.trim()) patch.api_key = key.value.trim();
        const baseChanged = patch.base_url !== s.base_url;
        await saveSettings(patch);
        if (baseChanged || patch.api_key) S.models = null;
        renderMessages(); closeModal(); toast("Settings saved");
      } }, "Save")));
  openModal("Settings", body);
}

// ------------------------------------------------------------------ PWA

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
matchMedia("(prefers-color-scheme: light)").addEventListener("change", applySettings);

boot().catch((e) => { document.body.textContent = "Failed to start: " + e.message; });
