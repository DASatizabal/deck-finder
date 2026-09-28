"""
Copies Great Stirrup Cay's venue data from the private deck-finder-builder repo into the app.

1. places/great-stirrup-cay/places.json, from islands/great-stirrup-cay/great-stirrup-cay.places.json:
   - keeps only venues with status "placed" or "approximate" (skipped and to-do venues are dropped),
   - marks approximate venues with "approximate": true,
   - adds "(name unconfirmed)" after tram stop names, since NCL doesn't publish stop names,
   - rejects any place west of longitude -77.9300 (that's CocoCay) and lists it.
2. places/great-stirrup-cay/survey-list.json, from venues-to-place.json: the full venue checklist
   for Survey mode, with only id, name, category, confidence and notes (no source links).

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


def write(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main():
    src = json.loads((BUILDER / "great-stirrup-cay.places.json").read_text(encoding="utf-8"))
    places, rejected, dropped = [], [], {}
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
        name = p["name"]
        if p.get("category") == "tram" and UNCONFIRMED not in name:
            name += UNCONFIRMED
        out = {"id": p["id"], "name": name, "category": p["category"], "lat": p["lat"], "lon": p["lon"], "status": status}
        if status == "approximate":
            out["approximate"] = True
        places.append(out)

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "places.json", {"island": src.get("island", "Great Stirrup Cay"),
                                "exported": src.get("exported"), "imported": date.today().isoformat(),
                                "places": places})
    print(f"places.json: {len(places)} places kept "
          f"({sum(1 for p in places if p.get('approximate'))} approximate); dropped {dropped or 'none'}")
    print("Rejected: " + ("; ".join(rejected) if rejected else "none"))

    vs = json.loads((BUILDER / "venues-to-place.json").read_text(encoding="utf-8"))
    venues = [{k: v[k] for k in ("id", "name", "category", "confidence", "notes") if k in v} for v in vs["venues"]]
    write(OUT / "survey-list.json", {"island": vs.get("island", "Great Stirrup Cay"), "compiled": vs.get("compiled"),
                                     "categories": vs.get("categories", []), "venues": venues})
    print(f"survey-list.json: {len(venues)} venues in {len(vs.get('categories', []))} categories")
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
