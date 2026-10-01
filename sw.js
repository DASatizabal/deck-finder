// Bump VERSION on every release (it must match APP_VERSION and version.json), so phones grab the update.
const VERSION = "deckfinder-v1.16.2";
// Each ship saved for offline lives in its own cache, "deckfinder-ship-<line>-<ship>".
// These are NOT tied to the app version: they stay until that ship's hash in ships/index.json changes.
const SHIP_CACHE_PREFIX = "deckfinder-ship-";
// Island maps work the same way: each lives in its own cache, "deckfinder-place-<id>".
const PLACE_CACHE_PREFIX = "deckfinder-place-";
const FILES = ["./", "./index.html", "./version.json", "./ships/index.json", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
const TIMEOUT_MS = 3000;

self.addEventListener("install", e => {
  // cache: "reload" skips the browser's HTTP cache so a new release never saves old files.
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(FILES.map(f => new Request(f, { cache: "reload" })))));
});
self.addEventListener("activate", e => {
  // Remove old app versions, but never the saved ships or island maps.
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION && !k.startsWith(SHIP_CACHE_PREFIX) && !k.startsWith(PLACE_CACHE_PREFIX)).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// The app's "Tap to update" banner sends this to switch to the new version right away.
self.addEventListener("message", e => { if (e.data === "SKIP_WAITING") self.skipWaiting(); });

// index.html, version.json and ships/index.json: try the network for up to 3 seconds,
// then use the saved copy (offline at sea).
function networkFirst(req, isPage){
  const url = new URL(req.url); url.search = "";
  const saved = () => caches.match(url.href, { cacheName: VERSION }).then(hit => hit || (isPage ? caches.match("./index.html", { cacheName: VERSION }) : undefined));
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
  const url = new URL(e.request.url);
  const scope = new URL(self.registration.scope).pathname;
  const rel = url.pathname.startsWith(scope) ? url.pathname.slice(scope.length) : url.pathname;
  // Add to calendar (1.12.0): the app puts the calendar file in the address and this answers it as a
  // real .ics file, so an iPhone shows its Add to Calendar screen. It never touches the network.
  if (rel === "calendar.ics") {
    const d = url.searchParams.get("d") || "";
    const name = (url.searchParams.get("n") || "event.ics").replace(/[^\w.-]/g, "").slice(0, 80) || "event.ics";
    let text = "";
    try { text = new TextDecoder().decode(Uint8Array.from(atob(d.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0))); } catch (err) {}
    e.respondWith(/^BEGIN:VCALENDAR\r\n/.test(text)
      ? new Response(text, { headers: { "Content-Type": "text/calendar; charset=utf-8", "Content-Disposition": 'inline; filename="' + name + '"', "X-Content-Type-Options": "nosniff" } })
      : new Response("That calendar link is broken. Go back to Deck Finder and tap Add to calendar again.", { status: 400, headers: { "Content-Type": "text/plain; charset=utf-8" } }));
    return;
  }
  const isPage = e.request.mode === "navigate" || rel === "" || rel === "index.html";
  if (isPage || rel === "version.json" || rel === "ships/index.json") { e.respondWith(networkFirst(e.request, isPage)); return; }

  // Ship files (ships/<line>/<ship>/<file>, and since 1.16.0 files in a ship's subfolder like
  // walkable/deck5.json): use the saved copy for that ship if there is one.
  const ship = rel.match(/^ships\/([^/]+)\/([^/]+)\/.+$/);
  if (ship) {
    if (url.search) return; // "?v=" means the app is downloading this ship for offline: go to the network
    const cacheName = SHIP_CACHE_PREFIX + ship[1] + "-" + ship[2];
    e.respondWith(caches.match(url.href, { cacheName }).then(hit => hit || fetch(e.request)));
    return;
  }
  // Island map files (places/<id>/<file>): the same, from that island's own cache.
  const place = rel.match(/^places\/([^/]+)\/[^/]+$/);
  if (place) {
    if (url.search) return; // downloading this island for offline: go to the network
    const cacheName = PLACE_CACHE_PREFIX + place[1];
    e.respondWith(caches.match(url.href, { cacheName }).then(hit => hit || fetch(e.request)));
    return;
  }

  e.respondWith(
    caches.match(e.request, { ignoreSearch: true, cacheName: VERSION }).then(hit => hit || fetch(e.request).catch(() => caches.match("./index.html", { cacheName: VERSION })))
  );
});
