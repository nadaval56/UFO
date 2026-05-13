#!/usr/bin/env python3
"""
fallback_previews.py — fill in preview pages for files that have NO
visually-interesting content (no photo / illustration / clipping).

The original sample.py policy was "empty is better than misleading" —
preview_pages stays empty rather than showing typewritten/handwritten/
cover pages. In production this left ~86 of 158 files with zero visuals,
which feels broken on the public site.

This script adds a parallel `preview_pages_fallback` field for affected
files, rendering up to N pages (default 4) of *any* kind — cover, first
non-blank typewritten / handwritten page, etc. The original
`preview_pages` field is left untouched, so the front-end can still tell
"curated" vs "fallback" thumbnails apart.

Picking strategy for fallback:
  1. The cover page (page 1) if it's not blank.
  2. The first N-1 non-blank, non-divider pages in document order
     (typewritten / handwritten / mixed / cover continued).

DPI 220, JPEG quality 70, max-side 1600px — matches sample.py defaults.
Idempotent — if `preview_pages_fallback` already exists for an entry,
the entry is skipped (delete the field to redo). Rendered JPEGs are
skipped if already on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifest.json"
DEFAULT_CLASS_DIR = REPO_ROOT / "data" / "_classification"
DEFAULT_PREVIEW_DIR = REPO_ROOT / "data" / "previews"

PREVIEW_DPI = 220
JPEG_QUALITY = 70
MAX_DIMENSION = 1600
MAX_FALLBACK_DEFAULT = 4

# Kinds we'd never want to surface even as fallback
SKIP_KINDS = {"blank", "divider"}


def pick_fallback_pages(pages: list[dict], target: int) -> list[dict]:
    """Pick up to `target` pages for fallback presentation.

    Strategy: page 1 if not blank, then first non-blank, non-divider
    pages in document order. No interest-score sorting — we just want
    *something* to show, in roughly the order a human would flip
    through the PDF.
    """
    by_page = sorted(pages, key=lambda p: p["page"])
    picked: list[dict] = []
    seen_pages = set()

    # Cover page first if not blank
    if by_page and by_page[0]["kind"] not in SKIP_KINDS:
        picked.append(by_page[0])
        seen_pages.add(by_page[0]["page"])

    # Then fill in document order
    for p in by_page:
        if len(picked) >= target:
            break
        if p["page"] in seen_pages:
            continue
        if p["kind"] in SKIP_KINDS:
            continue
        picked.append(p)
        seen_pages.add(p["page"])

    return picked


def find_pdf(raw_dir: Path, manifest_entry: dict) -> Path | None:
    fn = (manifest_entry.get("source_url") or "").rsplit("/", 1)[-1].lower()
    if not fn:
        return None
    for p in raw_dir.rglob("*.pdf"):
        if p.name.lower() == fn:
            return p
    return None


def render_preview(pdf_path: Path, page_num: int, out_path: Path) -> None:
    from pdf2image import convert_from_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    imgs = convert_from_path(
        str(pdf_path),
        dpi=PREVIEW_DPI,
        first_page=page_num,
        last_page=page_num,
        fmt="jpeg",
    )
    if not imgs:
        return
    img = imgs[0]
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    img.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--raw-dir", required=True,
                    help="Directory containing the source PDFs")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--class-dir", default=str(DEFAULT_CLASS_DIR))
    ap.add_argument("--preview-dir", default=str(DEFAULT_PREVIEW_DIR))
    ap.add_argument("--max-fallback", type=int, default=MAX_FALLBACK_DEFAULT,
                    help="Max fallback pages per file (default %(default)s)")
    ap.add_argument("--min-existing", type=int, default=2,
                    help=("Only fill in fallback when preview_pages has "
                          "fewer than this many entries (default %(default)s)"))
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only the first N applicable files")
    args = ap.parse_args()

    from tqdm import tqdm

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_dir = Path(args.raw_dir)
    class_dir = Path(args.class_dir)
    preview_dir = Path(args.preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)

    files = manifest["files"]

    todo = []
    for f in files:
        eid = f.get("id")
        if not eid:
            continue
        if "preview_pages_fallback" in f:
            continue  # already done; remove field to redo
        existing = f.get("preview_pages") or []
        if len(existing) >= args.min_existing:
            continue
        cjson = class_dir / f"{eid}.json"
        if not cjson.exists():
            continue
        todo.append(f)

    if args.limit:
        todo = todo[: args.limit]

    print(f"Will process {len(todo)} files needing fallback previews",
          file=sys.stderr)

    for entry in tqdm(todo):
        eid = entry["id"]
        cjson = class_dir / f"{eid}.json"
        cdata = json.loads(cjson.read_text(encoding="utf-8"))
        pages = cdata.get("pages", [])
        if not pages:
            continue

        existing_pages = {p["page"] for p in (entry.get("preview_pages") or [])}
        candidate_pages = [p for p in pages if p["page"] not in existing_pages]

        picks = pick_fallback_pages(candidate_pages, args.max_fallback)
        if not picks:
            continue

        pdf = find_pdf(raw_dir, entry)
        if not pdf:
            print(f"  no PDF for {eid}; skipping", file=sys.stderr)
            continue

        rendered: list[dict] = []
        for p in picks:
            jpg_name = f"p{p['page']:03d}.jpg"
            # The "path" stored in the manifest is always repo-relative so
            # the front-end can resolve it from the deployed site root.
            jpg_rel = Path("data") / "previews" / eid / jpg_name
            # The actual rendering target obeys --preview-dir so the script
            # is usable from a working dir other than the repo root.
            jpg_abs = preview_dir / eid / jpg_name
            if not jpg_abs.exists():
                try:
                    render_preview(pdf, p["page"], jpg_abs)
                except Exception as e:
                    print(f"  render fail {eid} p{p['page']}: {e}",
                          file=sys.stderr)
                    continue
            if jpg_abs.exists():
                rendered.append({
                    "page": p["page"],
                    "kind": p["kind"],
                    "path": str(jpg_rel).replace("\\", "/"),
                })

        entry["preview_pages_fallback"] = rendered

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
