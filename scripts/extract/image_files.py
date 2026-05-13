#!/usr/bin/env python3
"""
image_files.py — handle the standalone PNG/JPG files in --raw-dir (e.g.
the FBI-Photo-* and NASA-UAP-VM* images that are not PDFs).

For each image, find the matching manifest entry by filename, render a JPEG
preview (capped at ~1400px on the long side), and set the standard fields:
  page_count=1, content_kinds=["photo"], preview_pages=[{page,kind,path}],
leaving text_preview_en alone (these have no OCRable typewritten content).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp"}
JPEG_QUALITY = 75
MAX_SIDE = 1400


def find_entry(manifest: dict, fn_lower: str) -> dict | None:
    for f in manifest.get("files", []):
        u = (f.get("source_url") or "").lower()
        if u.endswith("/" + fn_lower) or u == fn_lower:
            return f
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--preview-dir", required=True)
    args = ap.parse_args()

    from PIL import Image

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    preview_dir = Path(args.preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = Path(args.raw_dir)
    images = sorted(p for p in raw_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in SUPPORTED_EXT)

    n_done = 0
    for img_path in images:
        entry = find_entry(manifest, img_path.name.lower())
        if not entry:
            print(f"  no manifest match for {img_path.name}; skipping",
                  file=sys.stderr)
            continue
        eid = entry["id"]
        out_dir = preview_dir / eid
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "p001.jpg"
        try:
            img = Image.open(img_path).convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE))
            img.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
        except Exception as e:
            print(f"  failed {img_path.name}: {e}", file=sys.stderr)
            continue

        manifest_rel = f"data/previews/{eid}/p001.jpg"
        entry["page_count"] = 1
        entry["content_kinds"] = ["photo"]
        entry["preview_pages"] = [{"page": 1, "kind": "photo", "path": manifest_rel}]
        n_done += 1

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"image_files: processed {n_done}/{len(images)} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
