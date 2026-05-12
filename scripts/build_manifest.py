#!/usr/bin/env python3
"""
build_manifest.py — produce data/manifest.json for the PURSUE Hebrew Mirror.

Pipeline:
  1. (optional) Fetch the war.gov UFO page and try to discover a JSON manifest
     or extract the file list from the embedded SPA bundle.
  2. (optional) Download Release_1.zip; extract; walk filenames.
  3. (optional) For each file, scrape the matching detail page for its
     English description.
  4. (optional) Translate each description to Hebrew via the Anthropic API.
  5. Emit data/manifest.json.

Default URL pattern (verified from the live site):

    https://www.war.gov/medialink/ufo/release_1/{lowercase_filename}

Filename pattern, FBI 62-HQ-83894 case file:

    65_HS1-{9-digit-id}_62-HQ-83894_SECTION_{N}.pdf

Run:
    pip install -r requirements.txt
    python build_manifest.py                       # everything (best-effort)
    python build_manifest.py --no-translate        # skip Anthropic call
    python build_manifest.py --skip-download       # use cached files
    python build_manifest.py --keep-existing-he    # don't re-translate already-translated entries
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UFO_PAGE_URL = "https://www.war.gov/UFO/"
BUNDLE_URL = "https://www.war.gov/medialink/ufo/bundle/Release_1.zip"
SOURCE_FILE_URL_BASE = "https://www.war.gov/medialink/ufo/release_1"
RELEASE_ID = "release_01"
RELEASE_DATE = "2026-05-08"

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / RELEASE_ID / "raw"
ZIP_PATH = DATA_DIR / RELEASE_ID / "Release_1.zip"
MANIFEST_PATH = DATA_DIR / "manifest.json"
CACHE_PAGE = DATA_DIR / RELEASE_ID / "ufo_page.html"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

KNOWN_EXTENSIONS = {
    ".pdf": "pdf",
    ".jpg": "img", ".jpeg": "img", ".png": "img", ".tif": "img", ".tiff": "img",
    ".mp4": "vid", ".mov": "vid", ".m4v": "vid", ".avi": "vid",
    ".txt": "txt", ".doc": "doc", ".docx": "doc",
}

CLAUDE_MODEL = "claude-sonnet-4-6"
TRANSLATION_SYSTEM = (
    "אתה מתרגם מקצועי. תרגם טקסט אנגלי לעברית רהוטה ומדויקת. שמור על שמות "
    "פרטיים, מקומות וקודי תיק (כמו 62-HQ-83894) במקור. החזר רק את התרגום, "
    "ללא הסברים נוספים."
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[build_manifest] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def http_get_bytes(url: str, retries: int = 3, timeout: int = 60) -> Optional[bytes]:
    backoff = 2
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            log(f"GET {url} failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(backoff)
                backoff *= 2
    return None


def http_download(url: str, dest: Path) -> bool:
    log(f"downloading {url}")
    data = http_get_bytes(url, timeout=180)
    if data is None:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    log(f"  → {dest} ({len(data)/1_000_000:.1f} MB)")
    return True


# ---------------------------------------------------------------------------
# Filename heuristics
# ---------------------------------------------------------------------------

FBI_RE = re.compile(r"\bHQ-\d{3,6}\b", re.IGNORECASE)
SECTION_RE = re.compile(r"_SECTION_\d+", re.IGNORECASE)
SERIAL_RE = re.compile(r"_SERIAL_\d+", re.IGNORECASE)
DOW_RE = re.compile(r"\bDOW[-_]", re.IGNORECASE)
NASA_RE = re.compile(r"\bNASA[-_]", re.IGNORECASE)
ODNI_RE = re.compile(r"\bODNI[-_]", re.IGNORECASE)
AARO_RE = re.compile(r"\bAARO[-_]", re.IGNORECASE)


def infer_agency(filename: str) -> str:
    if FBI_RE.search(filename): return "FBI"
    if DOW_RE.search(filename): return "DOW"
    if NASA_RE.search(filename): return "NASA"
    if ODNI_RE.search(filename): return "ODNI"
    if AARO_RE.search(filename): return "AARO"
    return "Unknown"


def infer_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return KNOWN_EXTENSIONS.get(ext, ext.lstrip(".") or "unknown")


def build_source_url(filename: str) -> str:
    # war.gov serves files as lowercase paths under /release_1/
    return f"{SOURCE_FILE_URL_BASE}/{filename.lower()}"


# ---------------------------------------------------------------------------
# Discovery: try multiple ways to find the file list
# ---------------------------------------------------------------------------

# Filenames that look like FBI section files inside the SPA page source
INLINE_FILENAME_RE = re.compile(
    r"\b(\d{2}_HS\d?[-_]\d+_\d{2}-HQ-\d+_(?:SECTION|SERIAL)_\d+)\.pdf",
    re.IGNORECASE,
)


def discover_from_page(html: str) -> list[str]:
    """Return de-duplicated filename list (without .pdf) found inside the SPA HTML."""
    seen = set()
    out = []
    for m in INLINE_FILENAME_RE.finditer(html):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def discover_from_zip(zip_path: Path, extract_to: Path) -> list[Path]:
    if not zip_path.exists():
        return []
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    log(f"extracted bundle to {extract_to}")
    out: list[Path] = []
    for p in extract_to.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            out.append(p)
    out.sort(key=lambda p: p.name)
    return out


# ---------------------------------------------------------------------------
# Description scraping
# ---------------------------------------------------------------------------

# Heuristic: the SPA likely embeds descriptions inside JSON-ish structures
# alongside the filename. Match either:
#   "description": "..." right after the filename
#   any other contextual paragraph linked to the filename
DESCRIPTION_NEAR_FILENAME_RE = re.compile(
    r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"',
    re.DOTALL,
)


def extract_descriptions_from_page(html: str) -> dict[str, str]:
    """
    Try to map filename → description by parsing the SPA HTML.

    Returns: dict mapping the bare filename (no extension, original case as it
    appears) to its description string. Empty if the page doesn't embed them.
    """
    results: dict[str, str] = {}
    # Split the HTML by filename occurrences and look for a nearby description.
    matches = list(INLINE_FILENAME_RE.finditer(html))
    if not matches:
        return results
    for i, m in enumerate(matches):
        name = m.group(1)
        # window: from this match until the next, or 4KB ahead
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(html), start + 4000)
        window = html[start:end]
        d = DESCRIPTION_NEAR_FILENAME_RE.search(window)
        if d:
            try:
                # Decode JSON-style escapes
                desc = json.loads(f'"{d.group(1)}"')
            except json.JSONDecodeError:
                desc = d.group(1)
            results[name] = desc.strip()
    return results


# ---------------------------------------------------------------------------
# Anthropic translation
# ---------------------------------------------------------------------------

def translate_to_hebrew(texts: list[str]) -> list[Optional[str]]:
    """
    Translate a batch of English strings to Hebrew. Returns a list of the same
    length (None for entries we couldn't translate). Uses prompt caching so the
    system prompt is cached across calls.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log("ANTHROPIC_API_KEY not set — skipping translation")
        return [None] * len(texts)

    try:
        import anthropic  # type: ignore
    except ImportError:
        log("anthropic package not installed — skipping translation")
        return [None] * len(texts)

    client = anthropic.Anthropic(api_key=api_key)
    out: list[Optional[str]] = []
    for i, text in enumerate(texts, start=1):
        if not text or not text.strip():
            out.append(None)
            continue
        try:
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                system=[{
                    "type": "text",
                    "text": TRANSLATION_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": text}],
            )
            translated = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
            out.append(translated or None)
            if i % 10 == 0:
                log(f"translated {i}/{len(texts)}")
        except Exception as e:
            log(f"translation failed for entry {i}: {e}")
            out.append(None)
    return out


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------

@dataclass
class FileEntry:
    id: str
    filename: str
    agency: str
    type: str
    size_bytes: Optional[int] = None
    source_url: str = ""
    release_date: str = RELEASE_DATE
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    summary_en: Optional[str] = None
    summary_he: Optional[str] = None


def entry_from_name(name_no_ext: str, ext: str = ".pdf",
                    size_bytes: Optional[int] = None) -> FileEntry:
    filename = f"{name_no_ext}{ext}"
    return FileEntry(
        id=name_no_ext,
        filename=filename,
        agency=infer_agency(filename),
        type=infer_type(filename),
        size_bytes=size_bytes,
        source_url=build_source_url(filename),
    )


def entry_from_path(path: Path) -> FileEntry:
    e = entry_from_name(path.stem, path.suffix or ".pdf", size_bytes=path.stat().st_size)
    return e


def emit_manifest(entries: list[FileEntry], out_path: Path) -> None:
    payload = {
        "release_id": RELEASE_ID,
        "release_date": RELEASE_DATE,
        "source_bundle_url": BUNDLE_URL,
        "source_page_url": UFO_PAGE_URL,
        "total_files": len(entries),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": [asdict(e) for e in entries],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f"wrote {out_path} ({len(entries)} files)")


def load_existing_he(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, str] = {}
    for f in data.get("files", []):
        fid = f.get("id")
        he = f.get("summary_he")
        if fid and he:
            out[fid] = he
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-page-fetch", action="store_true",
                        help="don't try to fetch the war.gov UFO page")
    parser.add_argument("--skip-download", action="store_true",
                        help="don't download Release_1.zip")
    parser.add_argument("--skip-extract", action="store_true",
                        help="don't extract the zip even if it's present")
    parser.add_argument("--no-translate", action="store_true",
                        help="skip the Anthropic translation step")
    parser.add_argument("--keep-existing-he", action="store_true",
                        help="re-use summary_he from the existing manifest when present")
    parser.add_argument("--raw-dir", default=None,
                        help="override the directory of already-extracted files")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve() if args.raw_dir else RAW_DIR

    # ------------------------------------------------------------------ 1. page
    page_html = ""
    if not args.skip_page_fetch:
        data = http_get_bytes(UFO_PAGE_URL)
        if data:
            page_html = data.decode("utf-8", errors="replace")
            CACHE_PAGE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PAGE.write_text(page_html, encoding="utf-8")
            log(f"cached SPA page → {CACHE_PAGE} ({len(page_html)} chars)")
        else:
            log("could not fetch war.gov/UFO/ — continuing without page metadata")

    inline_names = discover_from_page(page_html) if page_html else []
    descriptions = extract_descriptions_from_page(page_html) if page_html else {}
    log(f"inline filenames from page: {len(inline_names)}; descriptions: {len(descriptions)}")

    # ------------------------------------------------------------------ 2. zip
    zip_paths: list[Path] = []
    if not args.skip_download and not ZIP_PATH.exists():
        if not http_download(BUNDLE_URL, ZIP_PATH):
            log("bundle download failed")
    if not args.skip_extract and ZIP_PATH.exists():
        zip_paths = discover_from_zip(ZIP_PATH, raw_dir)
    elif raw_dir.exists():
        zip_paths = sorted([p for p in raw_dir.rglob("*") if p.is_file()])

    # ------------------------------------------------------------------ 3. merge sources
    seen: set[str] = set()
    entries: list[FileEntry] = []

    # Prefer zip (gives us real sizes); fall back to inline names from the page.
    for p in zip_paths:
        if p.stem in seen:
            continue
        seen.add(p.stem)
        e = entry_from_path(p)
        e.summary_en = descriptions.get(p.stem)
        entries.append(e)

    for name in inline_names:
        if name in seen:
            continue
        seen.add(name)
        e = entry_from_name(name)
        e.summary_en = descriptions.get(name)
        entries.append(e)

    if not entries:
        log("no files discovered from page or zip — keeping existing manifest unchanged")
        return 0

    # ------------------------------------------------------------------ 4. translate
    existing_he = load_existing_he(MANIFEST_PATH) if args.keep_existing_he else {}
    if not args.no_translate:
        to_translate_idx: list[int] = []
        to_translate_txt: list[str] = []
        for i, e in enumerate(entries):
            if args.keep_existing_he and e.id in existing_he:
                e.summary_he = existing_he[e.id]
                continue
            if e.summary_en:
                to_translate_idx.append(i)
                to_translate_txt.append(e.summary_en)
        if to_translate_txt:
            log(f"translating {len(to_translate_txt)} descriptions to Hebrew")
            translated = translate_to_hebrew(to_translate_txt)
            for idx, t in zip(to_translate_idx, translated):
                entries[idx].summary_he = t

    # ------------------------------------------------------------------ 5. write
    entries.sort(key=lambda e: e.filename)
    emit_manifest(entries, MANIFEST_PATH)

    agencies: dict[str, int] = {}
    types: dict[str, int] = {}
    with_en = sum(1 for e in entries if e.summary_en)
    with_he = sum(1 for e in entries if e.summary_he)
    for e in entries:
        agencies[e.agency] = agencies.get(e.agency, 0) + 1
        types[e.type] = types.get(e.type, 0) + 1
    log(f"agencies: {agencies}")
    log(f"types:    {types}")
    log(f"summaries: en={with_en}, he={with_he}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
