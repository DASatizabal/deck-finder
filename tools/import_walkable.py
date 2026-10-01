"""
Copies a ship's walkable grids (the pathfinder's hallway maps) from the builder into this repo.

  python tools/import_walkable.py                 # Norwegian Getaway
  python tools/import_walkable.py --ship joy      # another ship, once the builder has made its grids

It reads D:\\AI-VAULT\\projects\\deck-finder-builder\\deck-vision\\out\\<ship>\\walkable\\ (index.json
and one deck<N>.json per deck; the overlay pictures are left behind), checks every file, and writes
them to ships/<line>/<ship>/walkable/. Deck files no longer in the builder's index.json are removed.
It adds "walkable": "walkable/index.json" to the ship's ship.json when it isn't there, then runs
tools/build_index.py, so the grids are saved for offline use with the ship. Commit the result as a
normal release (a PATCH version for a refresh).

It never changes the builder. When the walkable editor's corrections
(deck-vision/reviewed/<line>/<ship>/<ship>.walkable-overrides.json) are newer than the grids, it
stops and says to run build_walkable.py in the builder first, so a refresh never misses them.

Checks: each grid's bitmap has exactly cols x rows cells, the grid matches its deck image's size,
every deck of ship.json has a grid, every connection names decks that exist, and every access cell
lies inside its deck's grid.
"""
import argparse
import base64
import json
import math
import subprocess
import sys
from pathlib import Path

BUILDER = Path(r"D:\AI-VAULT\projects\deck-finder-builder\deck-vision")


def fail(msg):
    raise SystemExit("Not imported: " + msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ship", default="getaway")
    ap.add_argument("--line", default="ncl")
    ap.add_argument("--force", action="store_true", help="import even when the editor's corrections are newer than the grids")
    a = ap.parse_args()

    src = BUILDER / "out" / a.ship / "walkable"
    ship_dir = Path("ships") / a.line / a.ship
    dest = ship_dir / "walkable"
    ship_file = ship_dir / "ship.json"
    if not (src / "index.json").is_file():
        fail(f"{src / 'index.json'} doesn't exist. Run build_walkable.py --ship {a.ship} in the builder first.")
    if not ship_file.is_file():
        fail(f"{ship_file} doesn't exist")
    ovr = BUILDER / "reviewed" / a.line / a.ship / f"{a.ship}.walkable-overrides.json"
    if ovr.is_file() and ovr.stat().st_mtime > (src / "index.json").stat().st_mtime and not a.force:
        fail(f"the walkable editor's corrections ({ovr.name}) are newer than the grids. In the builder's deck-vision folder, "
             f"run: python build_walkable.py --ship {a.ship} --images ..\\..\\deck-finder\\ships\\{a.line}\\{a.ship}  then run this again.")

    ship = json.loads(ship_file.read_text(encoding="utf-8"))
    idx = json.loads((src / "index.json").read_text(encoding="utf-8"))
    ship_decks = {int(k) for k in ship["decks"]}
    grid_decks = {int(k) for k in idx.get("decks", {})}
    if ship_decks - grid_decks:
        fail(f"no grid for deck(s) {sorted(ship_decks - grid_decks)}")
    if grid_decks - ship_decks:
        fail(f"grids for deck(s) {sorted(grid_decks - ship_decks)}, which ship.json doesn't have")
    for c in idx.get("connections", []):
        bad = [d for d in c.get("decks", []) if d not in ship_decks]
        if bad or not c.get("decks") or c.get("kind") not in ("stairs", "elevator"):
            fail(f"connection {c.get('id')!r} names decks {c.get('decks')} (kind {c.get('kind')!r}); bad decks: {bad}")

    files = {"index.json": (src / "index.json").read_bytes()}
    for d, name in idx["decks"].items():
        raw = (src / name).read_bytes()
        g = json.loads(raw)
        cols, rows = g["cols"], g["rows"]
        nbytes = len(base64.b64decode(g["walkable"]))
        if nbytes != math.ceil(cols * rows / 8):
            fail(f"{name}: the bitmap has {nbytes} bytes, but {cols} x {rows} cells need {math.ceil(cols * rows / 8)}")
        img = ship_dir / ship["decks"][str(d)]["image"]
        try:
            from PIL import Image
            size = list(Image.open(img).size)
            if size != list(g["image_size"]):
                fail(f"{name} was made for a {g['image_size']} image, but {img} is {size}")
        except ImportError:
            print("note: Pillow isn't installed, so the image sizes weren't compared")
        for c in g.get("connections", []):
            for col, row in c.get("access", []):
                if not (0 <= col < cols and 0 <= row < rows):
                    fail(f"{name}: {c['id']!r} has an access cell [{col}, {row}] outside the {cols} x {rows} grid")
        files[name] = raw

    dest.mkdir(parents=True, exist_ok=True)
    changed = []
    for name, raw in files.items():
        raw = raw.replace(b"\r\n", b"\n")
        p = dest / name
        if not p.is_file() or p.read_bytes() != raw:
            changed.append(name)
            p.write_bytes(raw)
    removed = [p.name for p in dest.glob("*.json") if p.name not in files]
    for n in removed:
        (dest / n).unlink()

    if ship.get("walkable") != "walkable/index.json":
        text = ship_file.read_text(encoding="utf-8")
        ship_obj = json.loads(text)
        ship_obj["walkable"] = "walkable/index.json"
        with open(ship_file, "w", encoding="utf-8", newline="\n") as f:
            json.dump(ship_obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        changed.append("../ship.json (added \"walkable\")")

    print(f"{a.ship}: {len(grid_decks)} decks, {len(idx.get('connections', []))} stairs and elevator connections")
    print("  changed: " + (", ".join(changed) if changed else "nothing, the files were already the same"))
    if removed:
        print("  removed: " + ", ".join(removed))
    sys.stdout.flush()
    subprocess.run([sys.executable, "tools/build_index.py"], check=True)
    print("Next: test the routes, bump the version (PATCH), add a CHANGELOG entry, and run python .github/scripts/check_release.py")


if __name__ == "__main__":
    main()
