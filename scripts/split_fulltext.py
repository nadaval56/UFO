#!/usr/bin/env python3
"""
split_fulltext.py — move each record's full OCR text (`text_en`) out of
data/manifest.json into its own file under data/text/.

Why: the full OCR is ~13 MB of the manifest's ~17 MB, yet only the detail
page shows it, and only when the reader opens the "Full OCR" section. Left
inline it made every visitor download it on the homepage, and it pushed the
manifest past Googlebot's 15 MB per-file fetch limit — a truncated JSON file
fails to parse, so Google would render every page as an empty "loading" shell.

Each record keeps a pointer instead: `text_en_path: "data/text/<name>.txt"`.
file-detail.js fetches it lazily. Idempotent: records that already have
`text_en_path` and no `text_en` are left alone; a fresh `text_en` (e.g. from a
new release's OCR bundle) is written out and replaced by the pointer.

Run after merging any bundle that carries `text_en`:
    python scripts/split_fulltext.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
TEXT_DIR = ROOT / "data" / "text"


def safe_name(record_id: str) -> str:
    # Ids come from war.gov filenames and can contain spaces; keep file
    # names URL-safe so the pointer needs no encoding.
    return re.sub(r"[^A-Za-z0-9._-]+", "_", record_id).strip("_") + ".txt"


def main() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    moved, seen = 0, set()
    for f in m["files"]:
        text = f.get("text_en")
        if not text:
            f.pop("text_en", None)
            continue
        name = safe_name(f["id"])
        if name in seen:
            raise SystemExit(f"file-name collision for {f['id']!r} -> {name}")
        seen.add(name)
        (TEXT_DIR / name).write_text(text, encoding="utf-8")
        f["text_en_path"] = f"data/text/{name}"
        del f["text_en"]
        moved += 1
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    size = MANIFEST.stat().st_size
    print(f"moved text_en for {moved} records -> {TEXT_DIR.relative_to(ROOT)}/; "
          f"manifest now {size / 1e6:.1f} MB", file=sys.stderr)
    if size > 10_000_000:
        print("warning: manifest > 10 MB — Googlebot stops at 15 MB per file", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
