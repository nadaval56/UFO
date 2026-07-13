#!/usr/bin/env python3
"""Merge DVIDS video metadata into manifest.json.

Reads data/dvids/uap_videos.json (captured from war.gov DVIDS API) and adds
per-video fields to the 28 vid entries in data/manifest.json:
  - dvids_id           e.g. "1006056"
  - dvids_url          DVIDS page URL
  - media_url          best balanced MP4 (~720p, ~3000kbps)
  - media_url_hq       highest-quality MP4 (1080p)
  - media_url_lq       low-bandwidth MP4 (288p)
  - poster_url         thumbnail (720w)
  - duration_s         duration in seconds
  - aspect_ratio       e.g. "16:9"
Note: DVIDS description is already in `summary_en` (harvested earlier),
so we don't write `description_en`.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
DVIDS = ROOT / "data" / "dvids" / "uap_videos.json"


def _norm_pr(s: str) -> str:
    """Make PR codes zero-pad-insensitive so DOW-UAP-PR050 == DOW-UAP-PR50.
    war.gov re-padded the codes between Release 01 and 02."""
    return re.sub(r"PR0*(\d+)", r"PR\1", s)


def title_key(title: str) -> str:
    """Extract a canonical prefix usable for matching anchors.

    "DOW-UAP-PR19, Unresolved UAP Report, ..."  -> "DOW-UAP-PR19"
    "NASA Audio 12/5/1965 Low Earth Orbit"      -> "NASA-AUDIO-1965"  (manual NASA mapping)
    """
    if title.startswith("NASA Audio"):
        return "NASA-UAP-D3A"  # Gemini 7 audio, 12/5/1965 — confirmed via analyticsParams
    # Any agency PR code (DOW/FBI/CIA/…-UAP-PR###), not just DOW.
    m = re.match(r"^([A-Z]{2,5}-UAP-PR\d+)", title)
    return _norm_pr(m.group(1)) if m else title


def anchor_key(anchor: str) -> str:
    """First segment of anchor: DOW-UAP-PR19-..., NASA-UAP-D3A-... -> prefix."""
    if anchor.startswith("NASA-UAP-D3A"):
        return "NASA-UAP-D3A"
    m = re.match(r"^([A-Z]{2,5}-UAP-PR\d+)", anchor)
    return _norm_pr(m.group(1)) if m else anchor


def pick_mp4(files: list, target_height: int) -> dict | None:
    """Pick the smallest MP4 file at >= target_height (cheapest acceptable)."""
    eligible = [f for f in files if f.get("type") == "video/mp4" and f.get("height", 0) >= target_height]
    if not eligible:
        eligible = [f for f in files if f.get("type") == "video/mp4"]
    if not eligible:
        return None
    return min(eligible, key=lambda f: f.get("size", 1 << 60))


def main():
    dvids = json.loads(DVIDS.read_text(encoding="utf-8"))

    # Index DVIDS records by title-key
    by_key: dict[str, dict] = {}
    for asset_id, rec in dvids.items():
        if not rec:
            continue
        k = title_key(rec.get("title", ""))
        by_key[k] = rec

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    applied, missed = 0, []
    total_vid = sum(1 for f in manifest["files"] if f.get("type") == "vid")

    for f in manifest["files"]:
        if f.get("type") != "vid":
            continue
        src = f.get("source_url") or ""
        if "#" not in src:
            missed.append(f.get("id"))
            continue
        anchor = src.split("#", 1)[1]
        k = anchor_key(anchor)
        rec = by_key.get(k)
        if not rec:
            missed.append(f"{f.get('id')} ({k})")
            continue

        files = rec.get("files", [])
        mp4_hq = pick_mp4(files, 1080)
        mp4_md = pick_mp4(files, 720)
        mp4_lq = pick_mp4(files, 288)
        # 720p balanced default
        if mp4_md is None:
            mp4_md = mp4_hq

        dvids_id = str(rec.get("id", "")).replace("video:", "")
        f["dvids_id"] = dvids_id
        f["dvids_url"] = rec.get("url")
        if mp4_md: f["media_url"] = mp4_md["src"]
        if mp4_hq: f["media_url_hq"] = mp4_hq["src"]
        if mp4_lq: f["media_url_lq"] = mp4_lq["src"]
        thumb = (rec.get("thumbnail") or {}).get("url") or rec.get("image")
        if thumb: f["poster_url"] = thumb
        if rec.get("duration") is not None: f["duration_s"] = rec["duration"]
        if rec.get("aspect_ratio"): f["aspect_ratio"] = rec["aspect_ratio"]
        if rec.get("date"): f["dvids_date"] = rec["date"]
        # description_en duplicates summary_en (already in manifest), so we drop it
        f.pop("description_en", None)

        applied += 1

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"applied: {applied}/{total_vid}")
    if missed:
        print(f"missed: {missed}")


if __name__ == "__main__":
    main()
