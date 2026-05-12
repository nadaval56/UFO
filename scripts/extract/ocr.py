#!/usr/bin/env python3
"""
ocr.py — OCR typewritten pages and produce `text_preview_en` per manifest entry.

For each manifest entry, find the pages classified as `typewritten` (and
optionally `clipping`), render them at 300 DPI, run tesseract, drop pages
whose confidence is too low, concatenate, trim to ~3000 chars sentence-aligned,
write back to `manifest.files[i].text_preview_en`.

Caches per-page raw OCR text in data/_ocr/{id}/p{NNN}.txt so re-runs are cheap.

Configure max pages per file via --max-pages-per-file (default: 3). Going
higher gets you more text but also more cost; for most files 3 typewritten
pages is plenty for a preview.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifest.json"
DEFAULT_CLASS_DIR = REPO_ROOT / "data" / "_classification"
DEFAULT_OCR_DIR = REPO_ROOT / "data" / "_ocr"

OCR_DPI = 300
PREVIEW_CHAR_LIMIT = 3000
MIN_CONFIDENCE = 60        # average tesseract confidence threshold
PREFERRED_KINDS = ["typewritten", "clipping"]


def ocr_page(pdf_path: Path, page_num: int, dpi: int = OCR_DPI) -> tuple[str, float]:
    """Return (text, mean_confidence)."""
    import pytesseract
    from pdf2image import convert_from_path
    imgs = convert_from_path(str(pdf_path), dpi=dpi,
                             first_page=page_num, last_page=page_num, fmt="jpeg")
    if not imgs:
        return "", 0.0
    img = imgs[0]
    # word-level data for confidence scoring
    data = pytesseract.image_to_data(img, lang="eng", output_type=pytesseract.Output.DICT)
    confs = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
    text = pytesseract.image_to_string(img, lang="eng")
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return text, mean_conf


def trim_to_chars(s: str, limit: int) -> str:
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    # Back up to the last sentence end if reasonable
    m = re.search(r"[.!?]\s+\S+$", cut[-200:])
    if m:
        cut = cut[: limit - 200 + m.start() + 1]
    return cut.rstrip() + "…"


def find_pdf(raw_dir: Path, manifest_entry: dict) -> Path | None:
    fn = (manifest_entry.get("source_url") or "").rsplit("/", 1)[-1].lower()
    if not fn:
        return None
    for p in raw_dir.rglob("*.pdf"):
        if p.name.lower() == fn:
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--class-dir", default=str(DEFAULT_CLASS_DIR))
    ap.add_argument("--ocr-dir", default=str(DEFAULT_OCR_DIR))
    ap.add_argument("--max-pages-per-file", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    from tqdm import tqdm
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_dir = Path(args.raw_dir)
    class_dir = Path(args.class_dir)
    ocr_dir = Path(args.ocr_dir)
    ocr_dir.mkdir(parents=True, exist_ok=True)

    files = manifest["files"]
    if args.limit:
        files = files[:args.limit]

    for entry in tqdm(files):
        eid = entry.get("id")
        if not eid:
            continue
        if entry.get("text_preview_en"):
            continue  # already done
        cjson = class_dir / f"{eid}.json"
        if not cjson.exists():
            continue
        pages = json.loads(cjson.read_text(encoding="utf-8")).get("pages", [])
        # Pick top N typewritten/clipping pages by score
        candidates = [p for p in pages if p["kind"] in PREFERRED_KINDS]
        candidates.sort(key=lambda p: p["score"], reverse=True)
        candidates = candidates[: args.max_pages_per_file]
        if not candidates:
            continue
        pdf = find_pdf(raw_dir, entry)
        if not pdf:
            continue

        cache_dir = ocr_dir / eid
        cache_dir.mkdir(parents=True, exist_ok=True)
        chunks: list[str] = []
        for c in candidates:
            cache_file = cache_dir / f"p{c['page']:03d}.txt"
            if cache_file.exists():
                text = cache_file.read_text(encoding="utf-8")
            else:
                try:
                    text, conf = ocr_page(pdf, c["page"])
                except Exception as e:
                    print(f"  ocr fail {eid} p{c['page']}: {e}", file=sys.stderr)
                    continue
                if conf < MIN_CONFIDENCE:
                    print(f"  low conf {eid} p{c['page']}: {conf:.0f}", file=sys.stderr)
                    continue
                cache_file.write_text(text, encoding="utf-8")
            if text.strip():
                chunks.append(text.strip())

        if chunks:
            preview = trim_to_chars("\n\n".join(chunks), PREVIEW_CHAR_LIMIT)
            entry["text_preview_en"] = preview

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
