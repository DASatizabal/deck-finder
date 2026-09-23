// Bump VERSION on every release (it must match APP_VERSION and version.json), so phones grab the update.
const VERSION = "deckfinder-v1.4.0";
const FILES = ["./", "./index.html", "./version.json", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
const TIMEOUT_MS = 3000;

self.addEventListener("install", e => {
  // cache: "reload" skips the browser's HTTP cache so a new release never saves old files.
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(FILES.map(f => new Request(f, { cache: "reload" })))));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// The app's "Tap to update" banner sends this to switch to the new version right away.
self.addEventListener("message", e => { if (e.data === "SKIP_WAITING") self.skipWaiting(); });

// index.html and version.json: try the network for up to 3 seconds, then use the saved copy (offline at sea).
function networkFirst(req, isPage){
  const url = new URL(req.url); url.search = "";
  const saved = () => caches.match(url.href).then(hit => hit || (isPage ? caches.match("./index.html") : undefined));
  const net = fetch(new Request(url.href, { cache: "no-store" })).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(url.href, copy)); }
    return res;
  });
  const fromNet = net.catch(() => saved().then(hit => hit || Response.error()));
  // After 3 seconds use the saved copy if there is one, otherwise keep waiting for the network.
  const slow = new Promise(r => setTimeout(r, TIMEOUT_MS)).then(saved).then(hit => hit || fromNet);
  return Promise.race([fromNet, slow]);
}

self.addEventListener("fetch", e => {
  // Only handle this app's own files. Itinerary lookups go straight to the network.
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  const path = new URL(e.request.url).pathname;
  const scope = new URL(self.registration.scope).pathname;
  const isPage = e.request.mode === "navigate" || path === scope || path === scope + "index.html";
  if (isPage || path === scope + "version.json") { e.respondWith(networkFirst(e.request, isPage)); return; }
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then(hit => hit || fetch(e.request).catch(() => caches.match("./index.html")))
  );
});
