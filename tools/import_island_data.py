"""
Copies Great Stirrup Cay's venue data from the private deck-finder-builder repo into the app.

1. places/great-stirrup-cay/places.json, from islands/great-stirrup-cay/great-stirrup-cay.places.json:
   - keeps only venues with status "placed" or "approximate" (skipped and to-do venues are dropped),
   - marks approximate venues with "approximate": true,
   - adds "(name unconfirmed)" after tram stop names, except stops whose confirmed_by in
     venues-to-place.json is exactly "official island map" (named on NCL's island sign),
   - copies each venue's official_area and official_number (the legend on NCL's island sign,
     like "Lagoon 4") from venues-to-place.json when it has them,
   - rejects any place west of longitude -77.9300 (that's CocoCay) and lists it.
2. places/great-stirrup-cay/survey-list.json, from venues-to-place.json: the full venue checklist
   for Survey mode, with only id, name, category, confidence, notes, official_area,
   official_number and not_on_official_map (no source links).

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
UNCONFIRMED = " (name unconfirmed)"
OFFICIAL_MAP = "official island map"


def official(v):
    """The legend fields from venues-to-place.json, only when the venue has both."""
    if v and v.get("official_area") and isinstance(v.get("official_number"), int):
        return {"official_area": v["official_area"], "official_number": v["official_number"]}
    return {}


def write(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main():
    src = json.loads((BUILDER / "great-stirrup-cay.places.json").read_text(encoding="utf-8"))
    vs = json.loads((BUILDER / "venues-to-place.json").read_text(encoding="utf-8"))
    by_id = {v["id"]: v for v in vs["venues"]}
    places, rejected, dropped, confirmed_trams = [], [], {}, []
    for p in src["places"]:
        status = p.get("status")
        if status not in ("placed", "approximate"):
            dropped[status] = dropped.get(status, 0) + 1
            continue
        if not isinstance(p.get("lat"), (int, float)) or not isinstance(p.get("lon"), (int, float)):
            rejected.append(f'{p["name"]} (no position)')
            continue
        if p["lon"] < WEST_LIMIT:
            rejected.append(f'{p["name"]} at {p["lat"]}, {p["lon"]} (west of {WEST_LIMIT}, CocoCay)')
            continue
        v = by_id.get(p["id"])
        name = p["name"].replace(UNCONFIRMED, "")
        if p.get("category") == "tram":
            if v and v.get("confirmed_by") == OFFICIAL_MAP:
                confirmed_trams.append(name)
            else:
                name += UNCONFIRMED
        out = {"id": p["id"], "name": name, "category": p["category"], "lat": p["lat"], "lon": p["lon"], "status": status}
        out.update(official(v))
        if status == "approximate":
            out["approximate"] = True
        places.append(out)

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "places.json", {"island": src.get("island", "Great Stirrup Cay"),
                                "exported": src.get("exported"), "imported": date.today().isoformat(),
                                "places": places})
    print(f"places.json: {len(places)} places kept "
          f"({sum(1 for p in places if p.get('approximate'))} approximate); dropped {dropped or 'none'}")
    print(f"{sum(1 for p in places if 'official_number' in p)} with an official legend number")
    print("Tram stops named on the official map: " + (", ".join(confirmed_trams) or "none"))
    print("Rejected: " + ("; ".join(rejected) if rejected else "none"))

    venues = []
    for v in vs["venues"]:
        out = {k: v[k] for k in ("id", "name", "category", "confidence", "notes") if k in v}
        out.update(official(v))
        if v.get("not_on_official_map"):
            out["not_on_official_map"] = True
        venues.append(out)
    write(OUT / "survey-list.json", {"island": vs.get("island", "Great Stirrup Cay"), "compiled": vs.get("compiled"),
                                     "categories": vs.get("categories", []), "venues": venues})
    print(f"survey-list.json: {len(venues)} venues in {len(vs.get('categories', []))} categories, "
          f"{sum(1 for v in venues if v.get('not_on_official_map'))} not on the official map")
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
