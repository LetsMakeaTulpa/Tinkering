/* Read-only shared chat page. CHAT is injected by the server. */
"use strict";
document.getElementById("t").textContent = CHAT.title;
document.getElementById("m").textContent = CHAT.model ? `Model: ${CHAT.model}` : "";
document.documentElement.dataset.theme = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
marked.setOptions({ gfm: true, breaks: true });
const box = document.getElementById("msgs");
for (const m of CHAT.messages) {
  const node = document.createElement("div");
  node.className = `msg ${m.role}`;
  if (m.role === "assistant" && m.model) {
    const who = document.createElement("div");
    who.className = "who";
    who.textContent = m.model.split("/").pop();
    node.append(who);
  }
  if (m.attachments && m.attachments.length) {
    const row = document.createElement("div");
    row.className = "att-row";
    for (const a of m.attachments) {
      const c = document.createElement("span");
      c.className = "chip";
      c.textContent = "📎 " + a.name;
      row.append(c);
    }
    node.append(row);
  }
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (m.role === "user") bubble.textContent = m.content;
  else {
    const md = document.createElement("div");
    md.className = "md";
    // Hide <think> reasoning on shared pages.
    const text = (m.content || "").replace(/^\s*<think>[\s\S]*?(<\/think>|$)/, "");
    md.innerHTML = DOMPurify.sanitize(marked.parse(text));
    md.querySelectorAll("pre code").forEach((c) => { try { hljs.highlightElement(c); } catch {} });
    bubble.append(md);
  }
  node.append(bubble);
  box.append(node);
}
