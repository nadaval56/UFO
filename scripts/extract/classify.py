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

    # row-wise dark density — for line-spacing estimation
    row_dark = dark.sum(axis=1)
    # count peaks (rows with >= 0.5% of width as dark) to estimate text lines
    threshold = w * 0.005
    line_peaks = 0
    in_peak = False
    for v in row_dark:
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

    return {
        "dark_ratio": dark_ratio,
        "line_peaks": line_peaks,
        "edge_density": edge_density,
        "midtone_ratio": midtone_ratio,
        "width": w,
        "height": h,
    }


# --------------------------------------------------------------------------
# Heuristic classifier — TUNE ME
# --------------------------------------------------------------------------

def classify(metrics: dict, page_no: int, total_pages: int) -> tuple[str, float]:
    """Return (kind, interest_score). Refine thresholds against real samples."""
    d = metrics["dark_ratio"]
    lp = metrics["line_peaks"]
    ed = metrics["edge_density"]
    mt = metrics["midtone_ratio"]

    # Very low ink → blank or divider
    if d < 0.005:
        return ("blank", 0)
    if d < 0.02 and lp < 5:
        return ("divider", 5)

    # Cover heuristic — first page with moderate ink and few lines, or words
    # like "FOLDER" should be detected by OCR later. For now: page 1-2 with
    # < 20 lines and moderate ink ratio → cover.
    if page_no <= 2 and lp < 15 and d < 0.15:
        return ("cover", 10)

    # Photo: lots of midtone, low line-peak count
    if mt > 0.35 and lp < 8:
        return ("photo", 90)

    # Clipping: high edge density + many short text lines
    if ed > 0.08 and lp > 20:
        return ("clipping", 80)

    # Typewritten: moderate-to-high line peaks, regular spacing,
    # ink ratio in typical text range
    if lp >= 15 and 0.03 < d < 0.4:
        # bonus if line count is "page-shaped" (40-65 lines)
        score = 60 + min(20, max(0, lp - 20))
        return ("typewritten", score)

    # Handwritten — heuristic: ink ratio moderate but few clean line peaks.
    # Very crude. Refine.
    if d > 0.05 and lp < 12:
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
            "line_peaks": m["line_peaks"],
            "edge_density": round(m["edge_density"], 4),
            "midtone_ratio": round(m["midtone_ratio"], 4),
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
