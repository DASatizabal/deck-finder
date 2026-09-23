"""
One-time tool: move the deck plan images out of index.html into per-ship folders.

Reads the `const IMG = {...};` line of index.html (without ever printing it) and saves
each image, for keys like "getaway:5", to ships/ncl/<ship>/deck<N>.webp.

Run from the repo root:  python tools/split_images.py
"""
import base64
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LINE = "ncl"  # every ship in the old IMG object is a Norwegian Cruise Line ship

html = Path("index.html").read_text(encoding="utf-8")
m = re.search(r"^const IMG = (\{.*\});\s*$", html, re.M)
if not m:
    sys.exit("No `const IMG = {...};` line found in index.html. Nothing to split.")
images = json.loads(m.group(1))

counts = defaultdict(list)
for key, uri in images.items():
    ship, deck = key.split(":")
    head, b64 = uri.split(",", 1)
    if head != "data:image/webp;base64":
        sys.exit(f"{key} is not a base64 WebP image ({head[:30]}). Stopping so nothing is lost.")
    out = Path("ships") / LINE / ship / f"deck{int(deck)}.webp"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    counts[ship].append(int(deck))

for ship, decks in sorted(counts.items()):
    decks.sort()
    print(f"{ship}: {len(decks)} decks ({decks[0]} to {decks[-1]})")
