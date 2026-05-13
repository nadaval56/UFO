#!/usr/bin/env python3
"""
finalize.py — add `text_preview_he: null` and `_extracted_at` to every
manifest entry that the pipeline touched (has page_count, preview_pages,
or text_preview_en). Idempotent.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    path = Path(args.manifest)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    touched_keys = ("page_count", "content_kinds", "preview_pages", "text_preview_en")
    n_touched = 0
    for f in manifest.get("files", []):
        if any(f.get(k) is not None for k in touched_keys):
            f.setdefault("text_preview_he", None)
            f.setdefault("_extracted_at", stamp)
            n_touched += 1

    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"finalize: stamped {n_touched}/{len(manifest['files'])} entries at {stamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
