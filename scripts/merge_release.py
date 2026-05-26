#!/usr/bin/env python3
"""
merge_release.py — fold a fresh browser scrape into data/manifest.json,
adding only the records that are new for a release.

Why this exists: war.gov serves one unified table across all releases, so a
re-scrape returns every file (old + new). We want to keep the already-enriched
older entries (translations, previews, video embeds) untouched and append only
the genuinely-new records, tagged with the new release date.

Matching is by a *canonical* key that ignores zero-padding, because war.gov
re-pads document codes between releases (e.g. DOW-UAP-PR19 -> DOW-UAP-PR019).
A naive title/id match would treat the re-padded file as new and duplicate it.

Video/audio records arrive with unstable `record-N` ids (the row index, which
shifts every scrape), so new ones are re-keyed to a stable slug from their
document code (e.g. DOW-UAP-PR050 -> dow-uap-pr050).

Usage:
    python scripts/merge_release.py --new ~/Downloads/manifest.json \\
        --release-label "5/22/26"
    python scripts/merge_release.py --new scrape.json --release-label "5/22/26" --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"


def log(msg: str) -> None:
    print(f"[merge_release] {msg}", file=sys.stderr, flush=True)


def canon(title: str | None) -> str:
    """Canonical match key from a title: the document code before the first
    comma, uppercased, spaces stripped, and digit-runs normalized to drop
    leading zeros (PR019 -> PR19, D001 -> D1)."""
    head = (title or "").split(",")[0].strip().upper()
    head = re.sub(r"\s+", "", head)
    head = re.sub(r"\d+", lambda m: str(int(m.group(0))), head)
    return head


def make_id(entry: dict, used: set[str]) -> str:
    """Stable, unique id. Filename-derived ids (PDFs/images) are kept
    (lowercased); unstable record-N ids (video/audio) are re-derived from the
    document-code prefix of the title."""
    rid = entry.get("id") or ""
    if rid and not re.match(r"^record-\d+$", rid):
        base = rid.lower()
    else:
        head = (entry.get("title") or "").split(",")[0].strip()
        base = re.sub(r"[^a-z0-9]+", "-", head.lower()).strip("-") or (rid.lower() or "item")
    cand, i = base, 2
    while cand in used:
        cand = f"{base}-{i}"
        i += 1
    used.add(cand)
    return cand


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", required=True, help="freshly downloaded scrape manifest.json")
    ap.add_argument("--manifest", default=str(MANIFEST_PATH),
                    help="manifest to merge into (default: data/manifest.json)")
    ap.add_argument("--release-label", required=True,
                    help='release_date to stamp on new records, e.g. "5/22/26"')
    ap.add_argument("--dry-run", action="store_true", help="report only; don't write")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    scrape = json.loads(Path(args.new).read_text(encoding="utf-8"))
    existing = manifest.get("files", [])
    scraped = scrape.get("files", [])
    log(f"existing: {len(existing)} files | scraped: {len(scraped)} files")

    existing_ids = {f.get("id") for f in existing}
    existing_canon = {canon(f.get("title")) for f in existing}
    used_ids = set(existing_ids)

    new_records: list[dict] = []
    for f in scraped:
        if f.get("id") in existing_ids or canon(f.get("title")) in existing_canon:
            continue  # already have it (this or a prior release) — keep enriched copy
        entry = dict(f)
        entry["id"] = make_id(f, used_ids)
        entry["release_date"] = args.release_label
        new_records.append(entry)

    log(f"new records for release {args.release_label!r}: {len(new_records)}")
    from collections import Counter
    by_type = dict(Counter(e.get("type") for e in new_records))
    log(f"  by type: {by_type}")

    merged = existing + new_records
    manifest["files"] = merged
    manifest["total_files"] = len(merged)

    # Rebuild the data-driven release summary from per-file release_date.
    counts: dict[str, int] = {}
    for f in merged:
        counts[f.get("release_date") or "unknown"] = counts.get(f.get("release_date") or "unknown", 0) + 1
    manifest["releases"] = [{"label": k, "count": v}
                            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
    manifest["release_id"] = "combined" if len(counts) > 1 else manifest.get("release_id")
    manifest["release_date"] = None if len(counts) > 1 else next(iter(counts), None)
    manifest["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    log(f"merged total: {len(merged)} | releases: {manifest['releases']}")

    if args.dry_run:
        log("dry-run: not writing")
        for e in new_records[:10]:
            log(f"  + [{e.get('type')}] {e['id']}  ({(e.get('title') or '')[:55]})")
        return 0

    Path(args.manifest).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
