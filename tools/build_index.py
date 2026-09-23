"""
Builds ships/index.json, the catalog the app reads to find every cruise line and ship.

For each ship it records the folder path, deck count, total bytes, and a content hash of
all the ship's files. The app re-downloads a saved ship only when that hash changes.

Run from the repo root after changing anything under ships/:  python tools/build_index.py
"""
import hashlib
import json
from pathlib import Path

SHIPS_DIR = Path("ships")
INDEX = SHIPS_DIR / "index.json"


def ship_hash(folder):
    """sha256 over every file in the ship folder (name, size, bytes), in a fixed order."""
    h = hashlib.sha256()
    for f in sorted(p for p in folder.iterdir() if p.is_file()):
        data = f.read_bytes()
        h.update(f"{f.name}\n{len(data)}\n".encode())
        h.update(data)
    return h.hexdigest()


def build():
    lines = []
    for line_file in sorted(SHIPS_DIR.glob("*/line.json")):
        line = json.loads(line_file.read_text(encoding="utf-8"))
        ships = []
        for ship_file in line_file.parent.glob("*/ship.json"):
            ship = json.loads(ship_file.read_text(encoding="utf-8"))
            folder = ship_file.parent
            ships.append({
                "id": ship["id"],
                "name": ship["name"],
                "path": folder.as_posix() + "/",
                "decks": len(ship["decks"]),
                "bytes": sum(p.stat().st_size for p in folder.iterdir() if p.is_file()),
                "hash": ship_hash(folder),
            })
        ships.sort(key=lambda s: s["name"])
        lines.append({"id": line["id"], "name": line["name"], "path": line_file.parent.as_posix() + "/", "ships": ships})
    return {"lines": lines}


def render():
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    INDEX.write_text(render(), encoding="utf-8", newline="\n")
    for line in build()["lines"]:
        for s in line["ships"]:
            print(f'{s["id"]}: {s["decks"]} decks, {s["bytes"]:,} bytes, hash {s["hash"][:12]}')
