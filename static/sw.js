/* Service worker: caches the app shell so the PWA opens instantly and installs on Android.
   API calls always go to the network. Bump VERSION when static files change. */
const VERSION = "fc-v1";
const SHELL = [
  "/", "/static/style.css", "/static/app.js", "/manifest.webmanifest",
  "/static/vendor/marked.min.js", "/static/vendor/purify.min.js", "/static/vendor/highlight.min.js",
  "/static/vendor/hljs-dark.css", "/static/vendor/hljs-light.css", "/static/icons/icon-192.png", "/static/icons/icon-512.png",
];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/") || url.pathname.startsWith("/s/")) return;
  // Network first (so updates show up), cache as offline fallback.
  e.respondWith(
    fetch(e.request).then((r) => {
      if (r.ok) { const copy = r.clone(); caches.open(VERSION).then((c) => c.put(e.request, copy)); }
      return r;
    }).catch(() => caches.match(e.request))
  );
});
