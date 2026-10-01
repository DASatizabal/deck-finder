"""
Release inspector for Deck Finder. GitHub Actions runs this on every push to main.
If any check fails, the site is NOT published and the commit gets a red X.

Checks:
1. version.json, APP_VERSION in index.html, and VERSION in sw.js all match.
2. The version is higher than the newest existing git tag.
3. CHANGELOG.md starts with an entry for this version.
4. The JavaScript in index.html has no syntax errors.
5. Every deck image named in each ships/<line>/<ship>/ship.json exists.
6. ships/index.json matches what tools/build_index.py would generate right now.
7. Every ships/<line>/<ship>/ship.json has the app's format (id, line, name, itinerary_code,
   and decks that each have an image and a venues list), and is not a Deck Vision review file.
8. Every geometry file named in a ship.json exists and is valid JSON.
9. Every deck in every ship.json has a ship_extent with top less than bottom, both 0 to 100.
10. Every island map (places/<id>/place.json) is valid JSON and names a basemap, a places file and
    a survey list that exist and are valid JSON. The basemap carries the OpenStreetMap attribution,
    and every place has a lat and lon inside the island's bounds. Since 1.11.1, an island that names
    an "areas" file must have exactly five areas (each with an id, name, #RRGGBB color and an outline
    of at least three [lat, lon] corners), and every place and survey venue's area_id must be one of
    them. No name the family sees may contain a builder note like "(marker 3-b)". Since 1.13.0, an
    island that names a "tram_routes" file must have valid routes: each a line of at least two
    [lon, lat] points, with at least two stops, and every stop an active tram stop in the places file
    (category "tram", same stop_number). Since 1.15.0, an island that names a "sign_alignment" file
    must have valid control points (at least three, each with x, y, lat and lon, the lat and lon
    inside the island's bounds), the image's width, height and a 64-digit fingerprint, and a map
    panel; and no image file of any kind may sit anywhere under places/, because the island sign
    image must never be published.
11. Since 1.16.0, a ship.json that names a "walkable" index must have a grid for every deck (each a
    bitmap of exactly cols x rows cells, with access cells inside it), and every stairs or elevator
    connection must name only decks the ship has. A "directions" rules file must have its costs as
    positive numbers and a list of tips. Since 1.16.2 its "either" stairs limit must be a whole number
    above 0, and each of its "names" must name a stairway or elevator bank of the walkable index (with
    the same decks).
"""
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

errors = []


def fail(msg):
    errors.append(msg)
    print(f"FAIL: {msg}")


def load_json(path, label):
    if not path.is_file():
        fail(f"{label} is missing")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{label} is not valid JSON: {e}")
        return None


def parse(v):
    return tuple(int(x) for x in v.split("."))


# 1. Versions match
info = json.loads(Path("version.json").read_text(encoding="utf-8"))
version = info.get("version", "")
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    fail(f'version.json "version" must look like 1.4.0, found "{version}"')
for field in ("date", "notes"):
    if not info.get(field):
        fail(f'version.json is missing "{field}"')

html = Path("index.html").read_text(encoding="utf-8")
m = re.search(r'const APP_VERSION\s*=\s*"([^"]+)"', html)
app_version = m.group(1) if m else None
if app_version != version:
    fail(f"APP_VERSION in index.html is {app_version}, but version.json says {version}")

sw = Path("sw.js").read_text(encoding="utf-8")
m = re.search(r'const VERSION\s*=\s*"deckfinder-v([^"]+)"', sw)
sw_version = m.group(1) if m else None
if sw_version != version:
    fail(f"VERSION in sw.js is deckfinder-v{sw_version}, but version.json says {version}")

# 2. Higher than the newest tag
tags = subprocess.run(["git", "tag", "--list", "v*"], capture_output=True, text=True).stdout.split()
released = sorted((parse(t[1:]) for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+", t)), reverse=True)
if released and re.fullmatch(r"\d+\.\d+\.\d+", version) and parse(version) <= released[0]:
    newest = ".".join(map(str, released[0]))
    fail(f"version {version} is not higher than the newest release v{newest}. Bump the version.")

# 3. Changelog has this version at the top
changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
headings = re.findall(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})", changelog, re.M)
if not headings or headings[0][0] != version:
    top = headings[0][0] if headings else "nothing"
    fail(f"CHANGELOG.md must start with '## [{version}] - YYYY-MM-DD', but the first entry is {top}")
else:
    # Save this version's notes for the GitHub Release page
    start = changelog.index(f"## [{version}]")
    nxt = changelog.find("\n## [", start + 1)
    Path("release_notes.md").write_text(changelog[start: nxt if nxt != -1 else None].strip() + "\n", encoding="utf-8")

# 4. JavaScript syntax check (catches a broken app before family members get it)
scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
Path("app_check.js").write_text("\n;\n".join(scripts), encoding="utf-8")
result = subprocess.run(["node", "--check", "app_check.js"], capture_output=True, text=True)
if result.returncode != 0:
    fail("index.html has a JavaScript error:\n" + result.stderr[-1500:])
Path("app_check.js").unlink(missing_ok=True)

# 5. Every deck image named in each ship.json exists
ship_files = sorted(Path("ships").glob("*/*/ship.json"))
if not ship_files:
    fail("no ships found (expected ships/<line>/<ship>/ship.json)")
for ship_file in ship_files:
    folder = ship_file.parent.as_posix()
    try:
        ship = json.loads(ship_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{folder}/ship.json is not valid JSON: {e}")
        continue

    # 7. ship.json has the app's format. A Deck Vision review file (from the builder repo) has
    #    "ship", "source_folder" and "generated" at the top and cabin boxes in every deck; the app
    #    can't read it, so catch it before it is published.
    review_keys = [k for k in ("source_folder", "generated", "issues", "category_shades") if k in ship]
    decks = ship.get("decks")
    if review_keys or (isinstance(decks, dict) and any(isinstance(v, dict) and "cabins" in v for v in decks.values())):
        fail(f"{folder}/ship.json looks like a Deck Vision review file, not the app's ship.json "
             f"(it has {', '.join(review_keys) or 'cabin boxes in its decks'}). Restore it with: "
             f"git restore {folder}/ship.json. Reviewed geometry belongs in geometry.json, made by make_app_json.py.")
        continue
    missing = [k for k in ("id", "line", "name", "itinerary_code") if not ship.get(k)]
    if missing:
        fail(f"{folder}/ship.json is missing {', '.join(missing)}")
    if not isinstance(decks, dict) or not decks:
        fail(f"{folder}/ship.json needs a \"decks\" object with at least one deck")
        continue
    for deck, info in decks.items():
        if not isinstance(info, dict) or not isinstance(info.get("image"), str) or not isinstance(info.get("venues"), list):
            fail(f"{folder}/ship.json deck {deck} needs an \"image\" file name and a \"venues\" list")
            continue
        # 5. Every deck image named in each ship.json exists
        if not (ship_file.parent / info["image"]).is_file():
            fail(f"{folder}: deck {deck} image {info['image']!r} is missing")
        # 9. Every deck has a ship_extent (from tools/calibrate_decks.py) with 0 <= top < bottom <= 100
        ext = info.get("ship_extent")
        ok = isinstance(ext, dict) and all(isinstance(ext.get(k), (int, float)) for k in ("top", "bottom"))
        if not ok or not (0 <= ext["top"] < ext["bottom"] <= 100):
            fail(f"{folder}/ship.json deck {deck} needs a \"ship_extent\" with top less than bottom, both "
                 f"between 0 and 100 (found {ext!r}). Run python tools/calibrate_decks.py.")

    # 8. A geometry file named in ship.json exists and is valid JSON
    geo = ship.get("geometry")
    if geo is not None:
        gpath = ship_file.parent / str(geo)
        if not isinstance(geo, str) or not gpath.is_file():
            fail(f"{folder}/ship.json names geometry {geo!r}, but that file is missing")
        else:
            try:
                g = json.loads(gpath.read_text(encoding="utf-8"))
                if not isinstance(g.get("decks"), dict):
                    fail(f"{folder}/{geo} has no \"decks\" object")
            except json.JSONDecodeError as e:
                fail(f"{folder}/{geo} is not valid JSON: {e}")

    # 11. Walkable grids for Directions (1.16.0): every deck has a grid of the right size, and every
    #     stairs or elevator connection names real decks, with access cells inside the grids.
    wk = ship.get("walkable")
    widx = None
    if wk is not None:
        wpath = ship_file.parent / str(wk)
        widx = load_json(wpath, f"{folder}/{wk}") if isinstance(wk, str) else None
        if isinstance(widx, dict):
            wdecks = widx.get("decks") if isinstance(widx.get("decks"), dict) else {}
            ship_decks = {str(k) for k in decks}
            for d in sorted(ship_decks - set(wdecks), key=int):
                fail(f"{folder}/{wk} has no grid for deck {d}. Run python tools/import_walkable.py.")
            for d in sorted(set(wdecks) - ship_decks, key=lambda x: int(x) if str(x).isdigit() else 0):
                fail(f"{folder}/{wk} has a grid for deck {d}, which {folder}/ship.json doesn't have")
            for c in widx.get("connections") or []:
                cd = c.get("decks") if isinstance(c, dict) else None
                if not (isinstance(c, dict) and c.get("kind") in ("stairs", "elevator") and isinstance(cd, list) and cd
                        and all(str(x) in ship_decks for x in cd)):
                    fail(f"{folder}/{wk}: connection {c.get('id') if isinstance(c, dict) else c!r} must be stairs or elevator and name only decks the ship has (found {cd!r})")
            for d, fname in wdecks.items():
                gfile = wpath.parent / str(fname)
                g = load_json(gfile, f"{folder}/{gfile.relative_to(ship_file.parent).as_posix()}")
                if not isinstance(g, dict):
                    continue
                cols, rows = g.get("cols"), g.get("rows")
                try:
                    nbytes = len(base64.b64decode(g.get("walkable", ""), validate=True))
                except Exception:
                    nbytes = -1
                if not (isinstance(cols, int) and isinstance(rows, int) and nbytes == (cols * rows + 7) // 8):
                    fail(f"{folder}/{fname}: the grid needs cols, rows and a bitmap of exactly cols x rows cells")
                    continue
                for c in g.get("connections") or []:
                    if any(not (0 <= a[0] < cols and 0 <= a[1] < rows) for a in c.get("access") or []):
                        fail(f"{folder}/{fname}: {c.get('id')!r} has an access cell outside the grid")
    # The Directions rules (1.16.0): costs as numbers and a list of tips.
    dr = ship.get("directions")
    if dr is not None:
        rules = load_json(ship_file.parent / str(dr), f"{folder}/{dr}")
        if isinstance(rules, dict):
            costs = rules.get("costs") or {}
            need = ("ship_length_m", "walk_m_per_s", "stairs_up_s_per_deck", "stairs_down_s_per_deck", "elevator_wait_s", "elevator_s_per_deck")
            if not all(isinstance(costs.get(k), (int, float)) and costs[k] > 0 for k in need):
                fail(f"{folder}/{dr} needs \"costs\" with {', '.join(need)} as positive numbers")
            if not isinstance(rules.get("tips"), list) or not all(isinstance(t, dict) and t.get("id") and t.get("text") for t in rules["tips"]):
                fail(f"{folder}/{dr} needs a \"tips\" list, each with an id and a text")
            # Since 1.16.2: the stairs limit in Either mode, and friendly names for stairways and elevator
            # banks, each naming a connection of the walkable index with the same decks.
            ei = rules.get("either")
            if ei is not None and not (isinstance(ei, dict) and isinstance(ei.get("max_stairs_decks_in_a_row"), int) and ei["max_stairs_decks_in_a_row"] > 0):
                fail(f"{folder}/{dr}: \"either\" needs \"max_stairs_decks_in_a_row\" as a whole number above 0")
            names = rules.get("names")
            if names is not None:
                conns = {c.get("id"): c.get("decks") for c in (widx or {}).get("connections") or [] if isinstance(c, dict)}
                for cid, n in (names.items() if isinstance(names, dict) else []):
                    if not (isinstance(n, dict) and isinstance(n.get("text"), str) and n["text"].strip()):
                        fail(f"{folder}/{dr}: the name for {cid!r} needs a \"text\"")
                    elif cid not in conns or (n.get("decks") is not None and sorted(n["decks"]) != sorted(conns[cid] or [])):
                        fail(f"{folder}/{dr}: the name for {cid!r} (decks {n.get('decks')}) matches no stairway or elevator bank in {folder}/{wk} (found decks {conns.get(cid)}). The builder may have renumbered it: check the walkable index and fix the name.")
                if not isinstance(names, dict):
                    fail(f"{folder}/{dr}: \"names\" must map connection ids to names")

# 10. Island maps: the files exist, are valid JSON, and every place sits inside the island's bounds
num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
for place_file in sorted(Path("places").glob("*/place.json")):
    folder = place_file.parent
    fname = folder.as_posix()
    place = load_json(place_file, f"{fname}/place.json")
    if not isinstance(place, dict):
        continue
    missing = [k for k in ("id", "name", "port_name", "basemap", "places", "survey_list", "bounds") if not place.get(k)]
    if missing:
        fail(f"{fname}/place.json is missing {', '.join(missing)}")
        continue
    b = place["bounds"]
    if not (isinstance(b, dict) and all(num(b.get(k)) for k in ("min_lat", "min_lon", "max_lat", "max_lon"))
            and b["min_lat"] < b["max_lat"] and b["min_lon"] < b["max_lon"]):
        fail(f"{fname}/place.json needs \"bounds\" with min_lat, min_lon, max_lat and max_lon (min less than max)")
        continue
    base = load_json(folder / place["basemap"], f"{fname}/{place['basemap']}")
    if isinstance(base, dict):
        if "OpenStreetMap" not in str(base.get("attribution", "")):
            fail(f"{fname}/{place['basemap']} must keep its \"attribution\": \"© OpenStreetMap contributors\"")
        if not isinstance(base.get("features"), list) or not any(f.get("properties", {}).get("kind") == "land" for f in base["features"]):
            fail(f"{fname}/{place['basemap']} has no land shapes. Run python tools/build_island.py.")
    plist = load_json(folder / place["places"], f"{fname}/{place['places']}")
    if isinstance(plist, dict):
        if not isinstance(plist.get("places"), list):
            fail(f"{fname}/{place['places']} needs a \"places\" list")
        else:
            for pl in plist["places"]:
                lat, lon = pl.get("lat"), pl.get("lon")
                nm = pl.get("display_name") or pl.get("name")
                if not nm or not num(lat) or not num(lon):
                    fail(f"{fname}/{place['places']}: place {nm or pl.get('id')!r} needs a display_name, lat and lon")
                elif not (b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]):
                    fail(f"{fname}/{place['places']}: {nm!r} at {lat}, {lon} is outside the island's bounds")
    survey = load_json(folder / place["survey_list"], f"{fname}/{place['survey_list']}")
    if isinstance(survey, dict) and not isinstance(survey.get("venues"), list):
        fail(f"{fname}/{place['survey_list']} needs a \"venues\" list")
    shown = [("places", x) for x in (plist.get("places") if isinstance(plist, dict) and isinstance(plist.get("places"), list) else [])]         + [("survey list", x) for x in (survey.get("venues") if isinstance(survey, dict) and isinstance(survey.get("venues"), list) else [])]
    for where, x in shown:
        if "(marker" in str(x.get("display_name") or x.get("name") or ""):
            fail(f"{fname} {where}: {x.get('id')!r} shows a builder note in its name: {x.get('display_name') or x.get('name')!r}")
    # Areas (1.11.1): the five areas on the island sign.
    if place.get("areas"):
        areas = load_json(folder / place["areas"], f"{fname}/{place['areas']}")
        alist = areas.get("areas") if isinstance(areas, dict) else None
        if not isinstance(alist, list):
            fail(f"{fname}/{place['areas']} needs an \"areas\" list")
        else:
            if len(alist) != 5:
                fail(f"{fname}/{place['areas']} has {len(alist)} areas; the island sign has five")
            ids = set()
            for a in alist:
                oc = a.get("outline") if isinstance(a, dict) else None
                if not (isinstance(a, dict) and a.get("id") and a.get("name") and re.fullmatch(r"#[0-9A-Fa-f]{6}", str(a.get("color", "")))
                        and isinstance(oc, list) and len(oc) >= 3 and all(isinstance(c, list) and len(c) == 2 and num(c[0]) and num(c[1]) for c in oc)):
                    fail(f"{fname}/{place['areas']}: area {a.get('id') if isinstance(a, dict) else a!r} needs an id, name, #RRGGBB color and an outline of at least three [lat, lon] corners")
                    continue
                ids.add(a["id"])
            for where, x in shown:
                if x.get("area_id") not in ids:
                    fail(f"{fname} {where}: {x.get('id')!r} has area_id {x.get('area_id')!r}, which is not in {place['areas']}")
    # Tram routes (1.13.0): valid lines whose stops are all active tram stops.
    if place.get("tram_routes"):
        tf = f"{fname}/{place['tram_routes']}"
        routes = load_json(folder / place["tram_routes"], tf)
        feats = routes.get("features") if isinstance(routes, dict) else None
        if isinstance(routes, dict) and (not isinstance(feats, list) or not feats):
            fail(f"{tf} needs a \"features\" list with at least one route")
        elif isinstance(feats, list):
            trams = {x.get("id"): x for x in (plist.get("places") if isinstance(plist, dict) and isinstance(plist.get("places"), list) else [])
                     if x.get("category") == "tram"}
            for f in feats:
                pr = f.get("properties") if isinstance(f, dict) else None
                geo = f.get("geometry") if isinstance(f, dict) else None
                name = (pr or {}).get("name") or "a route"
                if not isinstance(pr, dict) or not pr.get("name") or not isinstance(pr.get("route_number"), int):
                    fail(f"{tf}: {name!r} needs a name and a route_number")
                coords = geo.get("coordinates") if isinstance(geo, dict) and geo.get("type") == "LineString" else None
                if not (isinstance(coords, list) and len(coords) >= 2 and all(isinstance(c, list) and len(c) == 2 and num(c[0]) and num(c[1])
                                                                               and b["min_lon"] <= c[0] <= b["max_lon"] and b["min_lat"] <= c[1] <= b["max_lat"] for c in coords)):
                    fail(f"{tf}: {name!r} needs a LineString line of at least two [lon, lat] points inside the island's bounds")
                stops = (pr or {}).get("stops")
                if not isinstance(stops, list) or len(stops) < 2:
                    fail(f"{tf}: {name!r} needs at least two stops")
                    continue
                for st in stops:
                    sid = st.get("id") if isinstance(st, dict) else st
                    if sid not in trams:
                        fail(f"{tf}: {name!r} names stop {sid!r}, which is not an active tram stop in {place['places']}")
                    elif trams[sid].get("stop_number") != st.get("stop_number"):
                        fail(f"{tf}: {name!r} calls {sid!r} stop {st.get('stop_number')!r}, but {place['places']} says {trams[sid].get('stop_number')!r}")

    # Island sign alignment (1.15.0): control points only, never the image.
    if place.get("sign_alignment"):
        sf = f"{fname}/{place['sign_alignment']}"
        sa = load_json(folder / place["sign_alignment"], sf)
        if isinstance(sa, dict):
            pairs = sa.get("pairs")
            im = sa.get("image") if isinstance(sa.get("image"), dict) else {}
            mp = sa.get("map_panel") if isinstance(sa.get("map_panel"), dict) else {}
            if not (isinstance(pairs, list) and len(pairs) >= 3 and all(isinstance(q, dict) and all(num(q.get(k)) for k in ("x", "y", "lat", "lon"))
                                                                       and b["min_lat"] <= q["lat"] <= b["max_lat"] and b["min_lon"] <= q["lon"] <= b["max_lon"] for q in pairs)):
                fail(f"{sf} needs at least three control points, each with x, y, lat and lon inside the island's bounds")
            if not (isinstance(im.get("width"), int) and isinstance(im.get("height"), int) and im["width"] > 0 and im["height"] > 0
                    and re.fullmatch(r"[0-9a-f]{64}", str((im.get("fingerprint") or {}).get("value", "")))):
                fail(f"{sf} needs the image's width, height and fingerprint. Run python tools/make_sign_alignment.py.")
            if not all(num(mp.get(k)) for k in ("x0", "y0", "x1", "y1")):
                fail(f"{sf} needs a map_panel with x0, y0, x1 and y1")
            if any(k in sa for k in ("data", "image_data", "base64")):
                fail(f"{sf} must hold coordinates only, never image data")
for img in sorted(x for x in Path("places").rglob("*") if x.is_file() and x.suffix.lower() in (".webp", ".png", ".jpg", ".jpeg", ".gif", ".avif", ".heic", ".bmp", ".tif", ".tiff")):
    fail(f"{img.as_posix()} is an image under places/. Island images (like the island sign) must never be published. Remove it.")

# 6. ships/index.json is up to date
sys.path.insert(0, "tools")
try:
    import build_index
    current = Path("ships/index.json").read_text(encoding="utf-8") if Path("ships/index.json").exists() else ""
    if current != build_index.render():
        fail("ships/index.json is out of date (ships or island maps changed). Run python tools/build_index.py and commit the result.")
except Exception as e:
    fail(f"could not run tools/build_index.py: {e}")

if errors:
    print(f"\n{len(errors)} problem(s) found. Nothing was published.")
    sys.exit(1)

print(f"All checks passed for version {version}.")
out = os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"version={version}\n")
