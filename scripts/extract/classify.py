#!/usr/bin/env python3
"""
classify.py — page-by-page heuristic classifier for the Release_1 PDFs.

For every PDF found in --raw-dir, render every page at 100 DPI and classify
it as one of: cover / blank / divider / typewritten / handwritten / clipping
/ photo / mixed. Writes one JSON file per PDF to data/_classification/{id}.json
with a row per page. Designed to be resumable — skips files whose output
already exists.

This is a STARTING POINT. Tune the thresholds against a sample of real files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# Lazy imports so --help works without deps installed
def _imports():
    global Image, np, convert_from_path, tqdm
    from PIL import Image
    import numpy as np
    from pdf2image import convert_from_path
    from tqdm import tqdm
    return Image, np, convert_from_path, tqdm


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "_classification"
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifest.json"


@dataclass
class PageInfo:
    page: int
    kind: str
    score: float           # 0..100 "interest" score
    dark_ratio: float      # fraction of dark pixels
    text_lines_est: int    # estimated typewritten line count
    edge_density: float    # ratio of edge pixels (for photo/clipping)


# --------------------------------------------------------------------------
# Per-page metrics
# --------------------------------------------------------------------------

def page_metrics(img_pil) -> dict:
    """Return cheap-to-compute metrics for one page (PIL image @ ~100 DPI)."""
    Image, np, _, _ = _imports()
    img = img_pil.convert("L")  # grayscale
    arr = np.array(img, dtype=np.uint8)
    h, w = arr.shape

    # dark_ratio: fraction below 90 (rough threshold for "ink")
    dark = arr < 90
    dark_ratio = float(dark.sum()) / (h * w)

    # ink_ratio: looser threshold to catch faint typewriter ribbon and
    # light-colored ink (e.g., blue ballpoint on tinted paper) that misses
    # the dark<90 cutoff. Used by blank/handwritten gates so a low-contrast
    # handwritten letter isn't tagged blank just because the ink is pale.
    ink = arr < 180
    ink_ratio = float(ink.sum()) / (h * w)

    # row-wise ink density — for line-spacing estimation. Use the looser
    # `ink` mask so faint text rows still register; pair with a dynamic
    # threshold (median + delta) so pages with continuous noise/stamps
    # don't collapse to a single peak. The original `dark<90 / w*0.005`
    # rule produced line_peaks=1 for every typewritten page on yellowed
    # or stamp-covered paper because every row exceeded the threshold —
    # the rising-edge counter then fired exactly once.
    row_ink = ink.sum(axis=1)
    baseline = float(np.median(row_ink))
    threshold = max(w * 0.005, baseline + max(w * 0.01, baseline * 0.5))
    line_peaks = 0
    in_peak = False
    for v in row_ink:
        if v > threshold and not in_peak:
            line_peaks += 1
            in_peak = True
        elif v <= threshold:
            in_peak = False

    # edge density via simple horizontal diff (photo detection — smooth gradients,
    # clipping detection — many sharp edges)
    diff = np.abs(arr[:, 1:].astype(int) - arr[:, :-1].astype(int))
    edges = diff > 30
    edge_density = float(edges.sum()) / (h * (w - 1))

    # midtone density: photos have many continuous mid-grey pixels
    midtone = (arr > 60) & (arr < 200)
    midtone_ratio = float(midtone.sum()) / (h * w)

    # photo region: count contiguous mid-grey areas. A single sparse image
    # in a mostly-white page (e.g. PANTEX radar/thermal scans) has low
    # midtone_ratio overall but still has a notable photo region. Estimate
    # by counting "blob" rows — rows where ink+midtone density is between
    # 0.05 and 0.95 (rules out pure-white rows and pure-black stamps).
    blob_mask = (arr > 30) & (arr < 220)
    row_blob = blob_mask.sum(axis=1)
    blob_rows = int(((row_blob > w * 0.03) & (row_blob < w * 0.95)).sum())
    photo_region_ratio = blob_rows / float(h) if h else 0.0

    return {
        "dark_ratio": dark_ratio,
        "ink_ratio": ink_ratio,
        "line_peaks": line_peaks,
        "edge_density": edge_density,
        "midtone_ratio": midtone_ratio,
        "photo_region_ratio": photo_region_ratio,
        "width": w,
        "height": h,
    }


# --------------------------------------------------------------------------
# Heuristic classifier — TUNE ME
# --------------------------------------------------------------------------

def classify(metrics: dict, page_no: int, total_pages: int) -> tuple[str, float]:
    """Return (kind, interest_score). Refine thresholds against real samples."""
    d = metrics["dark_ratio"]
    ink = metrics["ink_ratio"]
    lp = metrics["line_peaks"]
    ed = metrics["edge_density"]
    mt = metrics["midtone_ratio"]
    pr = metrics["photo_region_ratio"]

    # Very low ink → blank or divider. Use ink_ratio (loose threshold) so
    # pale-blue handwritten pages aren't tagged blank.
    if ink < 0.005:
        return ("blank", 0)
    if ink < 0.02 and lp < 5:
        return ("divider", 5)

    # Cover heuristic — first 1-2 pages with few lines and moderate ink,
    # AND no notable image region (so we don't tag a sparse-image first
    # page like a PANTEX radar shot as cover).
    if page_no <= 2 and lp < 15 and d < 0.15 and mt < 0.10 and pr < 0.15:
        return ("cover", 10)

    # Typewritten gate FIRST. If a page has many regular text lines, it's a
    # document scan no matter how grey/mid-toned the paper is. This prevents
    # the photo branch from grabbing scanned typed pages on yellowed paper.
    if lp >= 20 and 0.03 < ink < 0.7:
        score = 60 + min(20, max(0, lp - 20))
        return ("typewritten", score)

    # Photo, three cases:
    #   A. Full-page mid-grey photograph (lots of midtone, no text rows).
    #   B. Photograph mounted on a page — large photo region + dark mass
    #      (the photo itself) + few text rows. Catches classic UAP photos
    #      with a typed caption below.
    #   C. Sparse image on white background — small graphic in lots of
    #      whitespace (e.g. radar/thermal scans). Low ink, low edges.
    #      `lp < 8` and `mt > 0.03` keep sparse *text* out of this branch:
    #      DOS-UAP-D002 p2 is three typed lines and a signature on yellowed
    #      paper (pr≈0.97, ink≈0.015). It used to win the curated-preview
    #      slot, which suppressed the fallback previews, so the card showed
    #      a near-blank page.
    if (mt > 0.35 and lp < 6 and ed < 0.08) or \
       (pr > 0.30 and lp < 8 and (mt > 0.30 or ink > 0.20)) or \
       (pr > 0.15 and ink < 0.05 and ed < 0.05 and lp < 8 and mt > 0.03):
        return ("photo", 90)

    # Illustration: hand-drawn sketches / witness drawings. Moderate-to-high
    # edge density (lines and curves), low midtone (mostly white paper with
    # ink lines), few regular text rows.
    if 0.04 < ed < 0.15 and mt < 0.30 and lp < 10 and 0.02 < d < 0.20:
        return ("illustration", 85)

    # Clipping: newspaper/magazine — high edge density + many short text lines.
    if ed > 0.08 and lp > 15:
        return ("clipping", 80)

    # Looser typewritten fallback — covers faint old-typewriter ribbons
    # AND short typed letters with lots of whitespace (ink can be as low
    # as 1%). Lower bound just rules out near-blank pages.
    if lp >= 12 and ink > 0.003 and ink < 0.6:
        return ("typewritten", 55)

    # Handwritten — moderate ink (or even light ink), few clean line peaks.
    # Use ink_ratio so light-colored ballpoint catches.
    if ink > 0.02 and lp < 12:
        return ("handwritten", 30)

    return ("mixed", 40)


# --------------------------------------------------------------------------
# File iteration
# --------------------------------------------------------------------------

def manifest_id_for_filename(manifest: dict, filename: str) -> Optional[str]:
    """Find the manifest entry whose source_url ends with this filename, return its id."""
    fn = filename.lower()
    for f in manifest.get("files", []):
        u = (f.get("source_url") or "").lower()
        if u.endswith("/" + fn):
            return f.get("id")
    return None


def process_pdf(pdf_path: Path, out_path: Path, dpi: int = 100) -> None:
    Image, np, convert_from_path, tqdm = _imports()
    pages = convert_from_path(str(pdf_path), dpi=dpi, fmt="jpeg")
    total = len(pages)
    rows: list[dict] = []
    for i, img in enumerate(pages, start=1):
        m = page_metrics(img)
        kind, score = classify(m, page_no=i, total_pages=total)
        rows.append({
            "page": i,
            "kind": kind,
            "score": score,
            "dark_ratio": round(m["dark_ratio"], 4),
            "ink_ratio": round(m["ink_ratio"], 4),
            "line_peaks": m["line_peaks"],
            "edge_density": round(m["edge_density"], 4),
            "midtone_ratio": round(m["midtone_ratio"], 4),
            "photo_region_ratio": round(m["photo_region_ratio"], 4),
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "filename": pdf_path.name,
        "page_count": total,
        "pages": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", required=True,
                    help="Directory containing extracted Release_1 PDFs")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--dpi", type=int, default=100)
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only the first N files (for smoke-testing)")
    args = ap.parse_args()

    Image, np, convert_from_path, tqdm = _imports()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted([p for p in Path(args.raw_dir).rglob("*.pdf")])
    if args.limit:
        pdfs = pdfs[:args.limit]

    print(f"Processing {len(pdfs)} PDFs at {args.dpi} DPI...", file=sys.stderr)
    for pdf in tqdm(pdfs):
        mid = manifest_id_for_filename(manifest, pdf.name)
        if not mid:
            print(f"  no manifest match for {pdf.name}; skipping", file=sys.stderr)
            continue
        out = out_dir / f"{mid}.json"
        if out.exists():
            continue
        try:
            process_pdf(pdf, out, dpi=args.dpi)
        except Exception as e:
            print(f"  failed {pdf.name}: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
