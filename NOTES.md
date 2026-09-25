# Deck Finder: handoff notes

Read this with `CLAUDE.md` at the start of every session. CLAUDE.md holds the rules; this file holds the current state, known issues, lessons learned, and parked work. Last updated 2026-09-25 (version 1.8.0).

## Current state

- **Live version:** 1.8.0, at https://dasatizabal.github.io/deck-finder/ (check `version.json` there).
- **Priority ship:** Norwegian Getaway, which the family sails first (Oct 2, 2026). Joy and Aqua trips follow later. Trip details and cabin numbers live only in the saved trips on the phones, not in this public repo.
- **Install status:** David was installing the app on his Android phone for the first time. The first attempt failed with "This app cannot be installed", which 1.6.1 fixed. A successful install on a real phone has not been confirmed yet.

### Repo layout

Both repos sit side by side in `D:\AI-VAULT\projects`:

| Folder | GitHub | What it is |
|---|---|---|
| `deck-finder` | DASatizabal/deck-finder (public) | The app. GitHub Pages publishes it through `.github/workflows/publish.yml` (Pages source is "GitHub Actions"). |
| `deck-finder-builder` | DASatizabal/deck-finder-builder (private) | The workshop. `deck-vision/` reads deck plan images and makes cabin, venue, amenity and landmark boxes. It has its own `CLAUDE.md`. |

Inside `deck-finder`:
- `index.html`: the whole app, about 70 KB.
- `sw.js`: offline support, cache per app version plus one cache per saved ship.
- `version.json`, `CHANGELOG.md`, `manifest.webmanifest`, `icon-192.png`, `icon-512.png`.
- `ships/index.json`: the catalog, with a hash per ship.
- `ships/ncl/line.json`.
- `ships/ncl/<ship>/`: `ship.json`, one `deck<N>.webp` per deck, and for Getaway only, `geometry.json`.
- `tools/`: `build_index.py`, `calibrate_decks.py`, and `split_images.py` (one-time, already used). Not published.
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

### Saved data on the phone

Two localStorage keys:
- **`deckfinder`** (the view): `ship`, `deck`, `zoom`, and since 1.7.0, `layout`.
- **`deckfinder-trips`**: `trips`, `activeTripId`, `workerUrl`. Each trip has `id`, `ship`, `date`, `cabin`, `pin`, `itinerary`, and since 1.6.0, `pins`.

Fields have only been added, never renamed or reshaped.

## Known issues and limitations

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
- **Local preview:** a session needs its own `.claude/launch.json` running `python -m http.server <port> -d D:/AI-VAULT/projects/deck-finder`. The one from the 2026-09-23 session lived in a scratch folder.

## Parked work

- **Great Stirrup Cay island map.** A plan exists, but it is not in either repo or in `C:\DeckPlans`, and it wasn't made in the session that wrote these notes. It is probably in a Claude chat. It is waiting on two decisions from David:
  - how new venues on the island should be placed on the map,
  - the scope of the feature.

  Ask David for the plan before starting.
- **Joy and Aqua reviews in deck-finder-builder.** The pipeline has run on both ships with the current rules. For each ship:
  1. Review `deck-vision/out/<ship>/ship.json` on the review page.
  2. Save the result to `deck-vision/reviewed/ncl/<ship>/ship.json` and commit it in the builder.
  3. Run `make_app_json.py` on the reviewed file to make `geometry.json`.
  4. Add it to the public repo as a normal versioned release, following CLAUDE.md.

  Aqua 13768 is recorded as misprinted `13168` in `rules.json`.
