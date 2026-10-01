"""
Writes places/great-stirrup-cay/sign-alignment.json: how to lay NCL's island sign map over the real map.

The island sign image is private and is never copied into this repo. Each phone adds its own copy in
the app (Map view, Island sign), and the app keeps it on that phone only. This file holds only:
  - the control points from the builder's place editor (pixel x, y on the sign and the real lat, lon),
  - the map projection the place editor fits them in (the same thin-plate spline),
  - the part of the image that is the map (the title band and the legend are left out),
  - the original image's width, height and fingerprint, so the app can tell a wrong image apart.

The fingerprint is a 256-bit difference hash: the image on white, turned to gray, averaged into a grid
of 17 columns by 16 rows, then one bit per neighboring pair in each row (left brighter than right).
The app computes it the same way and accepts an image within FINGERPRINT_MAX_BITS of it, so a copy
that a phone re-saved or shrank still matches. The SHA-256 of the original file is kept as well.

Run from the repo root (reads the builder's files, never changes them):
  python tools/make_sign_alignment.py
Then python tools/build_index.py. Needs Pillow and numpy.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

REF = Path(r"D:\AI-VAULT\projects\deck-finder-builder\islands\great-stirrup-cay\reference")
OUT = Path("places/great-stirrup-cay/sign-alignment.json")
# The map part of the sign in pixels: below the dark title band (rows 0 to 291) and above the
# white legend (row 1334 down). Measured on the 1500 x 1865 original.
MAP_PANEL = {"x0": 0, "y0": 292, "x1": 1500, "y1": 1333}
FINGERPRINT_MAX_BITS = 40
# The place editor's projection (DEFAULT_CENTER in islands/place-editor.html): meters east and north
# of this point, divided by 1000 before fitting.
LAT0, LON0 = 25.8231433, -77.9105027


def dhash(img):
    rgba = img.convert("RGBA")
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    rgb = np.asarray(Image.alpha_composite(white, rgba).convert("RGB")).astype(np.float64)
    gray = (rgb[..., 0] * 299 + rgb[..., 1] * 587 + rgb[..., 2] * 114) / 1000
    h, w = gray.shape
    cols, rows = 17, 16
    cell = np.zeros((rows, cols))
    for r in range(rows):
        y0, y1 = r * h // rows, (r + 1) * h // rows
        for c in range(cols):
            x0, x1 = c * w // cols, (c + 1) * w // cols
            cell[r, c] = gray[y0:y1, x0:x1].mean()
    bits = "".join("1" if cell[r, c] > cell[r, c + 1] else "0" for r in range(rows) for c in range(cols - 1))
    return "%064x" % int(bits, 2)


def main():
    cp = json.loads((REF / "control-points.json").read_text(encoding="utf-8"))
    img_path = REF / cp["image"]
    img = Image.open(img_path)
    w, h = img.size
    if [w, h] != list(cp["image_size"]):
        raise SystemExit(f"The image is {w} x {h}, but control-points.json says {cp['image_size']}")
    out = {
        "island": cp.get("island", "Great Stirrup Cay"),
        "note": "Control points for laying the island sign map over the real map. Coordinates only: the image is never published. Each phone adds its own copy, kept on that phone.",
        "source": f"control-points.json from the builder's place editor, saved {cp.get('saved', '')}",
        "image": {
            "width": w,
            "height": h,
            "fingerprint": {"method": "dhash-17x16-gray-on-white", "value": dhash(img), "max_bits": FINGERPRINT_MAX_BITS},
            "sha256": hashlib.sha256(img_path.read_bytes()).hexdigest(),
        },
        "map_panel": MAP_PANEL,
        "model": cp.get("model", "tps"),
        "projection": {"lat0": LAT0, "lon0": LON0, "m_per_deg_lat": 110574, "m_per_deg_lon_at_equator": 111320, "units": "km"},
        "pairs": [{"id": p["id"], "x": p["x"], "y": p["y"], "lat": p["lat"], "lon": p["lon"]} for p in cp["pairs"]],
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Wrote {OUT}: {len(out['pairs'])} control points, image {w} x {h}, fingerprint {out['image']['fingerprint']['value'][:16]}...")


if __name__ == "__main__":
    main()
