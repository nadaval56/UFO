#!/usr/bin/env python3
"""
build_manifest.py — produce data/manifest.json for the PURSUE Hebrew Mirror.

Steps:
  1. Download Release_1.zip from war.gov (unless already cached).
  2. Extract to data/release_01/raw/.
  3. Walk extracted files, derive metadata heuristically from filename.
  4. Emit data/manifest.json.

Run:
    pip install -r requirements.txt
    python build_manifest.py

Notes on metadata extraction
----------------------------
The war.gov bundle does not (as of inspection) include sidecar metadata
files for individual documents. Each file's agency, type, and source_id are
inferred from the filename.

FBI filename pattern observed (from screenshot of the original page):
    65_HS1-834228961_62-HQ-83894_SERIAL_130.pdf
       ^prefix    ^HS id        ^class ^HQ file   ^serial

We treat any filename containing `HQ-` as FBI. The pattern can be extended
as new agencies appear in future releases.

Fields we cannot fill from the filename alone (incident_date,
incident_location, summary_he) are left null — these will be populated in
Phase 2 by PDF text extraction + Claude API summarization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
import urllib.error
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BUNDLE_URL = "https://www.war.gov/medialink/ufo/bundle/Release_1.zip"
SOURCE_FILE_URL_BASE = "https://www.war.gov/medialink/ufo/files"  # verify by sampling
RELEASE_ID = "release_01"
RELEASE_DATE = "2026-05-08"

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / RELEASE_ID / "raw"
ZIP_PATH = DATA_DIR / RELEASE_ID / "Release_1.zip"
MANIFEST_PATH = DATA_DIR / "manifest.json"

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

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FileEntry:
    id: str
    filename: str
    agency: str
    type: str
    size_bytes: int
    source_url: str
    sha256: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    summary_he: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[build_manifest] {msg}", file=sys.stderr)


def http_get(url: str, dest: Path, retries: int = 4) -> None:
    """Download `url` to `dest` with retry + browser-like UA."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    backoff = 2
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as out:
                total = 0
                while chunk := r.read(1024 * 256):
                    out.write(chunk)
                    total += len(chunk)
                log(f"downloaded {total/1_000_000:.1f} MB → {dest.name}")
            return
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            log(f"attempt {attempt} failed: {e}; retrying in {backoff}s")
            time.sleep(backoff)
            backoff *= 2
    raise RuntimeError(f"download failed for {url}: {last_err}")


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    log(f"extracted to {dest_dir}")


def sha256_of(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while data := f.read(chunk):
            h.update(data)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Filename heuristics
# ---------------------------------------------------------------------------

# FBI: filenames contain `HQ-NNNNN`
FBI_RE = re.compile(r"\bHQ-\d{3,6}\b", re.IGNORECASE)
# DOW: placeholder, refine when real samples seen
DOW_RE = re.compile(r"\bDOW[-_]", re.IGNORECASE)
# NASA: placeholder
NASA_RE = re.compile(r"\bNASA[-_]", re.IGNORECASE)
# ODNI / AARO: placeholders
ODNI_RE = re.compile(r"\bODNI[-_]", re.IGNORECASE)
AARO_RE = re.compile(r"\bAARO[-_]", re.IGNORECASE)


def infer_agency(filename: str) -> str:
    name = filename
    if FBI_RE.search(name):
        return "FBI"
    if DOW_RE.search(name):
        return "DOW"
    if NASA_RE.search(name):
        return "NASA"
    if ODNI_RE.search(name):
        return "ODNI"
    if AARO_RE.search(name):
        return "AARO"
    return "Unknown"


def infer_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return KNOWN_EXTENSIONS.get(ext, ext.lstrip(".") or "unknown")


def build_source_url(filename: str) -> str:
    # Verify by clicking a real link on war.gov/UFO — adjust if pattern differs.
    return f"{SOURCE_FILE_URL_BASE}/{filename}"


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------

def walk_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            out.append(p)
    out.sort(key=lambda p: p.name)
    return out


def entry_from_path(path: Path, include_sha: bool = False) -> FileEntry:
    name = path.name
    file_id = path.stem
    return FileEntry(
        id=file_id,
        filename=name,
        agency=infer_agency(name),
        type=infer_type(name),
        size_bytes=path.stat().st_size,
        source_url=build_source_url(name),
        sha256=(sha256_of(path) if include_sha else None),
    )


def emit_manifest(entries: list[FileEntry], out_path: Path) -> None:
    payload = {
        "release_id": RELEASE_ID,
        "release_date": RELEASE_DATE,
        "source_bundle_url": BUNDLE_URL,
        "total_files": len(entries),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": [asdict(e) for e in entries],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f"wrote {out_path} ({len(entries)} files)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-download", action="store_true",
                        help="skip downloading the bundle (use cached zip / raw dir)")
    parser.add_argument("--skip-extract", action="store_true",
                        help="skip extracting the bundle")
    parser.add_argument("--with-sha256", action="store_true",
                        help="compute SHA-256 of each file (slow but useful)")
    parser.add_argument("--raw-dir", default=None,
                        help="override the directory of already-extracted files")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve() if args.raw_dir else RAW_DIR

    if not args.skip_download:
        if ZIP_PATH.exists():
            log(f"bundle already at {ZIP_PATH}; pass --skip-download to skip next time")
        else:
            log(f"downloading {BUNDLE_URL}")
            http_get(BUNDLE_URL, ZIP_PATH)

    if not args.skip_extract:
        if not ZIP_PATH.exists() and not args.skip_download:
            log("zip missing; cannot extract")
            return 1
        if ZIP_PATH.exists():
            extract_zip(ZIP_PATH, raw_dir)

    if not raw_dir.exists():
        log(f"no raw dir at {raw_dir} — nothing to walk")
        return 1

    paths = walk_files(raw_dir)
    if not paths:
        log("no files found in raw dir")
        return 1

    log(f"processing {len(paths)} files (sha256={args.with_sha256})")
    entries = [entry_from_path(p, include_sha=args.with_sha256) for p in paths]
    emit_manifest(entries, MANIFEST_PATH)

    agencies: dict[str, int] = {}
    types: dict[str, int] = {}
    for e in entries:
        agencies[e.agency] = agencies.get(e.agency, 0) + 1
        types[e.type] = types.get(e.type, 0) + 1
    log(f"agencies: {agencies}")
    log(f"types:    {types}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
