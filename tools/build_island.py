"""
Builds places/great-stirrup-cay/basemap.json, the island map the app draws itself (no map tiles).

It downloads Great Stirrup Cay from the OpenStreetMap Overpass API: the coastline and land,
beaches, water and pools, paths and roads, piers, and buildings.

Sea water inside the coastline (since 1.15.0): OpenStreetMap draws the island's coastline straight
across the two entrances of the harbor by the Lagoon (the basin the Panoramic Bridge crosses, where
Tweed's Tenders docks), so the coastline alone paints the harbor as land. The harbor itself is a
separate "waterway=dock" + "harbour=yes" multipolygon (relation 9102656). Docks, bays, and water
tagged water=harbour or water=dock are downloaded and cut out of the land and the beaches, so the
sea shows through. The cut needs shapely (pip install shapely).

The bounding box stops at longitude -77.9300 on the west, so nothing from Little Stirrup Cay (Royal Caribbean's CocoCay)
is included, and anything that still reaches west of that line is dropped. Shapes are simplified
(Douglas-Peucker, in meters) and coordinates rounded to 6 decimals (about 10 cm).

The data is (c) OpenStreetMap contributors, under the Open Database License (ODbL). The
attribution is stored in the file, and the app shows it on the map.

Run from the repo root:  python tools/build_island.py
Then run python tools/build_index.py and commit both files.
"""
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

OUT = Path("places/great-stirrup-cay/basemap.json")
SOUTH, WEST, NORTH, EAST = 25.814, -77.9300, 25.832, -77.890
WEST_LIMIT = -77.9300      # CocoCay (Little Stirrup Cay) lies west of this line
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
ATTRIBUTION = "© OpenStreetMap contributors"

BB = f"({SOUTH},{WEST},{NORTH},{EAST})"
QUERY = f"""
[out:json][timeout:90];
(
  way["natural"="coastline"]{BB};
  way["place"~"^(island|islet)$"]{BB};
  relation["place"~"^(island|islet)$"]{BB};
  way["natural"~"^(beach|sand)$"]{BB};
  relation["natural"~"^(beach|sand)$"]{BB};
  way["natural"="water"]{BB};
  relation["natural"="water"]{BB};
  way["waterway"="dock"]{BB};
  relation["waterway"="dock"]{BB};
  way["natural"="bay"]{BB};
  relation["natural"="bay"]{BB};
  way["leisure"="swimming_pool"]{BB};
  way["highway"]{BB};
  way["building"]{BB};
  way["man_made"~"^(pier|breakwater|groyne)$"]{BB};
);
out geom;
"""

# Simplification tolerance in meters for each kind of shape.
TOLERANCE = {"land": 1.5, "beach": 1.0, "water": 0.8, "pool": 0.4, "building": 0.5, "pier": 0.5, "road": 1.0, "path": 1.0}
PATH_TYPES = {"footway", "path", "pedestrian", "steps", "cycleway", "track", "bridleway", "corridor"}


def fetch():
    last = None
    for url in ENDPOINTS:
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": QUERY}).encode(),
                                         headers={"User-Agent": "DeckFinder-build_island/1.0 (family app)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r), url
        except Exception as e:     # try the next server
            last = e
            print(f"{url} failed: {e}", file=sys.stderr)
            time.sleep(2)
    raise SystemExit(f"Overpass could not be reached: {last}")


# ---------- geometry helpers (local meters around the island) ----------
LAT0 = (SOUTH + NORTH) / 2
MX = 111320 * math.cos(math.radians(LAT0))
MY = 110540


def to_m(p):
    return ((p[0] - WEST) * MX, (p[1] - SOUTH) * MY)


def seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def simplify(coords, tol):
    """Douglas-Peucker on [lon, lat] points, measuring in meters. Keeps the first and last point."""
    if len(coords) < 3:
        return coords
    pts = [to_m(c) for c in coords]
    keep = [False] * len(coords)
    keep[0] = keep[-1] = True
    stack = [(0, len(coords) - 1)]
    while stack:
        i, j = stack.pop()
        best, idx = 0, None
        for k in range(i + 1, j):
            d = seg_dist(pts[k], pts[i], pts[j])
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [c for c, k in zip(coords, keep) if k]


def rnd(coords):
    return [[round(x, 6), round(y, 6)] for x, y in coords]


def ring_area(coords):
    pts = [to_m(c) for c in coords]
    return sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1] for i in range(len(pts) - 1)) / 2


def centroid_lon(coords):
    return sum(c[0] for c in coords) / len(coords)


def join_lines(lines):
    """Join open ways that share end points into longer lines and closed rings."""
    lines = [list(l) for l in lines if len(l) >= 2]
    rings, out = [], []
    while lines:
        cur = lines.pop()
        changed = True
        while changed and cur[0] != cur[-1]:
            changed = False
            for i, l in enumerate(lines):
                if l[0] == cur[-1]:
                    cur += l[1:]
                elif l[-1] == cur[-1]:
                    cur += l[-2::-1]
                elif l[-1] == cur[0]:
                    cur = l[:-1] + cur
                elif l[0] == cur[0]:
                    cur = l[:0:-1] + cur
                else:
                    continue
                lines.pop(i)
                changed = True
                break
        (rings if cur[0] == cur[-1] and len(cur) >= 4 else out).append(cur)
    return rings, out


def geom_of(way):
    return [[p["lon"], p["lat"]] for p in way.get("geometry", []) if p]


def is_sea(tags):
    """Sea water that OpenStreetMap may leave inside the coastline: docks, harbors and bays."""
    return (tags.get("waterway") == "dock" or tags.get("natural") == "bay"
            or (tags.get("natural") == "water" and tags.get("water") in ("harbour", "dock", "bay")))


def classify(tags):
    if is_sea(tags):
        return "sea"
    if tags.get("building"):
        return "building"
    if tags.get("leisure") == "swimming_pool":
        return "pool"
    if tags.get("natural") in ("beach", "sand"):
        return "beach"
    if tags.get("natural") == "water":
        return "water"
    if tags.get("man_made") in ("pier", "breakwater", "groyne"):
        return "pier"
    hw = tags.get("highway")
    if hw:
        return "path" if hw in PATH_TYPES else "road"
    return None


def main():
    data, endpoint = fetch()
    elements = data.get("elements", [])
    features, dropped_west = [], 0
    land_lines = []
    sea = []          # (outer rings, inner rings, osm id) of sea water to cut out of the land

    def west(coords):
        return any(c[0] < WEST_LIMIT for c in coords)

    def add(kind, coords, closed, name=None):
        nonlocal dropped_west
        if len(coords) < 2:
            return
        if west(coords):
            dropped_west += 1
            return
        coords = rnd(simplify(coords, TOLERANCE[kind]))
        if closed:
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            if len(coords) < 4:
                return
            geom = {"type": "Polygon", "coordinates": [coords]}
        else:
            geom = {"type": "LineString", "coordinates": coords}
        props = {"kind": kind}
        if name:
            props["name"] = name
        features.append({"type": "Feature", "properties": props, "geometry": geom})

    for el in elements:
        tags = el.get("tags", {})
        if el["type"] == "way":
            coords = geom_of(el)
            if tags.get("natural") == "coastline" or tags.get("place") in ("island", "islet"):
                land_lines.append(coords)
                continue
            kind = classify(tags)
            if not kind:
                continue
            if kind == "sea":
                if len(coords) >= 4 and coords[0] == coords[-1] and not west(coords):
                    sea.append(([coords], [], f"way {el['id']}"))
                continue
            closed = len(coords) >= 4 and coords[0] == coords[-1] and kind not in ("road", "path")
            if kind == "pier" and not closed:
                add(kind, coords, False)
            else:
                add(kind, coords, closed, tags.get("name"))
        elif el["type"] == "relation":
            outers = [geom_of(m) for m in el.get("members", []) if m.get("type") == "way" and m.get("role") in ("outer", "")]
            if tags.get("place") in ("island", "islet"):
                land_lines += outers
                continue
            kind = classify(tags)
            if kind == "sea":
                inners = [geom_of(m) for m in el.get("members", []) if m.get("type") == "way" and m.get("role") == "inner"]
                outer_rings, _ = join_lines(outers)
                inner_rings, _ = join_lines(inners)
                outer_rings = [r for r in outer_rings if not west(r)]
                if outer_rings:
                    sea.append((outer_rings, inner_rings, f"relation {el['id']}"))
                continue
            if kind in ("beach", "water"):
                rings, _ = join_lines(outers)
                for r in rings:
                    add(kind, r, True, tags.get("name"))

    # Land: join the coastline pieces into closed rings, keep only rings east of the CocoCay line.
    uniq = []
    for l in land_lines:
        if l and l not in uniq and l[::-1] not in uniq:
            uniq.append(l)
    rings, open_lines = join_lines(uniq)
    land = []
    for r in rings:
        if centroid_lon(r) < WEST_LIMIT or west(r):
            dropped_west += 1
            continue
        if ring_area(r) < 0:           # counter-clockwise outer rings, like GeoJSON asks
            r = r[::-1]
        land.append({"type": "Feature", "properties": {"kind": "land"},
                     "geometry": {"type": "Polygon", "coordinates": [rnd(simplify(r, TOLERANCE["land"]))]}})
    if not land:
        raise SystemExit("No closed coastline found for the island. Nothing was written.")
    # The island's outline before any cut, for island_bounds (the whole island, harbor or not).
    main_ring = max((f["geometry"]["coordinates"][0] for f in land), key=lambda r: abs(ring_area(r)))
    if sea:
        land, features = cut_sea(land, features, sea)
    if open_lines:
        print(f"note: {len(open_lines)} coastline piece(s) did not close into a ring and were left out", file=sys.stderr)

    # Big islands first so smaller shapes draw on top.
    land.sort(key=lambda f: -abs(ring_area(f["geometry"]["coordinates"][0])))
    order = ["beach", "water", "pool", "pier", "building", "road", "path"]
    features.sort(key=lambda f: order.index(f["properties"]["kind"]))
    features = land + features

    lons = [c[0] for c in main_ring]
    lats = [c[1] for c in main_ring]
    out = {
        "type": "FeatureCollection",
        "name": "Great Stirrup Cay",
        "attribution": ATTRIBUTION,
        "license": "Open Database License (ODbL), https://www.openstreetmap.org/copyright",
        "source": endpoint,
        "generated": date.today().isoformat(),
        "island_bounds": {"min_lat": min(lats), "min_lon": min(lons), "max_lat": max(lats), "max_lon": max(lons)},
        "sea_cut": {"note": "Sea water inside OpenStreetMap's coastline (docks, harbors, bays), cut out of the land and beaches.",
                    "from": [x[2] for x in sea]},
        "features": features,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    counts = {}
    for ft in features:
        counts[ft["properties"]["kind"]] = counts.get(ft["properties"]["kind"], 0) + 1
    print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes) from {endpoint}")
    print("  " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    print(f"  island bounds: {out['island_bounds']}")
    if dropped_west:
        print(f"  dropped {dropped_west} shape(s) reaching west of {WEST_LIMIT} (CocoCay side)")


def from_m(x, y):
    return (WEST + x / MX, SOUTH + y / MY)


def cut_sea(land, features, sea):
    """Cut the sea polygons out of the land and beach polygons (shapely, in meters)."""
    try:
        from shapely.geometry import Polygon, MultiPolygon
        from shapely.geometry.polygon import orient
        from shapely.ops import unary_union
    except ImportError:
        raise SystemExit("Cutting the harbor out of the land needs shapely: pip install shapely")

    def poly_m(outer, inners=()):
        return Polygon([to_m(c) for c in outer], [[to_m(c) for c in r] for r in inners]).buffer(0)

    water = unary_union([poly_m(o, [r for r in inners if poly_m(o).contains(poly_m(r))]) for outers, inners, _ in sea for o in outers])

    def pieces(g):
        if g.is_empty:
            return []
        return [g] if g.geom_type == "Polygon" else [x for x in getattr(g, "geoms", []) if x.geom_type == "Polygon"]

    def back(p, tol):
        p = orient(p.simplify(tol, preserve_topology=True), 1.0)    # outer ring counter-clockwise, holes clockwise
        rings = [p.exterior.coords] + [r.coords for r in p.interiors]
        return [rnd([list(from_m(x, y)) for x, y in r]) for r in rings]

    def cut(feats, kind, min_area):
        out = []
        for f in feats:
            rings = f["geometry"]["coordinates"]
            g = poly_m(rings[0], rings[1:])
            if not g.intersects(water):
                out.append(f)
                continue
            for p in pieces(g.difference(water)):
                if p.area < min_area:
                    continue
                out.append({"type": "Feature", "properties": dict(f["properties"]),
                            "geometry": {"type": "Polygon", "coordinates": back(p, TOLERANCE[kind])}})
        return out

    before = sum(poly_m(f["geometry"]["coordinates"][0]).area for f in land)
    land = cut(land, "land", 4)
    after = sum(poly_m(r["geometry"]["coordinates"][0], r["geometry"]["coordinates"][1:]).area for r in land)
    beaches = cut([f for f in features if f["properties"]["kind"] == "beach"], "beach", 2)
    features = beaches + [f for f in features if f["properties"]["kind"] != "beach"]
    print(f"  cut {len(sea)} sea shape(s) out of the land ({', '.join(x[2] for x in sea)}): "
          f"{(before - after) / 10000:.2f} hectares of water that the coastline had painted as land")
    return land, features


if __name__ == "__main__":
    main()
