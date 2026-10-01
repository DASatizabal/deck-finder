"""
Draws a before and after preview of part of the island map, and checks every place against the shoreline.

  python tools/preview_island.py                   # the Lagoon, before = basemap.json in the last commit
  python tools/preview_island.py --before old.json # compare with another basemap file
  python tools/preview_island.py --box -77.9150 25.8215 -77.9070 25.8285 --out tools/previews/x.png

The image goes to tools/previews/ (ignored by git, never published). It draws only the basemap
(OpenStreetMap shapes) and the places, never the island sign image.

The check lists every place that sits on the water (outside land, beach and pier shapes) in the new
basemap, and every place that changed sides between the two basemaps. Places that belong on the water
(bridges, docks and piers, overwater swings, snorkel spots, pools and lagoons) are marked as expected.
Ponds and pools drawn on the land count as water.

Needs Pillow and shapely. Run from the repo root.
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

ISLAND = Path("places/great-stirrup-cay")
LAGOON = (-77.9150, 25.8215, -77.9070, 25.8285)
# Places that belong over the water: the bridge, docks and piers, overwater swings, the snorkel garden.
ON_WATER_OK = ("bridge", "tender", "pier", "overwater", "over-the-water", "underwater", "snorkel", "water-tour")

COLORS = {"land": (228, 238, 211), "beach": (246, 231, 185), "water": (143, 208, 234), "pool": (143, 208, 234),
          "building": (207, 198, 182), "pier": (154, 165, 171)}
SEA = (191, 227, 240)


def ground(base):
    """Land, beach and pier polygons (with their holes), minus ponds and pools, as one shapely shape in lon/lat."""
    polys, wet = [], []
    for f in base["features"]:
        g, k = f["geometry"], f["properties"].get("kind")
        if g["type"] != "Polygon":
            continue
        shape = Polygon(g["coordinates"][0], g["coordinates"][1:]).buffer(0)
        if k in ("land", "beach", "pier"):
            polys.append(shape)
        elif k in ("water", "pool"):
            wet.append(shape)
    return unary_union(polys).difference(unary_union(wet))


def belongs_on_water(p):
    return any(k in p["id"] for k in ON_WATER_OK) or p.get("category") == "pool" or (p.get("display_name") or "").endswith("Lagoon")


def draw(base, places, box, scale, title):
    w_, s_, e_, n_ = box
    kx = 111320 * math.cos(math.radians((s_ + n_) / 2)) * scale
    ky = 110574 * scale
    w, h = int((e_ - w_) * kx), int((n_ - s_) * ky)
    px = lambda lon, lat: ((lon - w_) * kx, (n_ - lat) * ky)
    im = Image.new("RGB", (w, h + 34), SEA)
    d = ImageDraw.Draw(im)
    order = ["land", "beach", "water", "pool", "pier", "building"]
    feats = sorted(base["features"], key=lambda f: order.index(f["properties"]["kind"]) if f["properties"]["kind"] in order else 99)
    for f in feats:
        k, g = f["properties"]["kind"], f["geometry"]
        if g["type"] == "Polygon" and k in COLORS:
            for i, r in enumerate(g["coordinates"]):
                pts = [px(*c) for c in r]
                d.polygon(pts, fill=COLORS[k] if i == 0 else SEA, outline=(120, 150, 100) if k == "land" else None)
        elif g["type"] == "LineString":
            col = {"road": (255, 255, 255), "path": (169, 133, 90), "pier": (154, 165, 171)}.get(k, (120, 120, 120))
            d.line([px(*c) for c in g["coordinates"]], fill=col, width=3 if k != "path" else 2)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
        big = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = big = ImageFont.load_default()
    gr = ground(base)
    for p in places:
        x, y = px(p["lon"], p["lat"])
        if not (0 <= x < w and 0 <= y < h):
            continue
        dry = gr.contains(Point(p["lon"], p["lat"]))
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(200, 30, 30) if dry else (20, 60, 200), outline=(255, 255, 255), width=2)
        d.text((x + 8, y - 8), p.get("display_name") or p["name"], fill=(0, 0, 0), font=font, stroke_width=2, stroke_fill=(255, 255, 255))
    d.rectangle((0, h, w, h + 34), fill=(30, 40, 50))
    d.text((10, h + 7), title + "   (red dot: on land, blue dot: on water)", fill=(255, 255, 255), font=big)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", help="older basemap file (default: basemap.json in the last commit)")
    ap.add_argument("--box", nargs=4, type=float, default=LAGOON, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    ap.add_argument("--scale", type=float, default=1.5, help="pixels per meter")
    ap.add_argument("--out", default="tools/previews/lagoon-before-after.png")
    a = ap.parse_args()

    after = json.loads((ISLAND / "basemap.json").read_text(encoding="utf-8"))
    if a.before:
        before = json.loads(Path(a.before).read_text(encoding="utf-8"))
    else:
        before = json.loads(subprocess.run(["git", "show", f"HEAD:{ISLAND.as_posix()}/basemap.json"],
                                           capture_output=True, check=True).stdout.decode("utf-8"))
    places = json.loads((ISLAND / "places.json").read_text(encoding="utf-8"))["places"]

    im1 = draw(before, places, a.box, a.scale, "Before")
    im2 = draw(after, places, a.box, a.scale, "After")
    out = Image.new("RGB", (im1.width + im2.width + 12, im1.height), (255, 255, 255))
    out.paste(im1, (0, 0))
    out.paste(im2, (im1.width + 12, 0))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.save(a.out)
    print(f"Wrote {a.out} ({out.width} x {out.height})")

    g0, g1 = ground(before), ground(after)
    print("\nPlaces on the water in the new basemap:")
    for p in places:
        if not g1.contains(Point(p["lon"], p["lat"])):
            ok = belongs_on_water(p)
            meters = g1.boundary.distance(Point(p["lon"], p["lat"])) * 105000   # degrees to meters, roughly
            print(f"  {'expected' if ok else 'CHECK   '}  {p['display_name']} ({p['id']}), {meters:.0f} m from the shore")
    print("\nPlaces that changed sides:")
    changed = 0
    for p in places:
        pt = Point(p["lon"], p["lat"])
        a0, a1 = g0.contains(pt), g1.contains(pt)
        if a0 != a1:
            changed += 1
            print(f"  {p['display_name']}: {'land' if a0 else 'water'} -> {'land' if a1 else 'water'}")
    if not changed:
        print("  none")


if __name__ == "__main__":
    main()
