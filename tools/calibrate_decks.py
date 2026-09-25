"""
Finds where the ship's drawing starts and ends on every deck plan, and saves it in ship.json.

For each deck image in ships/<line>/<ship>/, the tool looks for the first and last rows of the
ship's drawing and stores them in that deck's entry as
    "ship_extent": {"top": <percent of image height>, "bottom": <percent of image height>}
The app uses it to keep your place when you change decks: the same fraction of the way from
the top to the bottom of the ship on one deck maps to the same fraction on the next deck.

How the rows are found:
  * A pixel is part of the drawing when it isn't white (any channel below 235). On most decks
    the hull outline is dark, but on some top decks it is light gray or only colored deck areas.
  * The orange ship icon (a small solid orange shape) is left out.
  * Rows with drawing are grouped into runs, allowing gaps of up to MAX_GAP rows. The ship
    spans from the first to the last run that is at least MIN_RUN of the image height (top
    decks have big white open areas, so the ship can be several runs). Small marks separated
    from the ship by white space (the CDP watermark) are dropped; the watermark and icon that
    sit inside the ship don't change its first or last row.

Run from the repo root (needs Pillow and numpy), then run tools/build_index.py:
    python tools/calibrate_decks.py
    python tools/build_index.py
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

MAX_GAP = 10       # rows of white allowed inside the ship's drawing
MIN_PIXELS = 2     # a row counts as drawing when it has at least this many drawing pixels
MIN_RUN = 0.02     # a run of drawing rows counts as ship when it is at least 2% of the image height


def extent(path: Path):
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    H = rgb.shape[0]
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    drawing = rgb.min(axis=2) < 235
    icon = (r > 200) & (g > 90) & (g < 170) & (b < 80)            # the orange ship icon
    rows = np.where((drawing & ~icon).sum(axis=1) >= MIN_PIXELS)[0]
    if len(rows) == 0:
        return None
    # Split the drawing rows into runs wherever there is a gap bigger than MAX_GAP.
    runs, start, prev = [], rows[0], rows[0]
    for y in rows[1:]:
        if y - prev > MAX_GAP + 1:
            runs.append((start, prev))
            start = y
        prev = y
    runs.append((start, prev))
    # Top decks have big white open areas, so the ship can be several runs. Keep every run of
    # real size and span from the first to the last; tiny isolated marks are dropped.
    big = [ab for ab in runs if ab[1] - ab[0] + 1 >= MIN_RUN * H] or [max(runs, key=lambda ab: ab[1] - ab[0])]
    top, bottom = big[0][0], big[-1][1]
    return {"top": round(100 * top / H, 2), "bottom": round(100 * (bottom + 1) / H, 2)}


def main():
    for ship_file in sorted(Path("ships").glob("*/*/ship.json")):
        ship = json.loads(ship_file.read_text(encoding="utf-8"))
        for deck, info in ship["decks"].items():
            e = extent(ship_file.parent / info["image"])
            if e is None:
                raise SystemExit(f"{ship_file.parent}: deck {deck} image has no drawing")
            info["ship_extent"] = e
        ship_file.write_text(json.dumps(ship, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(ship["id"] + ":", ", ".join(f"{d} {v['ship_extent']['top']}-{v['ship_extent']['bottom']}"
                                          for d, v in ship["decks"].items()))


if __name__ == "__main__":
    main()
