#!/usr/bin/env python3
"""
fetch_dvids.py — harvest DVIDS video metadata into data/dvids/uap_videos.json.

The war.gov UAP videos are not self-hosted; each one is a DVIDS asset
(Defense Visual Information Distribution Service) published by the
All-domain Anomaly Resolution Office and tagged with the keyword
"UAPVIDEOS". data/dvids/uap_videos.json holds, per DVIDS id, the full asset
record — including the `files` array of MP4 renditions that the site plays.
scripts/merge_dvids_videos.py then folds those playable URLs into the
manifest.

This must run on YOUR machine: api.dvidshub.net is not reachable from the
cloud build environment, and the API needs a key.

Setup:
  1. Get a free API key: https://api.dvidshub.net/ (register, request a key).
  2. export DVIDS_API_KEY=...        (or pass --api-key)

Run:
  python scripts/fetch_dvids.py                 # search keyword UAPVIDEOS, merge all
  python scripts/fetch_dvids.py --query UAPVIDEOS --dry-run

After it writes the file, sanity-check that a record has a non-empty
"files" list (that's what playback needs), then run:
  python scripts/merge_dvids_videos.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dvids" / "uap_videos.json"
SEARCH_URL = "https://api.dvidshub.net/search"
ASSET_URL = "https://api.dvidshub.net/asset"


def log(msg: str) -> None:
    print(f"[fetch_dvids] {msg}", file=sys.stderr, flush=True)


def get_json(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(full, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 — surface and back off
            wait = 2 ** (attempt + 1)
            log(f"  request failed ({e}); retry in {wait}s")
            time.sleep(wait)
    raise SystemExit(f"giving up on {url}")


def search_ids(api_key: str, query: str, unit_id: str | None) -> list[str]:
    """Page through search results, returning every video asset id."""
    ids: list[str] = []
    page = 1
    while True:
        params = {
            "q": query,
            "type": "video",
            "max_results": 50,
            "page": page,
            "api_key": api_key,
        }
        if unit_id:
            params["unit_id"] = unit_id
        data = get_json(SEARCH_URL, params)
        results = data.get("results")
        if results is None:
            # Unexpected shape — show what we got so we can adjust the params.
            log("!! search response had no 'results' key. Top-level keys: "
                f"{list(data.keys())}")
            log(f"!! raw (first 500 chars): {json.dumps(data, ensure_ascii=False)[:500]}")
            log("!! send this output back and I'll fix the query/params.")
            break
        if not results:
            if page == 1:
                log(f"!! search for {query!r} returned 0 results. Try a different "
                    "--query, or --unit-id 8597 (the AARO unit). Send me the output.")
            break
        for r in results:
            rid = r.get("id")
            if rid:
                ids.append(rid)
        log(f"  page {page}: {len(results)} results (total {len(ids)})")
        # Stop when fewer than a full page came back.
        if len(results) < 50:
            break
        page += 1
        time.sleep(0.3)
    return ids


def fetch_asset(api_key: str, asset_id: str) -> dict | None:
    data = get_json(ASSET_URL, {"id": asset_id, "api_key": api_key})
    res = data.get("results")
    if isinstance(res, list):
        return res[0] if res else None
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api-key", default=os.environ.get("DVIDS_API_KEY"),
                    help="DVIDS API key (or set env DVIDS_API_KEY)")
    ap.add_argument("--query", default="UAPVIDEOS", help="search keyword (default: UAPVIDEOS)")
    ap.add_argument("--unit-id", default=None,
                    help="optional DVIDS unit_id filter (the AARO unit is 8597)")
    ap.add_argument("--dry-run", action="store_true", help="fetch and report; don't write")
    args = ap.parse_args()

    if not args.api_key:
        raise SystemExit("no API key — set DVIDS_API_KEY or pass --api-key "
                         "(get one free at https://api.dvidshub.net/)")

    ids = search_ids(args.api_key, args.query, args.unit_id)
    log(f"found {len(ids)} video assets for query {args.query!r}")

    existing = {}
    if OUT.exists():
        existing = json.loads(OUT.read_text(encoding="utf-8"))
        log(f"existing records: {len(existing)}")

    fetched = 0
    for aid in ids:
        asset = fetch_asset(args.api_key, aid)
        if not asset:
            continue
        key = str(asset.get("id", aid)).replace("video:", "")
        existing[key] = asset
        fetched += 1
        if fetched % 10 == 0:
            log(f"  fetched {fetched}/{len(ids)}")
        time.sleep(0.2)

    log(f"fetched {fetched} assets; total in file: {len(existing)}")
    n_with_files = sum(1 for r in existing.values() if r and r.get("files"))
    log(f"records with a non-empty 'files' (playable) list: {n_with_files}/{len(existing)}")

    if args.dry_run:
        log("dry-run: not writing")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
