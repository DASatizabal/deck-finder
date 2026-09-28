# Deck Finder: rules for every change

Also read NOTES.md at the start of every session for current state and known issues.

Deck Finder is an offline cruise ship deck map web app (PWA) hosted on GitHub Pages, used by David's family on Android (Chrome), iPhone (Safari home screen), and later an Android Capacitor build. These rules apply to every change, whether made in Claude Code or Claude chat.

## Version numbers (Semantic Versioning: MAJOR.MINOR.PATCH)
- PATCH (1.4.0 to 1.4.1): bug fixes, typo fixes, data corrections.
- MINOR (1.4.1 to 1.5.0): new features or new ships.
- MAJOR (1.5.0 to 2.0.0): changes that break saved data (trips, pins) or change how the app is installed.

## Every change to the app must do ALL of these, in one commit
1. Bump the version in these three places so they match exactly:
   - `const APP_VERSION = "1.4.1";` in `index.html`
   - `const VERSION = "deckfinder-v1.4.1";` in `sw.js`
   - `version.json` with fields `version`, `date` (YYYY-MM-DD), and `notes` (one short sentence)
2. Add an entry at the TOP of `CHANGELOG.md` (below the `# Changelog` title) in exactly this format:
   ```
   ## [1.4.1] - 2026-09-24
   ### Fixed
   - Plain-language description of what changed for the family.
   ```
   Use only the headings that apply: Added, Changed, Fixed, Removed. Write for a non-technical family member.
3. Commit message format: `v1.4.1: short summary`.
4. Push to main. Do NOT create or push git tags. The GitHub Action creates the tag and the Release page after the checks pass.
5. Wait about 3 minutes, then confirm the Action passed and the live site's `version.json` shows the new version.

Changes that only touch `CLAUDE.md`, `README.md`, `NOTES.md`, the `worker` folder, or the `tools` folder don't need a version bump. The Action ignores them (see `paths-ignore` in `publish.yml`). A commit that also touches any app file still runs the Action and needs the full release steps.

## The GitHub Action is the final gate
`.github/workflows/publish.yml` runs `.github/scripts/check_release.py` on every push to main. It publishes the site ONLY if:
- `version.json`, `APP_VERSION`, and the `sw.js` VERSION all match,
- the version is higher than the newest `v*` tag,
- `CHANGELOG.md` starts with an entry for this version,
- the JavaScript in `index.html` has no syntax errors.
Before pushing, run `python .github/scripts/check_release.py` locally (needs git and Node.js) and fix every FAIL line. It deletes its temporary files when done, but `release_notes.md` may be left behind: never commit it.

## Keeping every device on the latest version
- `sw.js` must fetch `index.html`, `version.json`, and `ships/index.json` network-first (3-second timeout), falling back to the cache when offline. All other files can be cache-first.
- Each ship saved for offline lives in its own cache named `deckfinder-ship-<line>-<ship>`. Never delete these when the app version changes. The app re-downloads a saved ship only when its hash in `ships/index.json` changes.
- The app checks `version.json` with `cache: "no-store"` on open and when it returns to the foreground. If the live version is newer than `APP_VERSION`, show a banner: "Update available (vX.Y.Z). Tap to update." Tapping it activates the new service worker and reloads.
- The menu shows "Version X.Y.Z (date)" and a "What's new" item that displays the latest `version.json` notes.
- Never remove the offline fallback. The app must still open with no internet at sea.

## Ship data
- Deck plans live in `ships/<line>/<ship>/`: a `ship.json` (name, `itinerary_code`, and each deck's `image` and `venues`) plus one `deck<N>.webp` per deck. Each line has `ships/<line>/line.json`.
- After adding or changing deck images, run `python tools/calibrate_decks.py` (needs Pillow and numpy). It stores each deck's `ship_extent` (where the ship's drawing starts and ends), which the app uses to keep your place when you change decks. The release check fails if a deck has none.
- After adding or changing anything under `ships/`, run `python tools/build_index.py` and commit the updated `ships/index.json`. The release check fails if it is out of date.
- Ship ids are `<line>/<ship>`, like `ncl/getaway`. Saved trips store these ids.
- A ship's `ship.json` may name a `"geometry"` file (for example `geometry.json`) with cabin, venue, amenity and landmark boxes. It comes from the private deck-finder-builder repo's `make_app_json.py`, run on a reviewed ship. Never copy a Deck Vision review file over `ship.json`; the release check rejects it.
- The `tools` folder is not published to the website.

## Cloudflare Worker (the backup helper)
- Its code lives in `worker/worker.js`. The `worker` folder is not published to the website, and Cloudflare does not deploy from this repo: after changing the file, David pastes it into the Cloudflare dashboard.
- Routes: `/?path=` is the NCL proxy (only the allowed NCL paths). `/itinerary?ship=&line=&date=` asks CruiseFeed for sold-out and past sailings and needs the header `X-DeckFinder-Pass` to match the Worker secret `APP_PASS`.
- The CruiseFeed key lives only in the Worker secret `CRUISEFEED_KEY` and in `D:\AI-VAULT\secrets\cruisefeed_key.txt`. Never print it, never copy that file, and never put the key in any file in this repo.
- The Worker keeps every itinerary it finds in the KV namespace bound as `ITINERARIES` (key `itin:<cruise line>:<ship>:<YYYY-MM-DD>`, no expiry), shared by every phone. It checks KV before CruiseFeed. KV holds only public sailing data, never anything from the request. `python tools/kv_put.py <file>` writes one itinerary there by hand (examples in `tools/itineraries/`).
- CruiseFeed's free allowance is 300 results for the life of the key and never resets. Every `/itinerary` lookup that isn't in KV yet spends one. To check what is left for free, run a `/v1/cruises` query that matches nothing (for example a 1990 departure date) and read `x-results-remaining`; `/v1/stats` doesn't report it. Never run CruiseFeed queries without David's say-so, and always use `limit=1`.

## Warnings
- Saved user data lives in the phone's localStorage under the keys `deckfinder` and `deckfinder-trips`. Never rename these keys or change their shape without a migration, and treat that as a MAJOR version.
- Always start from the latest `main` (`git pull`) before editing, so work from Claude chat and Claude Code never overwrites each other.

## Writing style for anything David reads
- No em dashes.
- Write step-by-step instructions out in full. Never say "same as step 3" or "see above."
- Do not leave decisions to the reader with "if you want X." Build each case out as its own numbered steps.
