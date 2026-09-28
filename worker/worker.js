// Deck Finder lookup helper (Cloudflare Worker)
// It fetches two kinds of NCL pages for the Deck Finder app and adds the
// "this app may read this" header that browsers require. Nothing else is allowed through.
//
// Since app version 1.9.0 it also has an /itinerary route that asks CruiseFeed
// (https://api.cruisefeed.io) for sailings NCL no longer lists (sold out or already sailed):
//   GET /itinerary?ship=Norwegian%20Getaway&line=Norwegian%20Cruise%20Line&date=2026-10-02
//   with the header X-DeckFinder-Pass: <the family passphrase>
// It needs two Worker secrets (Settings, Variables and Secrets):
//   CRUISEFEED_KEY  the CruiseFeed API key. Never put it in this file or anywhere in the repo.
//   APP_PASS        the family passphrase the app sends.
// and one KV namespace binding (Bindings), shared by every phone:
//   ITINERARIES     saved itineraries, key "itin:<cruise line>:<ship>:<YYYY-MM-DD>", no expiry.
//                   tools/kv_put.py writes to it too (for example an itinerary captured from NCL).
// This folder is not published to the website. Paste this file into the Cloudflare dashboard.

const ALLOWED = [
  /^\/api\/v2\/vacations\/search\?[A-Za-z0-9=&%,\-_.]*$/, // sailing search
  /^\/cruises\/[A-Z0-9]+$/                                 // one itinerary page
];

export default {
  async fetch(request, env, ctx) {
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "X-DeckFinder-Pass"
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "GET") return new Response("Only GET is allowed", { status: 405, headers: cors });

    const url = new URL(request.url);
    if (url.pathname === "/itinerary") return itinerary(request, url, env || {}, ctx, cors);

    const path = url.searchParams.get("path") || "";
    if (!ALLOWED.some(rule => rule.test(path))) {
      return new Response("That address isn't on the allowed list", { status: 400, headers: cors });
    }
    const upstream = await fetch("https://www.ncl.com" + path, {
      // Note: asking for "text/html" makes NCL redirect to a page without the data, so we ask for anything (*/*).
      headers: { "User-Agent": "Mozilla/5.0 (Deck Finder personal app)", "Accept": "*/*" },
      cf: { cacheTtl: 3600, cacheEverything: true }
    });
    const headers = new Headers(cors);
    headers.set("Content-Type", upstream.headers.get("Content-Type") || "text/plain");
    return new Response(upstream.body, { status: upstream.status, headers });
  }
};

// ---------- /itinerary: CruiseFeed lookup for sold-out and past sailings ----------
// Each CruiseFeed lookup spends one result from a small allowance that never resets, so:
// the passphrase is checked first, the ITINERARIES KV namespace is checked next, and only a
// sailing that isn't saved there yet costs one CruiseFeed result (asking for exactly one sailing).
// The found itinerary is saved to KV with no expiry, so every phone shares it from then on.
// KV holds only public sailing data, never anything from the request (passphrase, IP, phone).

function reply(obj, status, cors) {
  const headers = new Headers(cors);
  headers.set("Content-Type", "application/json");
  headers.set("Cache-Control", "no-store");
  return new Response(JSON.stringify(obj), { status, headers });
}

// Compare the passphrase in constant time (hashing first hides the length too).
async function samePass(given, expected) {
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([given, expected].map(s => crypto.subtle.digest("SHA-256", enc.encode(s))));
  if (crypto.subtle.timingSafeEqual) return crypto.subtle.timingSafeEqual(a, b);
  const x = new Uint8Array(a), y = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

async function itinerary(request, url, env, ctx, cors) {
  if (!env.APP_PASS || !env.CRUISEFEED_KEY) {
    return reply({ code: "not_configured", error: "The helper needs its CRUISEFEED_KEY and APP_PASS secrets." }, 500, cors);
  }
  // The app sends the passphrase through encodeURIComponent, so any character is safe in a header.
  let pass = request.headers.get("X-DeckFinder-Pass") || "";
  try { pass = decodeURIComponent(pass); } catch (e) {}
  if (!pass || !(await samePass(pass, env.APP_PASS))) {
    return reply({ code: "bad_pass", error: "The family passphrase wasn't accepted." }, 401, cors);
  }

  const ship = (url.searchParams.get("ship") || "").trim();
  const line = (url.searchParams.get("line") || "").trim();
  const date = url.searchParams.get("date") || "";
  const nameOk = s => s.length <= 80 && /^[\p{L}\p{N} .'&-]*$/u.test(s);
  const d = /^\d{4}-\d{2}-\d{2}$/.test(date) ? new Date(date + "T00:00:00Z") : null;
  if (!ship || !nameOk(ship) || !nameOk(line) || !d || isNaN(d) || d.toISOString().slice(0, 10) !== date) {
    return reply({ code: "bad_request", error: "Send ship (the ship name), date (YYYY-MM-DD), and optionally line (the cruise line)." }, 400, cors);
  }

  if (!env.ITINERARIES) {
    return reply({ code: "not_configured", error: "The helper needs its ITINERARIES KV binding." }, 500, cors);
  }
  const key = "itin:" + line + ":" + ship + ":" + date;
  let saved = null;
  try { saved = await env.ITINERARIES.get(key, "json"); } catch (e) { saved = null; } // unreadable entry: look it up again
  if (saved && Array.isArray(saved.stops)) return reply(saved, 200, cors);

  const q = new URLSearchParams({
    ship_name: ship,
    departure_from: date,
    departure_to: date,
    include_delisted: "true",
    include_past: "true",
    limit: "1"
  });
  if (line) q.set("cruise_line", line);
  let res, body = null;
  try {
    res = await fetch("https://api.cruisefeed.io/v1/cruises?" + q, {
      headers: { "Authorization": "Bearer " + env.CRUISEFEED_KEY, "Accept": "application/json" }
    });
    body = await res.json().catch(() => null);
  } catch (e) {
    return reply({ code: "upstream", error: "CruiseFeed couldn't be reached." }, 502, cors);
  }
  // What is left of the allowance goes to the Worker's own logs only, never to the app.
  if (body && body.allowance) console.log("CruiseFeed results remaining:", body.allowance.remaining);

  if (res.status === 401 || res.status === 403) {
    return reply({ code: "upstream_auth", error: "CruiseFeed refused the helper's key. Check the CRUISEFEED_KEY secret." }, 502, cors);
  }
  if (res.status === 429 || (body && body.allowance && body.allowance.exhausted && !(body.items || []).length)) {
    return reply({ code: "allowance", error: "CruiseFeed's lookup allowance is used up." }, 503, cors);
  }
  if (!res.ok || !body || !Array.isArray(body.items)) {
    return reply({ code: "upstream", error: "CruiseFeed answered " + res.status + "." }, 502, cors);
  }
  const c = body.items[0];
  if (!c) return reply({ code: "not_found", error: "CruiseFeed has no sailing for that ship on that date." }, 404, cors);

  // Only public sailing data is saved and sent back: never the key, account details, or the request.
  const out = {
    cruise_line: c.cruise_line || line || null,
    ship: c.ship_name || ship,
    departure_date: c.departure_date || date,
    return_date: c.return_date || null,
    nights: c.nights ?? null,
    title: c.title || null,
    source: "CruiseFeed",
    saved_at: new Date().toISOString().slice(0, 10),
    stops: (Array.isArray(c.itinerary) ? c.itinerary : []).map(s => ({
      seq: s.seq ?? null,
      day_number: s.day_number ?? null,
      date: s.date || null,
      port: s.port || null,
      arrive: s.arrive || null,
      depart: s.depart || null,
      is_embark: !!s.is_embark,
      is_disembark: !!s.is_disembark,
      is_sea_day: !!s.is_sea_day,
      overnight: !!s.overnight
    }))
  };
  // No expiry: past sailings don't change. If saving fails, the phone still gets its itinerary.
  try { await env.ITINERARIES.put(key, JSON.stringify(out)); }
  catch (e) { console.log("Could not save to KV:", e.message); }
  return reply(out, 200, cors);
}
