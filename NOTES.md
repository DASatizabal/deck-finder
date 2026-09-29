# Deck Finder: handoff notes

Read this with `CLAUDE.md` at the start of every session. CLAUDE.md holds the rules; this file holds the current state, known issues, lessons learned, and parked work. Last updated 2026-09-29 (version 1.12.0).

## Current state

- **Live version:** 1.12.0, at https://dasatizabal.github.io/deck-finder/ (check `version.json` there). Confirmed live on 2026-09-29.
- **Priority ship:** Norwegian Getaway, which the family sails first (Oct 2, 2026). Joy and Aqua trips follow later. Trip details and cabin numbers live only in the saved trips on the phones, not in this public repo.
- **Worker status (2026-09-27):** deployed at https://deck-finder.dasatizabal.workers.dev with the KV version of `worker/worker.js`, the secrets `CRUISEFEED_KEY` and `APP_PASS`, and the KV namespace `deck-finder-itineraries` bound as `ITINERARIES`. The Getaway Oct 2 sailing is seeded in KV with full times, and the live route returned it. The phones still need to re-run the Oct 2 lookup (Trip set up, Edit, Save and look up itinerary).
- **Install status:** David was installing the app on his Android phone for the first time. The first attempt failed with "This app cannot be installed", which 1.6.1 fixed. A successful install on a real phone has not been confirmed yet.

### Repo layout

Both repos sit side by side in `D:\AI-VAULT\projects`:

| Folder | GitHub | What it is |
|---|---|---|
| `deck-finder` | DASatizabal/deck-finder (public) | The app. GitHub Pages publishes it through `.github/workflows/publish.yml` (Pages source is "GitHub Actions"). |
| `deck-finder-builder` | DASatizabal/deck-finder-builder (private) | The workshop. `deck-vision/` reads deck plan images and makes cabin, venue, amenity and landmark boxes. It has its own `CLAUDE.md`. |

Inside `deck-finder`:
- `index.html`: the whole app, about 200 KB.
- `sw.js`: offline support, cache per app version plus one cache per saved ship. Since 1.12.0 it also answers `calendar.ics?n=<file name>&d=<base64url of the calendar text>` itself (never the network), for Add to calendar on iPhone.
- `version.json`, `CHANGELOG.md`, `manifest.webmanifest`, `icon-192.png`, `icon-512.png`.
- `ships/index.json`: the catalog, with a hash per ship, and since 1.10.0 a `places` list of island maps (port code, port name, `port_match`, bounds, hash).
- `ships/ncl/line.json`.
- `ships/ncl/<ship>/`: `ship.json`, one `deck<N>.webp` per deck, and for Getaway only, `geometry.json`. Since 1.12.0 Getaway's venues and amenities carry a `category` (bar, food, pool, entertainment, kids, shop, spa_fitness, service, sports, other), copied from the builder's `deck-vision/out/getaway/geometry.json` of 2026-09-28 15:45. That was the only change from the 1.6.0 file.
- `places/great-stirrup-cay/`: the island map (1.10.0). `place.json` (name, port code `NPI`, port name, `port_match` "Great Stirrup", `bounds`, and the file names), `basemap.json` (OpenStreetMap shapes as GeoJSON, with the attribution in the file), `places.json` (venues shown on the map), `survey-list.json` (the venue checklist for Survey mode, 108 venues since 1.11.1, plus the `merged` and `removed` id lookup), and since 1.11.1 `areas.json` (the five areas on NCL's island sign, named by `"areas"` in `place.json`).
- `worker/worker.js`: the Cloudflare Worker (backup helper). Not published; pasted into the Cloudflare dashboard by hand.
- `tools/kv_put.py` and `tools/itineraries/`: write one itinerary into the Worker's KV namespace by hand.
- `tools/`: `build_index.py`, `calibrate_decks.py`, `split_images.py` (one-time, already used), and since 1.10.0 `build_island.py` (downloads the island from the Overpass API and writes `basemap.json`) and `import_island_data.py` (copies `places.json` and `survey-list.json` from the builder; since 1.10.1 it also copies `official_area`, `official_number` and `not_on_official_map`; since 1.11.1 it also copies `areas.json`, see Island data below). Not published.
- `.github/scripts/check_release.py`: the release gate.

Inside `deck-finder-builder/deck-vision`:
- `extract_ship.py`: the pipeline.
- `deckvision/`: the modules.
- `rules.json`: aliases, amenity and landmark labels, suite codes, misprints.
- `make_app_json.py`: makes an app `geometry.json` from a reviewed file.
- `review/review.html`: the review page.
- `reviewed/ncl/getaway/ship.json`: committed human review.
- `out/`: pipeline output and the website cache, not committed.
- `.venv`: Python 3.12, not committed.

### What each release added

| Version | What it added |
|---|---|
| 1.4.0 | Norwegian Joy and Norwegian Aqua deck plans. Version number and What's new in the menu. Update banner and self-update. `check_release.py` and the publish Action. |
| 1.4.1 | GitHub Actions updated to current major versions. No app change. |
| 1.5.0 | Deck plans moved out of `index.html` into `ships/<line>/<ship>/` folders. Each ship is saved for offline in its own cache, re-downloaded only when its hash changes. The ships on your trips are saved automatically. Saved ship ids migrated from `getaway` to `ncl/getaway`. |
| 1.6.0 | Automatic cabin pin on Getaway from `geometry.json`. A hand-placed pin wins until "Use automatic position". Venue highlighting. Search finds any cabin number (including `printed_as` misprints) and amenities. Custom pins per trip (`trip.pins`) with a My pins list. |
| 1.6.1 | `index.html` now links `manifest.webmanifest`. It was missing since the first upload, so Android refused to install the app. iPhone home screen icon and title added. |
| 1.7.0 | Wide plan layout by default, with "On this deck" in a sheet. Full screen button. Menu switch back to the old Side by side layout (`state.layout`). Fixed the zoom button hiding behind the pin button. |
| 1.8.0 | Keeping your place when changing decks, using each deck's `ship_extent` (from `tools/calibrate_decks.py`) and, on Getaway, elevator banks as anchors. A faint line marks the spot. |
| 1.10.0 | Great Stirrup Cay island map, drawn by the app from `basemap.json` (no map tiles), with pinch zoom, search, and place markers by category. Blue dot from GPS with an accuracy circle. Save my spot and Take me back (compass arrow, or a line on the map without a compass; screen kept awake). Survey mode (tag venues with a 5-second averaged position, rename, doesn't exist, new places, record a walk, export). All-aboard countdown on island day. Islands saved for offline like ships. The itinerary sheet shows the Worker's source label. |
| 1.10.1 | Great Stirrup Cay data refreshed from the builder with the official island map names and positions: 52 places (was 7), 112 survey venues (was 100). Place cards and Survey show the sign's legend ("On the island map sign: Beaches 7"). Survey rows and venue sheets say "Not on the official map" for the 61 venues the sign doesn't show. |
| 1.11.0 | Welcome screen when there are no trips. The Worker address is built in (`DEFAULT_WORKER`); the helper address and passphrase moved into a collapsed Advanced section of Trip set up. Family invite links (`#join=`) and an Invite family menu item. Wide plan default view shows a fixed share of the ship's length (`VIEW_SHARE` 0.389). Selecting a venue, cabin, amenity, search result, pin or the cabin chip centers it at the current zoom, zooming out only for a box bigger than the view. Green square and green pin on your cabin. Ready for sea checklist with Fix buttons, and a banner from 3 days before sailing. Share trip links (`#trip=`). |
| 1.11.1 | Great Stirrup Cay areas (neighborhoods): tints in the sign colors, faded area names, an area-colored outline on each marker, "You're in" and "Near" line, area buttons that zoom and dim, area cards with notes and place lists. Search and Survey grouped by area in sign order. Markers a few meters apart fan out. Importer keeps placed, approximate and surveyed places, uses `display_name`, carries `area_id` and `area`, and writes the merged and removed lookup. Release check for `areas.json`. Add from a link (menu and welcome screen). |
| 1.12.0 | Category buttons above the deck plan (Bars, Food, Restrooms, Stairs, Elevators, Pools, and More: Entertainment, Kids, Shops, Spa and fitness, Services, Sports). One lights up at a time: glowing boxes in its color, a count at the bottom of the plan, and dots on the deck slider for every deck that has one. Greyed out with "Coming soon for this ship" on ships without geometry. Island map markers of the same area that overlap on screen merge into numbered bubbles below the on-island opening zoom (1.2). Trip events with reminders: an Events list in the trip editor, "Next:" on the trip strip, events under their day in the itinerary sheet, a reminder banner with Show me, Add to calendar (.ics with the alarm built in), Share the calendar file, and events in shared trip links. |
| 1.9.0 | Itinerary lookup order: the trip's saved itinerary, NCL live, then CruiseFeed through the Worker's `/itinerary` route, then typing it in. Itinerary sheet shows where it came from. Manual day editor in the trip editor. Family passphrase in Trip set up. Worker code moved into `worker/`. |

### Saved data on the phone

Two localStorage keys:
- **`deckfinder`** (the view): `ship`, `deck`, `zoom`, and since 1.7.0, `layout`. Since 1.11.0, `zoomAuto` (true means the default view, recomputed per deck; phones that had `zoom` 1 were set to true, others kept their zoom) and `readyHidden` (`<trip id>:<YYYY-MM-DD>`, the Ready for sea banner hidden for that day). Since 1.12.0, `remindDone`: the reminders dismissed or opened with Show me, as `<trip id>:<event id>:<date>T<time>:<remind>` (editing an event's time or reminder makes a new key, so it reminds again). Keys of deleted events are dropped the next time a reminder is dismissed. The lit-up category is in memory only.
- **`deckfinder-trips`**: `trips`, `activeTripId`, `workerUrl`, and since 1.9.0, `passphrase`. Each trip has `id`, `ship`, `date`, `cabin`, `pin`, `itinerary`, and since 1.6.0, `pins`.
- **`trip.itinerary`**: `title`, `fetched`, `days`, optional `code` (NCL only), and since 1.9.0, `source` (`ncl`, `cruisefeed` or `manual`; missing means `ncl`) and `edited` (true after a hand edit of a looked-up itinerary). Since 1.10.0, `sourceLabel` (the Worker's `source`, like `NCL website, captured 2026-09-23`) on itineraries from the backup helper. Each day is `{date, kind: "embark"|"port"|"debark", port, arrive, depart}` or `{date, sea: true}`, times as `HH:MM` local port time, and since 1.10.0 an optional `code` (NCL's port code, like `NPI`) on days from the NCL live lookup. `normalizeDays` sorts the days and makes the first `embark` and the last `debark`, and keeps `code`.
- **Since 1.10.0 on each trip:** `spots` (Save my spot: `{id, place, name, lat, lon, acc, saved}`) and `allAboard` (minutes before departure, 30 when missing).
- **Since 1.12.0 on each trip:** `events`, each `{id, title (60 characters at most), date YYYY-MM-DD, time HH:MM, remind (minutes before, 0 to 10080, or null for no reminder), place (optional)}`. A place is `{kind: "venue", ship, deck, name}` (a name from the deck lists or the geometry), `{kind: "cabin", ship, cabin}`, `{kind: "island", island, id, name}` (an id in the island's `places.json`), or `{kind: "text", text}`. Times are the phone's clock, like all aboard.
- **Since 1.10.0 in `deckfinder`:** `island` (the island map that was open, reopened on start).
- **`deckfinder-survey`** (new key in 1.10.0, separate from trips so saved spots never reach an export): `{places: {<place id>: {venues: {<venue id>: {lat, lon, acc, samples, at, rename, missing}}, added: [{id, name, category, lat, lon, acc, samples, at}], walks: [{id, started, ended, points: [[lat, lon, acc, time ms]]}]}}}`. Clearing the site's data in the browser deletes it, so export often.

Fields have only been added, never renamed or reshaped.

## Known issues and limitations

- **Links after the # (1.11.0).** The part after `#` never reaches any server.
  - `#join=<passphrase>` (URI-encoded) saves the family passphrase, shows "You're connected to your family's lookups", and `history.replaceState` removes it from the address bar and the page's Back history. Whether Chrome's or Safari's History list still records the original visit was not tested. Pasting an invite link into the Family passphrase field also works.
  - `#trip=<base64url of JSON>`: `{v: 1, ship, date, cabin, pin (hand-placed cabin pin), allAboard, itinerary {title, source, fetched, code, sourceLabel, edited, days}, pins [{id, ship, deck, x, y, label, color}]}`. Built only from these named fields, so the passphrase, `spots` (Save my spot) and survey data never go in. `parseSharedTrip` checks every field (ship in the catalog, ISO dates, `HH:MM` times, pin colors `#RRGGBB`, lengths capped). A Getaway trip with a 4-day itinerary and 2 pins made a 920-character link.
  - Same ship and date already on the phone: Merge the pins and events (skips pins with the same id or the same deck, position and label, and events with the same id or the same title, date and time) or Replace the trip (keeps the phone's trip id and its saved spots).
  - Since 1.12.0 the link also carries `events` (same fields as on the trip; the payload is still `v: 1`, and older versions ignore the field). `parseSharedTrip` keeps at most 100, drops any with a bad date, time or empty title, drops a reminder outside 0 to 10080, and drops a place whose ship or island isn't in the catalog. A Getaway trip with a 4-day itinerary and 6 events made a 1,943-character link.
- **iPhone home screen apps have their own storage,** separate from Safari. An invite or trip link tapped in Messages opens Safari, so it lands in Safari's copy, not the home screen app. Since 1.11.1, Add from a link (in the menu and on the welcome screen) takes a pasted invite or trip link, even inside other text, and does what tapping it would do.
- **Default view (1.11.0).** In the wide layout the plan shows `VIEW_SHARE` = 0.389 of the ship's length, from Getaway deck 5: forward-most stairs at 37.65% of the image, plus 1%, over ship_extent 0 to 99.44%. On a phone this is narrower than the screen (zoom about 0.65), so the plan sits centered with space on both sides. While `zoomAuto` is on, the zoom is recomputed for each deck (the same share of each deck's ship length); a pinch, the zoom button or a zoom-out for a big target turns it off, and that zoom then stays across decks as before. Ending a pinch within 5% of the default view turns it back on. The side by side layout's default is still the plan filling the column.
- **The green cabin square needs geometry.** Getaway only; Joy and Aqua show just the green pin where it was tapped. A hand-placed pin outside the geometry box hides the square (the pin wins).
- **The Worker is now always the fallback** for the NCL lookup (`/?path=`) and the itinerary route, using the built-in address unless one is typed in Advanced.
- **Ready for sea checks:** trip's ship saved for offline (current hash), each island on the itinerary saved, every non-sea day except the last has a departure time, location permission (`navigator.permissions`), the latest version (`version.json`, which the service worker answers from its cache when offline, so offline it reports the last version seen), and installed (`display-mode: standalone`, or `navigator.standalone` on iPhone). The install Fix uses Chrome's install prompt when Chrome offered one, otherwise shows the steps.

- **Top-deck alignment (1.8.0).** Every deck image is cropped to its own drawing, so `ship_extent` is about 0 to 100% on every deck. The top decks are shorter structures than the hull but still fill their images, so mapping by fraction of ship length is wrong there:
  - Getaway decks 17 and 18, which also have no elevators to anchor on.
  - Joy decks 18 to 20.
  - Aqua decks 18 to 20. Aqua deck 18 covers only the middle of the ship.

  A fix needs each deck's real position along the ship: measure it from matching features, or set it by hand per deck.
- **Joy and Aqua alignment uses `ship_extent` only.** They have no geometry, so there are no elevator anchors. On Getaway, extent alone was within about 1% of ship length on most deck pairs, but 4.5% off from deck 9 to 10.
- **Getaway has only two elevator banks on the plans,** midship at about 40% and aft at about 79%. There is no forward bank, so the forward part of the ship aligns by shifting with the midship anchor.
- **Full screen is not yet tested on a real Android phone.** It uses the browser's Fullscreen API where available. iPhones don't support it for web apps, so there it only hides the app's own header and footer.
- **The first Android install is not yet confirmed** after the 1.6.1 fix. If Chrome still says "This app cannot be installed", clear the site's data in Chrome settings and reload twice.
- **Joy and Aqua have no geometry yet.** No automatic cabin pin, no venue highlighting, and no amenity search on those ships; they use tap-to-place. Their Deck Vision output in the builder is unreviewed.
- **Getaway's ship.json lists "Pool" and "Sun Deck" as venues** in its deck lists. The geometry stores them as amenities. The app falls back to amenity boxes for those names, so tapping them still highlights.
- **`make_app_json.py` drops unconfirmed venues.** A venue flagged `not_in_ground_truth` and not marked reviewed is left out of `geometry.json`. The Getaway review cleared all flags, so nothing was dropped.
- **The cruisedeckplans.com cabin list is partial.** It lists only cabins with photos, about a fifth of a deck. It confirms readings, but it can't prove a cabin is missing.
- **`tools/calibrate_decks.py` needs Pillow and numpy,** which aren't installed by anything in this repo. The builder's `deck-vision\.venv` has both.
- **CruiseFeed has no port times for the Getaway Oct 2 sailing.** The one probe (2026-09-27) confirmed the stops and dates (Miami Oct 2, Nassau Oct 3, Great Stirrup Cay Oct 4, Miami Oct 5, title "Bahamas: Great Stirrup Cay & Nassau") but every `arrive` and `depart` was null. The app shows "Some times aren't listed" and the family adds times with Edit itinerary. The expected times (Miami sails 4:00 PM, Nassau and Great Stirrup Cay 7:00 AM to 5:00 PM, Miami arrives 7:00 AM) come from David, not from CruiseFeed.
- **CruiseFeed allowance:** the free tier is 300 results for the life of the key (not 1,000), and never resets. 298 left on 2026-09-27: 1 for the probe, 1 for the local Worker test. To check it for free, run a `/v1/cruises` query that matches nothing (for example `ship_name=Norwegian Getaway`, `departure_from` and `departure_to` both `1990-01-01`, `limit=1`) and read `x-results-remaining` or the `allowance` object; a zero-row query costs nothing (confirmed: `used` stayed at 2). `/v1/stats` doesn't report the allowance, and `/v1/account` needs a dashboard login, not the API key.
- **KV holds the shared itinerary cache.** The Worker's `/itinerary` route checks the KV namespace `deck-finder-itineraries` (bound as `ITINERARIES`) before CruiseFeed, so each sailing costs at most one CruiseFeed result, shared by every phone.
  - Key: `itin:<cruise line>:<ship>:<YYYY-MM-DD>`, built from the request's `line`, `ship` and `date` exactly as sent. The app sends the `line.json` and `ship.json` names, for example `itin:Norwegian Cruise Line:Norwegian Getaway:2026-10-02`.
  - Value: public sailing data only, as JSON: `cruise_line`, `ship`, `departure_date`, `return_date`, `nights`, `title`, `source` (a label such as `CruiseFeed` or `NCL website, captured 2026-09-23`), `saved_at` (YYYY-MM-DD), and `stops` (each with `seq`, `day_number`, `date`, `port`, `arrive`, `depart` as `HH:MM` local time or null, `is_embark`, `is_disembark`, `is_sea_day`, `overnight`). Nothing from the request is ever stored. No expiry.
  - On a miss the Worker calls CruiseFeed and saves the cleaned result. Without the `ITINERARIES` binding the route answers `not_configured` and spends nothing.
  - Since 1.10.0 the app shows the Worker's `source` label (for example "NCL website, captured 2026-09-23, looked up on ..."). Itineraries saved on the phones before 1.10.0 have no label and still say "Found through CruiseFeed" until the lookup is run again (Trip set up, Edit, Look up the itinerary again).
- **Seeding an itinerary with `tools/kv_put.py`.** Write a JSON file in the value format above into `tools/itineraries/` (copy `ncl-getaway-2026-10-02.json`), then:
  1. `python tools/kv_put.py tools/itineraries/<file>.json --dry-run` checks the file and shows the key. It contacts nothing.
  2. `python tools/kv_put.py tools/itineraries/<file>.json` writes it (replacing any entry for that sailing), sets `saved_at` to today, and reads it back.
  3. `python tools/kv_put.py <file> --delete` removes that sailing's entry.

  It reads `D:\AI-VAULT\secrets\cloudflare_kv_token.txt` (an API token with only Account, Workers KV Storage, Edit) and `D:\AI-VAULT\secrets\cloudflare_account_id.txt`, and never prints them. It refuses fields outside the value format.
- **Testing the live Worker for free:** seed a dummy entry for a 1990 date with `kv_put.py`, call `/itinerary` for that date with the passphrase (from `D:\AI-VAULT\secrets\deckfinder_app_pass.txt`), and expect the dummy back. If an old Worker were deployed, it would ask CruiseFeed for 1990, get zero rows, and still spend nothing. Delete the dummy afterwards with `--delete`.
- **CruiseFeed facts:** send `Authorization: Bearer <key>`. Exact names are cruise line `Norwegian Cruise Line` and ships `Norwegian Getaway`, `Norwegian Joy`, `Norwegian Aqua`; the app sends each ship's `ship.json` name and its `line.json` name. `include_past` is ignored when a departure date filter is set, so the exact-date query finds past sailings anyway. `/v1/stats`, `/v1/ship-names` and `/v1/cruise-lines` cost nothing. `/v1/cruises` answers carry `x-results-remaining`.
- **NCL lists the Getaway Oct 2 sailing again (2026-09-28).** In the 1.10.0 tests the NCL live lookup found it (3-Day Bahamas Round-Trip Miami) before the backup helper was needed. The helper label was tested by calling the helper route directly (a KV hit, no CruiseFeed result spent).
- **The NCL search API works directly from the browser** (it failed through Cloudflare because NCL blocks data center addresses). In the 1.9.0 tests, both NCL steps succeeded directly from Chrome, and the Worker's NCL proxy was not needed.
- **The Worker's `/itinerary` route asks for `ship`, `date` and an optional `line`.** The request in the 1.9.0 brief read `ship=<cruise_line ship_name>`; it was built as two parameters.
- **Island data (1.11.1).** From the builder export of 2026-09-28 13:27: 52 places on the map (all placed; 0 approximate, 0 surveyed yet), 108 survey venues, 5 areas.
  - `places.json` and `survey-list.json` entries carry `display_name`, never the builder's `name` (which can hold notes like "(marker 3-b)"). The app copies `display_name` into `name` when it loads the island, so every list, label, card and export uses it. Older cached files without `display_name` still work.
  - Surveyed places (status `surveyed`, from the builder's `merge_survey.py`) show as exact, with "Measured on the island, within <distance>, on <date>" from `accuracy_m` and `survey_date`.
  - `survey-list.json` has `merged` (`silver-cove-pool` -> `silver-cove-gazebo`) and `removed` (`tram-stop-cabana-beach`, `jumbey-beach`, `silver-cove`). When the island opens, a survey entry under a merged id moves to the venue it was merged into, unless that venue has its own entry. Entries under removed ids stay in the phone's data (and in exports) but are never shown or counted.
  - `areas.json`: `areas` in sign order (Welcome Plaza, Lagoon, Beaches, Silver Cove, Waterpark), each with `id`, `name`, `color`, optional `note`, and `outline` ([lat, lon] corners). The outlines are the builder's first draft (the Waterpark is a small circle around its one placed venue). The release check wants exactly five areas and every place's and survey venue's `area_id` among them, and rejects any name containing "(marker".
  - Area names on the map sit at the point inside each outline farthest from its edges, sized with the zoom (10 to 22 px) and hidden when the whole island is very small. "Near: <area>" shows only within 400 m of an outline.
  - Fanning: markers (places and saved spots) closer than 6 m that overlap on screen (under 30 px) spread around their shared spot, labels on the outer side. Markers farther apart can still overlap when zoomed far out: at the whole-island view, First Aid sits under Beaches Bar (45 m away). The Vibe Shore Club Cabanas marker (13 m from the Vibe trio) can cover part of the Vibe Restaurant label.
- **Island map data (1.10.1).** OpenStreetMap has almost none of the 2025 and 2026 construction (the new pier, Great Tides Waterpark, Vibe Shore Club), so the basemap shows the older island. The builder export of 2026-09-28 12:35 places 52 of 109 venues (0 approximate, 57 to do), most from the georeferenced official island map. None were west of -77.9300. Survey mode is how the rest gets placed.
  - **Legend fields:** `places.json` and `survey-list.json` entries carry `official_area` and `official_number` (both, or neither) from `venues-to-place.json`. 44 of the 52 places have them. The app shows them as "On the island map sign: <area> <number>". The survey list also carries `not_on_official_map: true` (61 venues).
  - **Tram stop names:** only `tram-stop-welcome-plaza` has `confirmed_by` exactly "official island map" (General 2, "Tram Stop & Restrooms"), so it is the only stop without "(name unconfirmed)". Great Life Lagoon and Silver Cove stops are "official island map (icon, not named)" and keep the suffix. The other three stops are not on the sign.
  - **Gone from the map in 1.10.1:** Jumbey Beach, Silver Cove (the area label) and Silver Cove Pool. The builder deleted the first two in the place editor (`deleted_ids`) and set Silver Cove Pool back to to do; Silver Cove Gazebo & Pool (Silver Cove 10) sits at nearly the same spot. All three stay in the survey list, so survey entries for them still work.
  - **Data quirks to fix in the builder:** three names carry the builder's marker suffix ("Beaches Bar (marker 3-b)", "Silver Cove Lagoon Villas (marker 8)", "Silver Cove Bar (marker 3-b)" and similar); the app copies names as they are. "Tram Stop: Great Life Lagoon" and "Tram Stop: Main Beach and Jumbey Beach Grill" have the identical position, and First Aid and Ocean Adventure Rentals are 0.5 m apart, so their labels overlap. The waterpark entrance is Waterpark 1, which the old sign calls Coming Soon.
  - **Survey data on the phones is keyed by venue id,** never by name, so renamed venues keep their recorded positions, renames and doesn't-exist marks. No venue id was removed in 1.10.1 (all 100 old ids are among the 112). Never change a venue id in the builder without a migration.
- **Island map features not yet tried on a real phone:** the compass arrow (iPhone motion permission, Android absolute orientation), the Screen Wake Lock, sharing the export file, and GPS accuracy under trees. The tests used headless Chrome with a simulated GPS and a simulated compass event.
- **The island is saved for offline only when a trip has an island day** (port code `NPI`, or a port name containing "Great Stirrup"), or when someone taps Download for offline in the menu.
- **All-aboard uses the phone's clock** and the itinerary's departure time, both assumed to be local time. Great Stirrup Cay and Miami share Eastern time, so this holds for the Bahamas sailings.
- **Category buttons (1.12.0).**
  - Bars, Food, Pools and the More kinds come from the `category` on venues and amenities. Restrooms, Stairs and Elevators come from the geometry's landmarks (`kind`).
  - The count is distinct venue names on the deck plus amenity and landmark boxes. A venue drawn as two boxes (La Cucina, Cagney's) counts once. The geometry names outdoor seating as separate venues ("Syd Normans Pour House Waterfront"), so Deck 8 says 8 bars.
  - Elevators count geometry boxes: 4 per deck on most decks, though the plans have two banks.
  - 15 venues and 7 amenities have the category `other` (Sun Deck, Atrium, Card Room, 678 Ocean Place and similar) and have no button.
  - The buttons sit in a row above the plan, and the count is a pill over the bottom of the plan, so turning a category on or off never changes the plan's height or zoom. `renderCats()` updates the boxes, count and slider dots without rebuilding the plan.
  - Tapping a glowing box shows its name in the message bar.
  - Ships whose `ship.json` names a geometry file that hasn't downloaded yet (offline, not saved) say so instead of "Coming soon".
- **Island bubbles (1.12.0).**
  - Below `ISLAND_OPEN_S` (1.2 pixels per meter, the zoom the map opens at when you're on the island), place markers of the same area whose centers are closer than 36 px on screen merge. The grouping chains (A near B and B near C is one bubble). At the whole-island view on a phone, that is one bubble per area: Beaches 21, Silver Cove 12, Lagoon 12, Welcome Plaza 4, Waterpark 2.
  - Saved spots, survey marks and the selected place never merge. Area names are drawn on top. Bubbles are placed biggest first, each on its own spot or the nearest free spot (trying straight down first), so none covers a name or another bubble. An earlier push-apart version oscillated near names that sit close together.
  - Tapping a bubble zooms, centered on its places, to where they all separate (capped at 1.2). When they wouldn't fit on screen at that zoom, it zooms only as far as keeps them on screen, at least far enough to split the bubble. The Beaches 21 bubble separates in 2 taps.
- **Trip events and reminders (1.12.0).**
  - The banner shows only while the app is open: from the reminder time until 15 minutes after the event starts, checked every 20 seconds plus a timer set for the next reminder. It shows the soonest due reminder. Show me opens the deck plan with the venue highlighted, the cabin's deck with its box, or the island map with the place selected, and it counts as dismissing.
  - Deck plan events store the venue name, and Show me finds its box with the same name matching as the "On this deck" list. On Joy and Aqua it just opens the deck.
  - **Add to calendar has not been tried on a real phone.** The file passed a strict parser (Python `icalendar` 7.3.0): CRLF, lines folded at 75 bytes, escaped commas and semicolons, UTC times from the phone's clock, a 30-minute length, a `VALARM` with `ACTION:DISPLAY` and `TRIGGER:-PT<n>M` (or `PT0M`), `METHOD:PUBLISH`, and a UID of `<event id>-<trip id>@dasatizabal.github.io`.
  - How the file reaches each phone: iPhone (with the service worker running) goes to `calendar.ics?...`, which `sw.js` answers with `Content-Type: text/calendar` and `Content-Disposition: inline`. WebKit never shows `text/calendar` as a page, so the app can't get stuck on a blank screen; Safari should show its Add to Calendar screen. Everything else downloads a blob with the `download` attribute, and the user opens it from Chrome's download message. Whether Google Calendar on Android opens `.ics` files depends on the phone; Samsung Calendar does.
  - Share the calendar file (shown when `navigator.canShare` accepts files) is the fallback: send it to yourself and open it from Mail or Gmail.
  - Calendar times are fixed in UTC, taken from the phone's time zone when the file is made. A file made while the phone is in another time zone would be off by the difference. Miami, Nassau and Great Stirrup Cay are all Eastern.
- **Not started:** the Android Capacitor build mentioned in CLAUDE.md.

## Lessons learned

- **A review file overwrote `ships/ncl/getaway/ship.json`.** The review page's "Download corrected ship.json" was saved into the public repo instead of the builder. It is a different format, and the app can't read it. It was caught before commit and restored with `git restore`. `check_release.py` now fails any `ship.json` that looks like a Deck Vision review file, with a message saying how to restore it. Reviewed files belong in `deck-finder-builder/deck-vision/reviewed/<line>/<ship>/ship.json`.
- **`git restore` wipes uncommitted work.** During the 1.6.0 review-file test, restoring `ship.json` also removed the new, uncommitted `"geometry"` line, and it had to be re-added. Commit first, or test on a copy.
- **The built-in test browser pauses animation.** When its pane is hidden, `requestAnimationFrame` doesn't fire and smooth scrolling doesn't move, so `scrollTo({behavior: "smooth"})` looks broken in tests.
  - The app's scroll code falls back to a 120 ms timer.
  - To test where a jump lands, override `Element.prototype.scrollTo` to force `behavior: "instant"`.
  - Screenshots can also time out while the pane is hidden, so prefer DOM measurements.
- **Clear the service worker before testing a new build locally.** Unregister it and delete the caches, or the old app keeps serving from its cache. The service worker registers on `localhost` on purpose, so offline tests work. Simulate offline by stopping the local server.
- **PowerShell 5.1 corrupts UTF-8.** `Get-Content` / `Set-Content` read and write with the ANSI code page, which garbled the ★ ▲ ■ symbols in a Python file, and `-Encoding utf8` adds a byte-order mark. Edit files with Python or the editor tools instead.
- **Heredocs with apostrophes can break** in the Bash tool. Write longer scripts to a file and run the file.
- **Watching a log for a finish line can match a stale log** from an earlier run. Delete old logs before starting a watched run.
- **The review page saves to Downloads.** After a review, copy the file from `%USERPROFILE%\Downloads\ship.json` into `deck-vision/reviewed/<line>/<ship>/`. The Getaway review (2026-09-25) was found in Downloads, not in `out/getaway/` where it was expected.
- **cruisedeckplans.com's robots.txt asks for 10 seconds between requests.** The builder's scraper waits 10 seconds and caches everything in `out/_cache`.
- **`.gitattributes` forces LF line endings.** Without it, Windows checkouts change the bytes of JSON files, and the ship hashes in `ships/index.json` stop matching in the GitHub Action.
- **Floating buttons with negative margins stack on top of each other.** The plan's buttons now sit in one `.maptools` row.
- **An app manifest does nothing unless `index.html` links it.** Check `<link rel="manifest">` if installing ever breaks again.
- **Test the Worker locally with a Node harness, never against the real CruiseFeed more than once.** The 1.9.0 session ran `worker/worker.js` under Node 22 (plain `import` of the file works; pass a fake `ITINERARIES` object with `get(key, "json")` and `put(key, value)` methods) on port 8787, with the key read from the secrets file into memory and a guard that blocked every CruiseFeed call after the first. It also fed a saved CruiseFeed reply through the Worker with `fetch` mocked, which tests the whole conversion for free.
- **Python's `Path.write_text` writes CRLF on Windows.** It turned `index.html` into CRLF line endings. Use `write_bytes` or `open(f, "w", newline="\n")`.
- **Headless Chrome through Playwright works for app tests** (`python -m playwright`, `channel="chrome"`, `service_workers="block"`), and avoids picking between the two Chrome browsers connected to the Claude in Chrome extension. Seed trips by setting the page's `data` and calling `save()`, because the app overwrites localStorage written from outside. The day editor must be reached with its sheet open.
- **Check what is listening on a port before stopping it.** The 1.9.0 session stopped a `pythonw` process on port 8000 that it had not started, probably an older local preview server.
- **Playwright's `page.clock.install(time=...)` takes seconds, not milliseconds,** when given a number from Python. Milliseconds put the page in the year 58728. Passing `datetime(...).timestamp()` works.
- **Simulating GPS:** an init script that defines `Navigator.prototype.geolocation` with a fake `watchPosition` (emitting every second, plus on demand) lets tests move the blue dot, set a poor accuracy, and deny permission. A compass reading can be simulated with `window.dispatchEvent(new DeviceOrientationEvent("deviceorientationabsolute", {alpha, absolute: true}))`.
- **Page-wide CSS selectors catch new elements.** `.imap svg` (meant for the map) also caught the Take me back arrow and made it overlap the text. Scope such rules by id (`#isvg`).
- **`grep -c $'\r'` in Git Bash is not a reliable line-ending check.** It reported CR on files that had none. Count `\r` bytes with Python instead.
- **Playwright's persistent profile breaks Cache Storage here.** In `launch_persistent_context` with a profile folder in the scratchpad, every `cache.put` failed with "Entry already exists", even a fresh cache with a one-line Response. A normal `browser.new_context(service_workers="allow")` works, and localStorage survives reloads within it, which is enough to test an update from the old build to the new one on the same origin (serve a `git archive HEAD` copy first, then copy the new files over it and reload).
- **Check a port before starting a test server on it.** In the 1.11.0 session, port 8791 was taken by the builder's `serve.py --port 8791`, so the test's `http.server` failed to bind silently and the test loaded the builder's directory listing. The 1.11.0 tests used port 8797.
- **A message bar at the top of the screen covers the menu button.** The 1.11.0 toast was moved to the bottom, above the footer.
- **1.11.0 tests:** `test_111.py` in that session's scratchpad (85 checks). It mocks `navigator.share` to capture the shared link, forces `scrollTo` to instant, fakes `display-mode: standalone` and a denied location permission with init scripts, answers `version.json` with a newer version through `page.route`, and pinches with a `WheelEvent` that has `ctrlKey`.
- **1.11.1 tests:** `test_1111.py` in that session's scratchpad (70 checks). Simulated GPS through a fake `Navigator.prototype.geolocation` with `window.__gps` and `window.__emit()`, a synthetic surveyed place added to `places.json` with `page.route`, and the offline check with the service worker allowed and the local server stopped. When a test needs the welcome screen gone, set `welcomeSeen = true` and call `render()`; setting `hidden` directly is undone by the next render.
- **1.12.0 tests:** `test_112.py` in that session's scratchpad (199 checks) plus `test_ios.py` (5 checks).
  - Expected category counts and slider dots came straight from `geometry.json` in Python, not from the app.
  - Reminders were tested with `page.clock.install` at 7:00 AM Eastern on island day (a `timezone.utc` datetime, with `timezone_id="America/New_York"`), then `page.clock.fast_forward`.
  - The calendar files were parsed with `icalendar` in a scratchpad venv.
  - The iPhone path was tested with an iPhone user agent and the service worker allowed. Chrome treats the `calendar.ics` answer as a download, which proves the service worker route and that the page stays put, but not Safari's calendar screen.
  - Offline was tested with `context.set_offline(True)` after the ship and island were saved.
- **Seeding a trip after startup doesn't save its ship for offline.** Call `syncOfflineShips()` in the test after `save()`, or the wait for `SAVED[...]` times out.
- **Pick on-screen elements in island tests.** At some zooms a bubble sits outside the viewport and `page.click` times out. Filter by the element's rectangle first.
- **Local preview:** a session needs its own `.claude/launch.json` running `python -m http.server <port> -d D:/AI-VAULT/projects/deck-finder`. The one from the 2026-09-23 session lived in a scratch folder.

## Parked work

- **Weekly NCL archive job on the AI PC (idea, not built).** NCL drops a sailing from its website once it stops selling it, and CruiseFeed has no port times for at least some of those (Getaway Oct 2). A scheduled job on the AI PC could, once a week:
  1. For Norwegian Getaway, Joy and Aqua, run the same NCL lookup the app does (the search API by month, then each `/cruises/<code>` page) for the coming months.
  2. Turn each sailing into the KV value format above, with `source` set to "NCL website, captured <date>".
  3. Write each sailing that isn't in KV yet with the `kv_put.py` logic, so its times survive after NCL delists it.

  Open questions: how many months ahead, how to stay polite to ncl.com (wait between requests, like the builder's scraper), and whether it should also replace an entry that came from CruiseFeed without times.

- **Survey export merge script (to write in deck-finder-builder).** Survey mode exports `great-stirrup-cay.survey-<date>.json` (`format: "deckfinder-survey"`, `format_version: 1`) with `venues` (id, list_name, category, confidence, and when present lat, lon, accuracy_m, samples, recorded, renamed_to, doesnt_exist), `new_places`, and `walks` (points with lat, lon, accuracy_m, time). Nothing merges it yet. The script should:
  1. Read the export and `islands/great-stirrup-cay/great-stirrup-cay.places.json`.
  2. For each venue with a position, set its lat and lon and mark it placed (or approximate when `accuracy_m` is over 20).
  3. Apply `renamed_to` as the new name, and mark `doesnt_exist` venues as skipped.
  4. Add `new_places` as new venues.
  5. Keep `walks` as path hints for review (OpenStreetMap has almost no paths for the new areas).
  6. Then, in this repo, run `python tools/import_island_data.py` and `python tools/build_index.py`, and release as a PATCH version.
- **Joy and Aqua reviews in deck-finder-builder.** The pipeline has run on both ships with the current rules. For each ship:
  1. Review `deck-vision/out/<ship>/ship.json` on the review page.
  2. Save the result to `deck-vision/reviewed/ncl/<ship>/ship.json` and commit it in the builder.
  3. Run `make_app_json.py` on the reviewed file to make `geometry.json`.
  4. Add it to the public repo as a normal versioned release, following CLAUDE.md.

  Aqua 13768 is recorded as misprinted `13168` in `rules.json`.
