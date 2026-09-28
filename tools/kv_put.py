"""
Write one itinerary to the Deck Finder Worker's shared ITINERARIES KV namespace, so every
phone gets it from the Worker's /itinerary route without spending a CruiseFeed result.

Usage:
    python tools/kv_put.py tools/itineraries/ncl-getaway-2026-10-02.json
    python tools/kv_put.py <file> --dry-run        (check the file and show the key; contacts nothing)
    python tools/kv_put.py <file> --namespace <KV namespace name>   (default: deck-finder-itineraries)
    python tools/kv_put.py <file> --delete         (remove the entry for that file's sailing)

The file holds only public sailing data, in the same shape the Worker saves:
cruise_line, ship, departure_date, return_date, nights, title, source, and stops (each with
seq, day_number, date, port, arrive, depart as "HH:MM" local port time or null, is_embark,
is_disembark, is_sea_day, overnight). saved_at is set to today when it is written.
An existing entry for the same sailing is replaced.

Reads the Cloudflare API token (Workers KV Storage: Edit only) and the account ID from
D:\\AI-VAULT\\secrets\\cloudflare_kv_token.txt and D:\\AI-VAULT\\secrets\\cloudflare_account_id.txt.
Never prints either of them.
"""
import argparse
import datetime
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SECRETS = Path(r"D:\AI-VAULT\secrets")
API = "https://api.cloudflare.com/client/v4"
TOP_KEYS = ["cruise_line", "ship", "departure_date", "return_date", "nights", "title", "source", "saved_at", "stops"]
STOP_KEYS = ["seq", "day_number", "date", "port", "arrive", "depart", "is_embark", "is_disembark", "is_sea_day", "overnight"]
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
NAME = re.compile(r"^[\w .'&-]{1,80}$")  # the same names the Worker accepts


def die(msg):
    print("FAIL:", msg)
    sys.exit(1)


def check(it):
    """Keep only public sailing fields, in a fixed order, and fail on anything odd."""
    extra = set(it) - set(TOP_KEYS)
    if extra:
        die(f"unexpected fields {sorted(extra)}. Only public sailing data may go to KV: {', '.join(TOP_KEYS)}.")
    for k in ("cruise_line", "ship", "departure_date", "title", "source"):
        if not isinstance(it.get(k), str) or not it[k].strip():
            die(f'"{k}" is required')
    for k in ("cruise_line", "ship"):
        if not NAME.fullmatch(it[k]):
            die(f'"{k}" has characters the Worker would refuse: {it[k]!r}')
    for k in ("departure_date", "return_date"):
        if it.get(k) is not None and not DATE.fullmatch(it[k]):
            die(f'"{k}" must look like 2026-10-02')
    stops = it.get("stops")
    if not isinstance(stops, list) or not stops:
        die('"stops" must be a list with at least one stop')
    clean_stops = []
    for i, s in enumerate(stops, 1):
        extra = set(s) - set(STOP_KEYS)
        if extra:
            die(f"stop {i} has unexpected fields {sorted(extra)}")
        if not s.get("date") or not DATE.fullmatch(s["date"]):
            die(f"stop {i} needs a date like 2026-10-02")
        if not s.get("is_sea_day") and not s.get("port"):
            die(f"stop {i} needs a port, or is_sea_day true")
        for k in ("arrive", "depart"):
            if s.get(k) is not None and not TIME.fullmatch(s[k]):
                die(f'stop {i} "{k}" must be "HH:MM" (24-hour, local port time) or null, found {s[k]!r}')
        clean_stops.append({
            "seq": s.get("seq", i), "day_number": s.get("day_number"), "date": s["date"], "port": s.get("port"),
            "arrive": s.get("arrive"), "depart": s.get("depart"),
            "is_embark": bool(s.get("is_embark")), "is_disembark": bool(s.get("is_disembark")),
            "is_sea_day": bool(s.get("is_sea_day")), "overnight": bool(s.get("overnight")),
        })
    out = {k: it.get(k) for k in TOP_KEYS if k != "stops"}
    out["saved_at"] = datetime.date.today().isoformat()
    out["stops"] = clean_stops
    return out


def read_secret(name, pattern, what):
    path = SECRETS / name
    if not path.is_file():
        die(f"{path} is missing. Save your {what} there.")
    value = path.read_text(encoding="utf-8-sig").strip()
    if not re.fullmatch(pattern, value):
        die(f"{path} doesn't look like a {what}. Check the file (its contents are not shown).")
    return value


def call(method, url, token, body=None):
    req = urllib.request.Request(url, data=body, method=method, headers={"Authorization": "Bearer " + token})
    if body is not None:
        req.add_header("Content-Type", "text/plain; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def cf_errors(raw):
    try:
        return "; ".join(f"{e.get('code')}: {e.get('message')}" for e in json.loads(raw).get("errors", []))
    except Exception:
        return raw[:200].decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser(description="Write one itinerary to the Deck Finder ITINERARIES KV namespace.")
    ap.add_argument("file")
    ap.add_argument("--namespace", default="deck-finder-itineraries", help="KV namespace name (title)")
    ap.add_argument("--dry-run", action="store_true", help="check the file and show the key; contacts nothing")
    ap.add_argument("--delete", action="store_true", help="remove the entry for this file's sailing instead of writing it")
    args = ap.parse_args()

    it = check(json.loads(Path(args.file).read_text(encoding="utf-8")))
    key = f"itin:{it['cruise_line']}:{it['ship']}:{it['departure_date']}"
    value = json.dumps(it, ensure_ascii=False, separators=(",", ":"))
    print("Key:", key)
    for s in it["stops"]:
        times = ", ".join(x for x in (s["arrive"] and "arrive " + s["arrive"], s["depart"] and "depart " + s["depart"]) if x)
        print(f"  {s['date']}  {'At sea' if s['is_sea_day'] else s['port']}  {times}")
    if args.dry_run:
        print("Dry run: nothing was sent.")
        return

    token = read_secret("cloudflare_kv_token.txt", r"[A-Za-z0-9_\-]{20,}", "Cloudflare API token")
    account = read_secret("cloudflare_account_id.txt", r"[0-9a-f]{32}", "Cloudflare account ID")
    base = f"{API}/accounts/{account}/storage/kv/namespaces"

    # Find the namespace by its name.
    ns_id, page = None, 1
    while ns_id is None:
        status, raw = call("GET", f"{base}?per_page=100&page={page}", token)
        if status != 200:
            die(f"couldn't list KV namespaces (HTTP {status}: {cf_errors(raw)}). Check the token has Workers KV Storage: Edit on this account.")
        data = json.loads(raw)
        ns_id = next((n["id"] for n in data["result"] if n["title"] == args.namespace), None)
        info = data.get("result_info") or {}
        if ns_id is None and page >= (info.get("total_pages") or 1):
            names = "an empty list" if page == 1 and not data["result"] else "other names only"
            die(f'no KV namespace named "{args.namespace}" (found {names}). Create it, or pass --namespace.')
        page += 1

    url = f"{base}/{ns_id}/values/{urllib.parse.quote(key, safe='')}"
    status, raw = call("GET", url, token)
    if status == 200:
        try:
            old = json.loads(raw)
            print(f"{'Found' if args.delete else 'Replacing'} the existing entry (source: {old.get('source')}, saved {old.get('saved_at')}).")
        except Exception:
            print(f"{'Found' if args.delete else 'Replacing'} an existing entry that wasn't valid JSON.")
    elif status == 404:
        print("No entry for this sailing yet.")
    else:
        die(f"couldn't read the current entry (HTTP {status}: {cf_errors(raw)})")

    if args.delete:
        if status == 404:
            return
        status, raw = call("DELETE", url, token)
        if status != 200:
            die(f"couldn't delete the entry (HTTP {status}: {cf_errors(raw)})")
        print(f'Deleted from KV namespace "{args.namespace}".')
        return

    status, raw = call("PUT", url, token, value.encode("utf-8"))
    if status != 200:
        die(f"couldn't write the entry (HTTP {status}: {cf_errors(raw)})")
    status, raw = call("GET", url, token)
    if status != 200 or json.loads(raw) != it:
        die(f"wrote the entry, but reading it back didn't match (HTTP {status}).")
    print(f'Saved and read back from KV namespace "{args.namespace}". No expiry.')


if __name__ == "__main__":
    main()
