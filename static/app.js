"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  chats: [],
  activeId: null,
  activeChat: null,
  filter: "active",
  attachments: [],
  streaming: false,
  abort: null,
};

const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function renderMarkdown(text) {
  const raw = marked.parse(text || "", { breaks: true, gfm: true });
  return DOMPurify.sanitize(raw);
}

function enhanceCode(root) {
  root.querySelectorAll("pre code").forEach((block) => {
    if (block.dataset.done) return;
    block.dataset.done = "1";
    try { hljs.highlightElement(block); } catch (e) {}
    const btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.textContent = "Copy";
    btn.onclick = () => {
      navigator.clipboard.writeText(block.textContent);
      btn.textContent = "Copied!";
      setTimeout(() => (btn.textContent = "Copy"), 1200);
    };
    block.parentElement.appendChild(btn);
  });
}

function renderMessage(m) {
  const div = document.createElement("div");
  div.className = "msg " + m.role;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.innerHTML = `<span>${esc(m.role === "user" ? "You" : "Assistant")}</span><button class="msg-del" data-id="${m.id}" title="Delete">✕</button>`;
  const body = document.createElement("div");
  body.className = "body";
  body.innerHTML = renderMarkdown(m.content);
  div.appendChild(meta);
  div.appendChild(body);
  if (m.attachments && m.attachments.length) {
    const atts = document.createElement("div");
    atts.innerHTML = m.attachments
      .map((a) => `<span class="att-chip">📄 <a href="/api/files/${a.id}/${encodeURIComponent(a.name)}">${esc(a.name)}</a></span>`)
      .join("");
    div.appendChild(atts);
  }
  meta.querySelector(".msg-del").onclick = async () => {
    await fetch("/api/messages/" + m.id, { method: "DELETE" });
    div.remove();
  };
  return div;
}

function renderMessages(messages) {
  const box = $("messages");
  box.innerHTML = "";
  messages.forEach((m) => {
    const el = renderMessage(m);
    box.appendChild(el);
    enhanceCode(el);
  });
  box.scrollTop = box.scrollHeight;
}

function renderChatList() {
  const list = $("chat-list");
  list.innerHTML = "";
  state.chats
    .filter((c) => (state.filter === "archived" ? c.archived : !c.archived))
    .forEach((c) => {
      const item = document.createElement("div");
      item.className = "chat-item" + (c.id === state.activeId ? " active" : "");
      item.innerHTML = `<span class="title">${esc(c.title)}</span><span class="pins">${c.pinned ? "📌" : ""}${c.share_id ? "🔗" : ""}</span>`;
      item.onclick = () => openChat(c.id);
      list.appendChild(item);
    });
}

async function refreshChats() {
  const r = await fetch("/api/chats");
  state.chats = await r.json();
  renderChatList();
}

async function openChat(id) {
  state.activeId = id;
  const r = await fetch("/api/chats/" + id);
  state.activeChat = await r.json();
  $("chat-title").value = state.activeChat.title;
  $("chat-title").disabled = false;
  if (state.activeChat.model) $("model-select").value = state.activeChat.model;
  $("btn-pin").textContent = state.activeChat.pinned ? "📌✓" : "📌";
  $("btn-archive").textContent = state.activeChat.archived ? "📦✓" : "📦";
  renderMessages(state.activeChat.messages);
  renderChatList();
  if (window.innerWidth <= 800) $("sidebar").classList.remove("open");
}

async function newChat() {
  const r = await fetch("/api/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const chat = await r.json();
  await refreshChats();
  await openChat(chat.id);
}

async function loadModels(selectValue) {
  const sel = $("model-select");
  const saved = await (await fetch("/api/settings")).json();
  let models = saved.models || [];
  const r = await fetch("/api/models").catch(() => null);
  if (r && r.ok) {
    const data = await r.json();
    if (Array.isArray(data.models) && data.models.length) models = data.models;
  }
  sel.innerHTML = '<option value="">Select model…</option>' + models.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
  if (selectValue) sel.value = selectValue;
}

async function sendMessage() {
  const prompt = $("prompt");
  const text = prompt.value.trim();
  if (!text || state.streaming || !state.activeId) return;
  const model = $("model-select").value;
  if (!model) { alert("Pick a model first (top bar)."); return; }
  const userMsg = { id: "tmp-user", role: "user", content: text, attachments: state.attachments };
  renderMessages([...(state.activeChat.messages || []), userMsg]);
  prompt.value = "";
  autoGrow(prompt);
  const attachments = state.attachments;
  state.attachments = [];
  renderAttachments();

  const aiBody = document.createElement("div");
  aiBody.className = "msg assistant";
  aiBody.innerHTML = '<div class="meta"><span>Assistant</span></div><div class="body"></div>';
  $("messages").appendChild(aiBody);
  $("messages").scrollTop = $("messages").scrollHeight;

  state.streaming = true;
  $("btn-send").classList.add("hidden");
  $("btn-stop").classList.remove("hidden");
  const bodyEl = aiBody.querySelector(".body");
  let acc = "";
  state.abort = new AbortController();
  try {
    const resp = await fetch(`/api/chats/${state.activeId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: state.abort.signal,
      body: JSON.stringify({
        model,
        save_user_message: true,
        user_content: text,
        attachments,
        temperature: 0.7,
        max_tokens: 2048,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      bodyEl.textContent = "Error: " + (err.error || resp.status);
    } else {
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (payload === "[DONE]") continue;
          try {
            const evt = JSON.parse(payload);
            if (evt.token) acc += evt.token;
            if (evt.final) acc = evt.final.content;
          } catch (e) {}
          bodyEl.innerHTML = renderMarkdown(acc);
          $("messages").scrollTop = $("messages").scrollHeight;
        }
      }
      enhanceCode(aiBody);
    }
  } catch (e) {
    if (e.name !== "AbortError") bodyEl.textContent = "Error: " + e.message;
  } finally {
    state.streaming = false;
    state.abort = null;
    $("btn-send").classList.remove("hidden");
    $("btn-stop").classList.add("hidden");
    const r = await fetch("/api/chats/" + state.activeId);
    state.activeChat = await r.json();
    renderMessages(state.activeChat.messages);
    if (!state.activeChat.title || state.activeChat.title === "New chat") {
      const title = text.slice(0, 40) || "New chat";
      await patchChat({ title });
    }
    refreshChats();
  }
}

async function patchChat(fields) {
  if (!state.activeId) return;
  await fetch("/api/chats/" + state.activeId, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  await refreshChats();
}

function renderAttachments() {
  $("attachments").innerHTML = state.attachments
    .map((a, i) => `<span class="att-chip">📄 ${esc(a.name)} <button data-i="${i}" title="Remove">✕</button></span>`)
    .join("");
  $("attachments").querySelectorAll("button").forEach((b) => {
    b.onclick = () => { state.attachments.splice(+b.dataset.i, 1); renderAttachments(); };
  });
}

function autoGrow(ta) {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/files", { method: "POST", body: fd });
  if (!r.ok) { alert("Upload failed (max 10 MB)"); return; }
  state.attachments.push(await r.json());
  renderAttachments();
}

// ---------- init & wiring ----------

window.addEventListener("DOMContentLoaded", async () => {
  const status = await (await fetch("/api/status")).json();
  loadModels();

  $("btn-new").onclick = newChat;
  $("btn-send").onclick = sendMessage;
  $("btn-stop").onclick = () => state.abort && state.abort.abort();
  $("prompt").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  $("prompt").addEventListener("input", (e) => autoGrow(e.target));

  $("btn-attach").onclick = () => $("file-input").click();
  $("file-input").onchange = (e) => {
    for (const f of e.target.files) uploadFile(f);
    e.target.value = "";
  };

  $("chat-title").addEventListener("change", (e) => patchChat({ title: e.target.value }));
  $("model-select").addEventListener("change", (e) => patchChat({ model: e.target.value }));
  $("btn-pin").onclick = () => {
    const c = state.chats.find((c) => c.id === state.activeId);
    patchChat({ pinned: !c.pinned }).then(() => {
      state.activeChat.pinned = !c.pinned;
      $("btn-pin").textContent = state.activeChat.pinned ? "📌✓" : "📌";
    });
  };
  $("btn-archive").onclick = () => {
    const c = state.chats.find((c) => c.id === state.activeId);
    patchChat({ archived: !c.archived }).then(() => {
      $("btn-archive").textContent = !c.archived ? "📦✓" : "📦";
    });
  };
  $("btn-delete").onclick = async () => {
    if (!state.activeId || !confirm("Delete this chat?")) return;
    await fetch("/api/chats/" + state.activeId, { method: "DELETE" });
    state.activeId = null;
    state.activeChat = null;
    renderMessages([]);
    $("chat-title").value = "";
    await refreshChats();
  };
  $("btn-share").onclick = async () => {
    if (!state.activeId) return;
    const r = await fetch(`/api/chats/${state.activeId}/share`, { method: "POST" });
    const data = await r.json();
    const url = location.origin + "/share/" + data.share_id;
    await navigator.clipboard.writeText(url).catch(() => {});
    alert("Share link copied:\n" + url);
    refreshChats();
  };

  $("btn-menu").onclick = () => $("sidebar").classList.toggle("open");
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.filter = tab.dataset.filter;
      renderChatList();
    };
  });

  $("btn-export").onclick = () => (location.href = "/api/export");
  $("btn-import").onclick = () => $("import-file").click();
  $("import-file").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const text = await file.text();
    const r = await fetch("/api/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: text });
    const data = await r.json();
    alert("Imported " + data.imported + " chats");
    refreshChats();
  };

  $("btn-settings").onclick = async () => {
    const s = await (await fetch("/api/settings")).json();
    $("set-theme").value = s.theme || "dark";
    $("set-models").value = (s.models || []).join("\n");
    $("set-api-key").value = "";
    $("settings-modal").classList.remove("hidden");
    $("modal-backdrop").classList.remove("hidden");
  };
  const closeSettings = () => {
    $("settings-modal").classList.add("hidden");
    $("modal-backdrop").classList.add("hidden");
  };
  $("btn-settings-close").onclick = closeSettings;
  $("modal-backdrop").onclick = closeSettings;
  $("btn-load-models").onclick = async () => {
    const r = await fetch("/api/models");
    const data = await r.json();
    if (data.models) $("set-models").value = data.models.join("\n");
    else alert("Could not load models: " + (data.error || ""));
  };
  $("btn-refresh-models").onclick = () => loadModels($("model-select").value);
  $("btn-settings-save").onclick = async () => {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        theme: $("set-theme").value,
        models: $("set-models").value.split("\n").map((s) => s.trim()).filter(Boolean),
        api_key: $("set-api-key").value || undefined,
      }),
    });
    document.body.dataset.theme = $("set-theme").value;
    loadModels($("model-select").value);
    closeSettings();
  };

  const theme = (await (await fetch("/api/settings")).json()).theme;
  document.body.dataset.theme = theme || "dark";

  await refreshChats();
  await newChat();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  }
});
