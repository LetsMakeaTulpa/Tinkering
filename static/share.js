const chat = JSON.parse(document.getElementById("chat-data").textContent);
document.getElementById("share-title").textContent = chat.title;
const box = document.getElementById("share-messages");
const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
chat.messages.forEach((m) => {
  const div = document.createElement("div");
  div.className = "msg " + m.role;
  div.innerHTML =
    '<div class="meta">' + esc(m.role === "user" ? "You" : "Assistant") + "</div>" +
    '<div class="body">' + DOMPurify.sanitize(marked.parse(m.content || "", { breaks: true })) + "</div>";
  box.appendChild(div);
});
