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
"""
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

# 6. ships/index.json is up to date
sys.path.insert(0, "tools")
try:
    import build_index
    current = Path("ships/index.json").read_text(encoding="utf-8") if Path("ships/index.json").exists() else ""
    if current != build_index.render():
        fail("ships/index.json is out of date. Run python tools/build_index.py and commit the result.")
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
