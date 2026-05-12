#!/usr/bin/env python3
"""
build_manifest.py — post-processor for data/manifest.json.

This used to scrape war.gov directly. It can't: war.gov is fronted by
Akamai WAF, which returns HTTP 403 to every AWS / GitHub-hosted IP. The
manifest is now produced by scripts/browser_scrape.js running in the
user's own browser DevTools console while on https://www.war.gov/UFO/
(see README.md for the workflow).

What this script does:
  - HEAD-checks each entry's source_url and records the HTTP status in
    `url_status`, so the front-end can flag broken links.
  - Carries forward any Hebrew translation fields (title_he, agency_he,
    incident_location_he, summary_he) if a previous manifest is supplied
    via --previous-manifest.

Run:
    python scripts/build_manifest.py            # validates URLs in place
    python scripts/build_manifest.py --no-validate
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def log(msg: str) -> None:
    print(f"[build_manifest] {msg}", file=sys.stderr, flush=True)


def head(url: str, timeout: int = 15) -> tuple[int, Optional[int]]:
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            length = r.headers.get("Content-Length")
            return r.status, int(length) if length else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        log(f"  HEAD failed: {url} → {e}")
        return -1, None


def merge_translations(manifest: dict, prev: dict) -> int:
    """Copy *_he fields from prev into manifest for entries with the same id.
    Returns number of entries enriched."""
    prev_by_id = {f.get("id"): f for f in prev.get("files", []) if f.get("id")}
    count = 0
    for f in manifest.get("files", []):
        p = prev_by_id.get(f.get("id"))
        if not p:
            continue
        for key in ("title_he", "agency_he", "incident_location_he", "summary_he"):
            if not f.get(key) and p.get(key):
                f[key] = p[key]
                count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(MANIFEST_PATH),
                    help="path to manifest.json (default: data/manifest.json)")
    ap.add_argument("--previous-manifest", default=None,
                    help="optional previous manifest to merge translations from")
    ap.add_argument("--no-validate", action="store_true",
                    help="skip HEAD validation of source_url")
    args = ap.parse_args()

    path = Path(args.manifest)
    if not path.exists():
        log(f"{path} does not exist")
        return 1

    manifest = json.loads(path.read_text(encoding="utf-8"))
    log(f"loaded {path}: {manifest.get('total_files')} files")

    if args.previous_manifest:
        prev_path = Path(args.previous_manifest)
        if prev_path.exists():
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
            n = merge_translations(manifest, prev)
            log(f"carried {n} Hebrew translation fields over from {prev_path}")

    if not args.no_validate:
        files = manifest.get("files", [])
        log(f"validating {len(files)} URLs")
        bad = 0
        for i, f in enumerate(files, start=1):
            url = f.get("source_url")
            if not url:
                continue
            status, length = head(url)
            f["url_status"] = status
            if length is not None and not f.get("size_bytes"):
                f["size_bytes"] = length
            if status != 200:
                log(f"  ⚠ {url} → {status}")
                bad += 1
            if i % 25 == 0:
                log(f"  validated {i}/{len(files)} ({bad} bad)")
        log(f"validation done — {bad}/{len(files)} bad URLs")

    manifest["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
