#!/usr/bin/env python3
"""
sample.py — pick 4-6 representative pages per PDF, render them at 300 DPI as
compressed JPEGs, write them into data/previews/{id}/p{NNN}.jpg, and update
data/manifest.json with `preview_pages` and `content_kinds`.

Reads the classification JSONs that classify.py produced. Idempotent: if a
preview JPEG already exists, skips re-rendering.

Picking strategy (refine as needed):
  - Sort pages by kind priority: photo > clipping > typewritten > mixed
  - Within each kind, sort by interest score descending
  - Take up to TARGET_COUNT pages, ensuring diversity of kinds when possible
  - Skip cover / blank / divider / handwritten unless nothing else available
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

KIND_PRIORITY = {
    "photo": 4,
    "clipping": 3,
    "typewritten": 2,
    "mixed": 1,
}
SKIP_KINDS = {"cover", "blank", "divider", "handwritten"}
TARGET_COUNT = 6
PREVIEW_DPI = 300
JPEG_QUALITY = 75
MAX_PREVIEW_KB = 120  # warn if a preview is bigger


def pick_pages(pages: list[dict], target: int = TARGET_COUNT) -> list[dict]:
    """Pick a diverse, interest-ranked subset."""
    eligible = [p for p in pages if p["kind"] not in SKIP_KINDS]
    if not eligible:
        # fallback: best non-blank pages even if "skipped"
        eligible = [p for p in pages if p["kind"] != "blank"]
    eligible.sort(
        key=lambda p: (KIND_PRIORITY.get(p["kind"], 0), p["score"]),
        reverse=True,
    )
    # Ensure kind diversity in the first picks
    picked, kinds_seen = [], set()
    for p in eligible:
        if p["kind"] not in kinds_seen:
            picked.append(p)
            kinds_seen.add(p["kind"])
        if len(picked) >= min(target, len(KIND_PRIORITY)):
            break
    # Fill remaining slots with next-best regardless of kind dup
    for p in eligible:
        if len(picked) >= target:
            break
        if p not in picked:
            picked.append(p)
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
    # Render only the one page
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
    img.thumbnail((1600, 1600))  # cap dimensions
    img.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True)


def update_manifest(manifest_path: Path, entry_id: str, content_kinds: list[str],
                    preview_pages: list[dict]) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for f in manifest["files"]:
        if f.get("id") == entry_id:
            f["page_count"] = f.get("page_count")  # set elsewhere
            f["content_kinds"] = content_kinds
            f["preview_pages"] = preview_pages
            break
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--class-dir", default=str(DEFAULT_CLASS_DIR))
    ap.add_argument("--preview-dir", default=str(DEFAULT_PREVIEW_DIR))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    from tqdm import tqdm
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_dir = Path(args.raw_dir)
    class_dir = Path(args.class_dir)
    preview_dir = Path(args.preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)

    files = manifest["files"]
    if args.limit:
        files = files[:args.limit]

    for entry in tqdm(files):
        eid = entry.get("id")
        if not eid:
            continue
        cjson = class_dir / f"{eid}.json"
        if not cjson.exists():
            continue
        cdata = json.loads(cjson.read_text(encoding="utf-8"))
        pages = cdata.get("pages", [])
        if not pages:
            continue

        # Aggregate content kinds (sorted by count desc)
        kind_counts: dict[str, int] = {}
        for p in pages:
            k = p["kind"]
            if k in SKIP_KINDS:
                continue
            kind_counts[k] = kind_counts.get(k, 0) + 1
        content_kinds = [k for k, _ in sorted(kind_counts.items(),
                                              key=lambda x: -x[1])]

        # Pick + render
        pdf = find_pdf(raw_dir, entry)
        if not pdf:
            print(f"  no PDF found for {eid}; skipping", file=sys.stderr)
            continue
        picks = pick_pages(pages)
        preview_pages: list[dict] = []
        for p in picks:
            jpg_name = f"p{p['page']:03d}.jpg"
            jpg_rel = Path("data") / "previews" / eid / jpg_name
            jpg_abs = REPO_ROOT / jpg_rel
            if not jpg_abs.exists():
                try:
                    render_preview(pdf, p["page"], jpg_abs)
                except Exception as e:
                    print(f"  render fail {eid} p{p['page']}: {e}", file=sys.stderr)
                    continue
            if jpg_abs.exists():
                preview_pages.append({
                    "page": p["page"],
                    "kind": p["kind"],
                    "path": str(jpg_rel).replace("\\", "/"),
                })
                sz = jpg_abs.stat().st_size // 1024
                if sz > MAX_PREVIEW_KB:
                    print(f"  ⚠ {jpg_rel} is {sz} KB (over {MAX_PREVIEW_KB})",
                          file=sys.stderr)

        # Patch the manifest in-memory; bulk-write below
        entry["page_count"] = cdata.get("page_count")
        entry["content_kinds"] = content_kinds
        entry["preview_pages"] = preview_pages

    # Bulk-write
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
