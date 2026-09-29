"""
Copies Great Stirrup Cay's venue data from the private deck-finder-builder repo into the app.

1. places/great-stirrup-cay/places.json, from islands/great-stirrup-cay/great-stirrup-cay.places.json:
   - keeps venues with status "placed", "approximate" or "surveyed" (surveyed ones are exact, and
     keep their accuracy_m, samples and survey_date for the details card),
   - drops removed, merged, skipped and to-do venues from the map,
   - marks approximate venues with "approximate": true,
   - writes the family's name as display_name (the name without builder notes such as
     "(marker 3-b)"), and never the builder's own name,
   - on tram stops, carries stop_number and name_confirmed (since 1.13.0; the app shows "Name to
     confirm on the stop's sign" when name_confirmed is false) instead of the old
     "(name unconfirmed)" suffix,
   - carries area_id (one of the areas in areas.json), area (the builder's plain-language area),
     and official_area and official_number (the legend on NCL's island sign, like "Lagoon 4"),
   - rejects any place west of longitude -77.9300 (that's CocoCay) and lists it.
2. places/great-stirrup-cay/survey-list.json, from venues-to-place.json: the venue checklist for
   Survey mode, with the same rules for names and areas, and without removed or merged venues.
   It also carries a small lookup: "merged" (old id -> the id it was merged into) and "removed"
   (ids taken off the map), so survey entries saved on the phones under those ids still work.
3. places/great-stirrup-cay/areas.json, copied from the builder: the five areas on NCL's island
   sign, each with an id, name, color, optional note, and outline. Since 1.13.0 the outlines cover
   only the built part of the island; open land belongs to no area.
4. places/great-stirrup-cay/tram-routes.json (since 1.13.0), copied from the builder: the two tram
   routes as GeoJSON lines, each with its stops in order and its segments (approximate_path marks
   a segment drawn dashed). Every stop a route names must be an active tram stop in places.json.

Survey data on the phones is keyed by venue id, so renamed venues keep their survey entries.
Never change a venue's id here.

Run from the repo root:  python tools/import_island_data.py
Then run python tools/build_index.py and commit the results.
"""
import json
import sys
from datetime import date
from pathlib import Path

BUILDER = Path(__file__).resolve().parents[2] / "deck-finder-builder" / "islands" / "great-stirrup-cay"
OUT = Path("places/great-stirrup-cay")
WEST_LIMIT = -77.9300
UNCONFIRMED = " (name unconfirmed)"   # the pre-1.13.0 suffix, stripped if a name still has it
TRAM_FIELDS = ("stop_number", "name_confirmed")
ON_MAP = ("placed", "approximate", "surveyed")
OFF_LIST = ("removed", "merged")


def write(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def display_name(v, p=None):
    """The name the family sees: display_name from either file, falling back to the builder name."""
    for x in (p, v):
        if x and isinstance(x.get("display_name"), str) and x["display_name"].strip():
            return x["display_name"].strip()
    return ((p or {}).get("name") or (v or {}).get("name") or "").strip()


def extras(v, p=None):
    """area_id, area and the sign legend, from the places file first, then venues-to-place.json."""
    out = {}
    for k in ("area_id", "area"):
        val = (p or {}).get(k) or (v or {}).get(k)
        if isinstance(val, str) and val:
            out[k] = val
    for k in TRAM_FIELDS:
        for x in (p, v):
            if x and k in x and x[k] is not None:
                out[k] = x[k]
                break
    src = p if p and p.get("official_area") and isinstance(p.get("official_number"), int) else v
    if src and src.get("official_area") and isinstance(src.get("official_number"), int):
        out["official_area"] = src["official_area"]
        out["official_number"] = src["official_number"]
    return out


def main():
    src = json.loads((BUILDER / "great-stirrup-cay.places.json").read_text(encoding="utf-8"))
    vs = json.loads((BUILDER / "venues-to-place.json").read_text(encoding="utf-8"))
    areas = json.loads((BUILDER / "areas.json").read_text(encoding="utf-8"))
    area_ids = {a["id"] for a in areas.get("areas", [])}
    by_id = {v["id"]: v for v in vs["venues"]}
    places, rejected, dropped, problems = [], [], {}, []
    counts = {s: 0 for s in ON_MAP}
    for p in src["places"]:
        status = p.get("status")
        if status not in ON_MAP:
            dropped[status] = dropped.get(status, 0) + 1
            continue
        name = display_name(by_id.get(p["id"]), p)
        if not isinstance(p.get("lat"), (int, float)) or not isinstance(p.get("lon"), (int, float)):
            rejected.append(f'{name} (no position)')
            continue
        if p["lon"] < WEST_LIMIT:
            rejected.append(f'{name} at {p["lat"]}, {p["lon"]} (west of {WEST_LIMIT}, CocoCay)')
            continue
        v = by_id.get(p["id"])
        name = name.replace(UNCONFIRMED, "")
        out = {"id": p["id"], "display_name": name, "category": p["category"], "lat": p["lat"], "lon": p["lon"], "status": status}
        out.update(extras(v, p))
        if out.get("area_id") not in area_ids:
            problems.append(f'{name}: area_id {out.get("area_id")!r} is not in areas.json')
        if status == "approximate":
            out["approximate"] = True
        if status == "surveyed":
            for k in ("accuracy_m", "samples", "survey_date"):
                if p.get(k) is not None:
                    out[k] = p[k]
        counts[status] += 1
        places.append(out)

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "places.json", {"island": src.get("island", "Great Stirrup Cay"),
                                "exported": src.get("exported"), "imported": date.today().isoformat(),
                                "places": places})
    print(f"places.json: {len(places)} places kept ({', '.join(f'{n} {s}' for s, n in counts.items())}); "
          f"dropped {dropped or 'none'}")
    print(f"{sum(1 for p in places if 'official_number' in p)} with an official legend number")
    trams = sorted((p for p in places if p["category"] == "tram"), key=lambda p: p.get("stop_number", 99))
    print("Tram stops: " + ", ".join(p["display_name"] + ("" if p.get("name_confirmed", True) else " (name to confirm)") for p in trams))
    for p in trams:
        if not isinstance(p.get("stop_number"), int):
            problems.append(f'{p["display_name"]}: tram stop has no stop_number')
    print("Rejected: " + ("; ".join(rejected) if rejected else "none"))

    venues, merged, removed = [], {}, []
    for v in vs["venues"]:
        st = v.get("status")
        if st == "merged":
            merged[v["id"]] = v.get("merged_into")
            continue
        if st == "removed":
            removed.append(v["id"])
            continue
        out = {"id": v["id"], "display_name": display_name(v).replace(UNCONFIRMED, "")}
        out.update({k: v[k] for k in ("category", "confidence", "notes") if k in v})
        out.update(extras(v))
        if out.get("area_id") not in area_ids:
            problems.append(f'{out["display_name"]} (survey list): area_id {out.get("area_id")!r} is not in areas.json')
        if v.get("not_on_official_map"):
            out["not_on_official_map"] = True
        venues.append(out)
    listed = {v["id"] for v in venues}
    for old, new in merged.items():
        if new not in listed:
            problems.append(f"{old} is merged into {new!r}, which is not in the survey list")
    write(OUT / "survey-list.json", {"island": vs.get("island", "Great Stirrup Cay"), "compiled": vs.get("compiled"),
                                     "categories": vs.get("categories", []), "merged": merged, "removed": removed,
                                     "venues": venues})
    print(f"survey-list.json: {len(venues)} venues in {len(vs.get('categories', []))} categories, "
          f"{sum(1 for v in venues if v.get('not_on_official_map'))} not on the official map; "
          f"left out {len(merged)} merged ({', '.join(f'{a} -> {b}' for a, b in merged.items()) or 'none'}) "
          f"and {len(removed)} removed ({', '.join(removed) or 'none'})")

    write(OUT / "areas.json", areas)
    print(f"areas.json: {len(areas.get('areas', []))} areas ({', '.join(a['name'] for a in areas.get('areas', []))})")

    routes = json.loads((BUILDER / "tram-routes.json").read_text(encoding="utf-8"))
    stops = {p["id"]: p for p in places if p["category"] == "tram"}
    for f in routes.get("features", []):
        pr = f.get("properties", {})
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            problems.append(f'tram route {pr.get("name")!r} has no line')
        for s in pr.get("stops", []):
            if s.get("id") not in stops:
                problems.append(f'tram route {pr.get("name")!r} names stop {s.get("id")!r}, which is not an active tram stop')
            elif stops[s["id"]].get("stop_number") != s.get("stop_number"):
                problems.append(f'tram route {pr.get("name")!r}: {s["id"]} is stop {s.get("stop_number")} there but '
                                f'{stops[s["id"]].get("stop_number")} in places.json')
        print(f'tram-routes.json: Route {pr.get("route_number")} {pr.get("name")}: stops '
              f'{", ".join(str(s.get("stop_number")) for s in pr.get("stops", []))}, {len(coords)} points, '
              f'{sum(1 for g in pr.get("segments", []) if g.get("approximate_path"))} approximate segment(s)')
    write(OUT / "tram-routes.json", routes)
    if problems:
        print("PROBLEMS:\n  " + "\n  ".join(problems))
    return 1 if rejected or problems else 0


if __name__ == "__main__":
    sys.exit(main())
