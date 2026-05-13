#!/usr/bin/env python3
"""
qc.py — print a quality-control summary of the manifest after extraction.

Reports:
  - total files, files processed, files with previews, files with OCR text
  - distribution of content_kinds across the corpus
  - preview size budget (total MB)
  - 10 randomly-sampled files with their content_kinds + preview pages
  - OCR text sanity: lengths, a few sample snippets
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--preview-dir", required=True)
    ap.add_argument("--sample-n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    preview_dir = Path(args.preview_dir)
    files = manifest["files"]

    n_total = len(files)
    n_processed = sum(1 for f in files if f.get("_extracted_at"))
    n_previews = sum(1 for f in files if f.get("preview_pages"))
    n_ocr = sum(1 for f in files if f.get("text_preview_en"))

    print(f"=== summary ===")
    print(f"total entries:         {n_total}")
    print(f"processed (_extracted): {n_processed}")
    print(f"with preview_pages:    {n_previews}")
    print(f"with text_preview_en:  {n_ocr}")
    print()

    kind_counts: Counter[str] = Counter()
    for f in files:
        for k in f.get("content_kinds") or []:
            kind_counts[k] += 1
    print("=== content_kinds across corpus (file-level presence) ===")
    for k, c in kind_counts.most_common():
        print(f"  {k:12s} {c}")
    print()

    n_with_photo_or_clipping = sum(
        1 for f in files
        if any(k in (f.get("content_kinds") or []) for k in ("photo", "clipping"))
    )
    print(f"files with at least one photo or clipping: {n_with_photo_or_clipping}")
    print()

    if preview_dir.exists():
        total_bytes = sum(p.stat().st_size for p in preview_dir.rglob("*.jpg"))
        print(f"=== preview disk budget ===")
        print(f"total previews: {sum(1 for _ in preview_dir.rglob('*.jpg'))}")
        print(f"total size:     {total_bytes/1024/1024:.1f} MB")
        print()

    print(f"=== random sample of {args.sample_n} processed files ===")
    rng = random.Random(args.seed)
    processed = [f for f in files if f.get("_extracted_at")]
    sample = rng.sample(processed, k=min(args.sample_n, len(processed)))
    for f in sample:
        print(f"\n--- {f.get('id')} ({f.get('page_count')} pages) ---")
        print(f"  kinds:    {f.get('content_kinds')}")
        for pp in (f.get("preview_pages") or [])[:6]:
            print(f"  preview:  p{pp['page']:03d} ({pp['kind']}) {pp['path']}")
        txt = f.get("text_preview_en") or ""
        if txt:
            print(f"  text_en ({len(txt)} chars): {txt[:240].strip()}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
