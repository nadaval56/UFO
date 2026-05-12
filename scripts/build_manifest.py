#!/usr/bin/env python3
"""
build_manifest.py — scrape the live war.gov/UFO file list with Playwright.

The page is a Single-Page Application: a plain HTTP GET returns only the JS
bundle, so heuristic filename parsing is useless. This script renders the
page in headless Chromium, walks every row of the file table, and writes
data/manifest.json with the real metadata.

For each file it captures:
  - title           (human-readable, displayed on the row)
  - filename        (the underlying asset name)
  - agency          (FBI, DEPARTMENT OF STATE, DEPARTMENT OF WAR, …)
  - release_date    (raw display, e.g. "5/8/26")
  - incident_date   (raw display, e.g. "9/1/23" or "LATE 2025")
  - incident_location  (e.g. "UNITED STATES", "TURKMENISTAN", …)
  - type            (.pdf / .img / .vid)
  - source_url      (real download URL — extracted from the page, not guessed)
  - summary_en      (the description shown on the detail panel)

A HEAD request validates each source_url returns 2xx; non-2xx URLs are
flagged in the manifest with `url_status` so the front-end can warn.

Hebrew translations are produced separately (Claude Code session) and live
in the same manifest under summary_he / title_he / agency_he etc. This
script preserves whatever Hebrew is already in the existing manifest.

Run locally:
    pip install -r scripts/requirements.txt
    playwright install --with-deps chromium
    python scripts/build_manifest.py

CI uses the same invocation (see .github/workflows/deploy.yml).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Any

UFO_PAGE_URL = "https://www.war.gov/UFO/"
RELEASE_ID = "release_01"
RELEASE_DATE = "2026-05-08"

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
DEBUG_DIR = DATA_DIR / "_debug"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

EXT_TYPE = {
    ".pdf": "pdf",
    ".jpg": "img", ".jpeg": "img", ".png": "img",
    ".mp4": "vid", ".mov": "vid", ".m4v": "vid",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[build_manifest] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FileEntry:
    id: str
    title: str
    filename: str
    agency: str
    type: str
    source_url: str
    release_date: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    summary_en: Optional[str] = None
    # Translation fields (filled by humans via Claude Code session)
    title_he: Optional[str] = None
    agency_he: Optional[str] = None
    incident_location_he: Optional[str] = None
    summary_he: Optional[str] = None
    # Metadata
    size_bytes: Optional[int] = None
    url_status: Optional[int] = None  # HTTP status when validated


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def validate_url(url: str, timeout: int = 15) -> tuple[int, Optional[int]]:
    """Return (status_code, content_length). status -1 means network error."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.status
            length = r.headers.get("Content-Length")
            return status, int(length) if length else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        log(f"  url check failed: {url} → {e}")
        return -1, None


# ---------------------------------------------------------------------------
# Existing Hebrew preservation
# ---------------------------------------------------------------------------

def load_existing(path: Path) -> dict[str, dict[str, Optional[str]]]:
    """Map id → existing Hebrew translation fields so we don't lose them."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict[str, Optional[str]]] = {}
    for f in data.get("files", []):
        fid = f.get("id") or f.get("filename")
        if not fid:
            continue
        out[fid] = {
            "title_he": f.get("title_he"),
            "agency_he": f.get("agency_he"),
            "incident_location_he": f.get("incident_location_he"),
            "summary_he": f.get("summary_he"),
        }
    return out


# ---------------------------------------------------------------------------
# Playwright scraping
# ---------------------------------------------------------------------------

EXTRACT_JS = r"""
(() => {
    // Try multiple strategies to locate the file rows.
    // 1) explicit attributes the SPA may use
    // 2) generic table rows under the file list

    function pickText(el) {
        return (el && el.textContent ? el.textContent.trim() : '').replace(/\s+/g, ' ');
    }

    function bracketsStrip(s) {
        if (!s) return s;
        return s.replace(/^\[|\]$/g, '').trim();
    }

    // Strategy A: look for rows that contain a download link to /medialink/ufo/
    const links = Array.from(document.querySelectorAll('a[href*="/medialink/ufo/"]'));
    const seen = new Set();
    const rows = [];

    for (const a of links) {
        const href = a.href;
        if (!href || seen.has(href)) continue;
        // Skip bundle zips; we only want individual files.
        if (/bundle/i.test(href)) continue;
        seen.add(href);

        // Walk up to find the row container — go up until we hit something
        // that contains a recognizable agency token like FBI / DEPARTMENT.
        let row = a;
        for (let i = 0; i < 8 && row && row !== document.body; i++) {
            row = row.parentElement;
            if (!row) break;
            const t = pickText(row).toUpperCase();
            if (/(FBI|DEPARTMENT OF|NASA|ODNI|AARO)/.test(t)) break;
        }

        rows.push({
            href: href,
            rowText: pickText(row || a.parentElement || a),
            rowHTML: (row || a.parentElement || a).outerHTML.slice(0, 3000),
        });
    }

    // Strategy B (additional): collect any structured cell text within the
    // visible release section, indexed by URL.
    return {
        href_count: links.length,
        unique_urls: seen.size,
        rows: rows,
        pageTitle: document.title,
        totalFilesText: (document.body.innerText.match(/(\d+)\s*FILES/i) || [])[0] || null,
    };
})()
"""


DIAGNOSTIC_JS = r"""
(() => {
    const allLinks = Array.from(document.querySelectorAll('a[href]'));
    const hostCounts = {};
    const pathCounts = {};
    for (const a of allLinks) {
        try {
            const u = new URL(a.href);
            hostCounts[u.host] = (hostCounts[u.host] || 0) + 1;
            const seg = u.pathname.split('/').slice(0, 4).join('/');
            pathCounts[seg] = (pathCounts[seg] || 0) + 1;
        } catch (e) {}
    }
    const interesting = allLinks
        .filter(a => /\.(pdf|jpg|jpeg|png|mp4|mov|zip)$/i.test(a.href) || /medialink|file|download/i.test(a.href))
        .slice(0, 30)
        .map(a => ({href: a.href, text: (a.textContent || '').trim().slice(0, 80)}));

    const bodyText = (document.body.innerText || '').trim();
    return {
        url: location.href,
        title: document.title,
        bodyTextLength: bodyText.length,
        bodyTextSnippet: bodyText.slice(0, 800),
        totalLinks: allLinks.length,
        topHosts: Object.entries(hostCounts).sort((a,b)=>b[1]-a[1]).slice(0, 8),
        topPaths: Object.entries(pathCounts).sort((a,b)=>b[1]-a[1]).slice(0, 12),
        interestingLinks: interesting,
        scriptCount: document.scripts.length,
        // Look for evidence of the file table
        hasReleaseSection: !!document.querySelector('[id*="release" i], [class*="release" i]'),
        hasFileCount: !!(bodyText.match(/\d+\s*FILES/i)),
        fileCountText: (bodyText.match(/\d+\s*FILES/i) || [])[0] || null,
    };
})()
"""


def scrape_with_playwright(
    debug_html: bool = True,
    page_timeout_ms: int = 60000,
) -> list[FileEntry]:
    """Open war.gov/UFO in headless Chromium, scroll/paginate, scrape rows."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        log("playwright not installed — `pip install playwright && playwright install chromium`")
        return []

    entries: list[FileEntry] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        page = ctx.new_page()

        # Capture console + network errors for the log.
        console_messages: list[str] = []
        page.on("console", lambda m: console_messages.append(f"[{m.type}] {m.text[:200]}"))
        page.on("pageerror", lambda e: console_messages.append(f"[pageerror] {str(e)[:200]}"))
        failed_requests: list[str] = []
        page.on("requestfailed", lambda r: failed_requests.append(f"{r.method} {r.url} → {r.failure}"))

        # Snapshot every response so we can see if war.gov returned 403.
        responses: list[tuple[int, str]] = []
        page.on("response", lambda r: responses.append((r.status, r.url)))

        log(f"navigating to {UFO_PAGE_URL}")
        try:
            resp = page.goto(UFO_PAGE_URL, wait_until="domcontentloaded", timeout=page_timeout_ms)
            log(f"  initial response: status={resp.status if resp else '?'} url={resp.url if resp else '?'}")
        except Exception as e:
            log(f"goto failed: {e}")
            browser.close()
            return []

        # Wait longer for SPA hydration + lazy data load.
        try:
            page.wait_for_load_state("networkidle", timeout=45000)
        except Exception as e:
            log(f"networkidle wait timed out: {e} (continuing anyway)")

        # Heuristic wait: any anchor with a file-ish href OR a count like "158 FILES"
        try:
            page.wait_for_function(
                """() => {
                    const txt = document.body.innerText || '';
                    return /\\d+\\s*FILES/i.test(txt)
                        || document.querySelector('a[href*=".pdf"]')
                        || document.querySelector('a[href*="medialink"]');
                }""",
                timeout=25000,
            )
            log("  detected rendered file UI")
        except Exception:
            log("  WARN: file UI never appeared (timeout)")

        # Try various selectors but don't fail if none match — diagnostics will tell us why.
        matched_selector = None
        for selector in [
            'a[href*="/medialink/ufo/release_1/"]',
            'a[href*="medialink"]',
            '[class*="file" i] a[href*=".pdf"]',
            'a[href$=".pdf"]',
        ]:
            try:
                page.wait_for_selector(selector, timeout=5000)
                matched_selector = selector
                log(f"found rendered files via selector: {selector}")
                break
            except Exception:
                continue
        if not matched_selector:
            log("WARN: no file selector matched — page may not have rendered, or selectors changed")

        try_load_all_pages(page)

        # ---- diagnostics ALWAYS dumped ----
        diag = page.evaluate(DIAGNOSTIC_JS)
        log("==== DIAGNOSTICS ====")
        log(f"  final URL:        {diag['url']}")
        log(f"  page title:       {diag['title']!r}")
        log(f"  body text length: {diag['bodyTextLength']}")
        log(f"  total <a> links:  {diag['totalLinks']}")
        log(f"  script tags:      {diag['scriptCount']}")
        log(f"  has release sec:  {diag['hasReleaseSection']}")
        log(f"  file-count text:  {diag['fileCountText']!r}")
        log(f"  top hosts:        {diag['topHosts']}")
        log(f"  top paths:        {diag['topPaths']}")
        log(f"  first 800 chars of body text:")
        for line in diag['bodyTextSnippet'].splitlines()[:12]:
            log(f"    | {line}")
        log(f"  first 30 interesting links:")
        for L in diag['interestingLinks']:
            log(f"    - {L['href']}   text={L['text']!r}")
        # Response codes that came back during the page load
        status_counts: dict[int, int] = {}
        for s, _ in responses:
            status_counts[s] = status_counts.get(s, 0) + 1
        log(f"  HTTP response status counts: {status_counts}")
        non_2xx = [(s, u) for s, u in responses if s >= 400][:10]
        if non_2xx:
            log("  first 10 non-2xx responses:")
            for s, u in non_2xx:
                log(f"    {s}  {u}")
        if console_messages:
            log("  console messages (first 20):")
            for m in console_messages[:20]:
                log(f"    {m}")
        if failed_requests:
            log("  failed requests (first 10):")
            for r in failed_requests[:10]:
                log(f"    {r}")
        log("==== /DIAGNOSTICS ====")

        if debug_html:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "rendered.html").write_text(page.content(), encoding="utf-8")
            try:
                page.screenshot(path=str(DEBUG_DIR / "rendered.png"), full_page=True)
                log(f"  saved screenshot → {DEBUG_DIR / 'rendered.png'}")
            except Exception as e:
                log(f"  screenshot failed: {e}")
            (DEBUG_DIR / "diagnostics.json").write_text(
                json.dumps(diag, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            log(f"  saved diagnostics → {DEBUG_DIR / 'diagnostics.json'}")

        data = page.evaluate(EXTRACT_JS)
        log(f"extracted: href_count={data['href_count']}, unique_urls={data['unique_urls']}, "
            f"totalFilesText={data['totalFilesText']!r}")

        if debug_html:
            (DEBUG_DIR / "extracted.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        for row in data["rows"]:
            entry = row_to_entry(row)
            if entry:
                entries.append(entry)

        if entries:
            enrich_descriptions(page, entries, page_timeout_ms=page_timeout_ms)

        browser.close()

    return entries


def try_load_all_pages(page) -> None:
    """If the file browser paginates, click "NEXT" repeatedly until we've
    surfaced every row. Some SPAs render only the current page in the DOM."""
    last_count = -1
    for _ in range(40):  # cap to 40 iterations as a safety
        try:
            count = page.evaluate(
                'document.querySelectorAll(\'a[href*="/medialink/ufo/release_1/"]\').length'
            )
        except Exception:
            count = 0
        if count == last_count:
            break
        last_count = count
        next_btn = page.query_selector('button:has-text("NEXT"), a:has-text("NEXT")')
        if not next_btn or next_btn.is_disabled():
            break
        try:
            next_btn.click()
            page.wait_for_timeout(500)
        except Exception:
            break


def row_to_entry(row: dict[str, Any]) -> Optional[FileEntry]:
    href: str = row["href"]
    text: str = row.get("rowText", "")
    if not href.endswith(tuple(EXT_TYPE.keys())):
        return None

    filename = href.rsplit("/", 1)[-1]
    file_id = filename.rsplit(".", 1)[0]

    # Strip away the bracketed metadata cells from the row text.
    # Common pattern from the live site:
    #   "TITLE_TEXT  [AGENCY]  [RELEASE_DATE]  [INCIDENT_DATE]  [LOCATION]  [.PDF]"
    brackets = re.findall(r"\[([^\]]+)\]", text)
    title_text = re.sub(r"\s*\[[^\]]+\]\s*", " ", text).strip()

    # Heuristically pick agency / release / incident / location / type from brackets.
    agency = release_date = incident_date = incident_location = ext = None
    if brackets:
        # Last bracket is normally the file type (.pdf, .img, .vid).
        for b in reversed(brackets):
            if b.startswith(".") and len(b) <= 5:
                ext = b
                brackets.remove(b)
                break
        # First bracket is usually agency.
        if brackets:
            agency = brackets[0]
        # Find a date-like bracket for release_date (typical: M/D/YY).
        for b in brackets[1:]:
            if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", b) and release_date is None:
                release_date = b
                continue
            if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", b):
                incident_date = b
                continue
            # ISO-ish or "LATE 2025" / "2023"
            if re.match(r"^(LATE\s+\d{4}|EARLY\s+\d{4}|\d{4})$", b, re.I) and incident_date is None:
                incident_date = b
                continue
            # Else assume location
            if incident_location is None:
                incident_location = b

    type_ = (ext or filename.rsplit(".", 1)[-1]).lstrip(".").lower()
    type_ = EXT_TYPE.get("." + type_, type_)

    return FileEntry(
        id=file_id,
        title=title_text or filename,
        filename=filename,
        agency=(agency or "Unknown").strip().upper(),
        type=type_,
        source_url=href,
        release_date=release_date or RELEASE_DATE,
        incident_date=incident_date,
        incident_location=incident_location,
    )


def enrich_descriptions(page, entries: list[FileEntry], page_timeout_ms: int) -> None:
    """For each entry, navigate to its hash route on war.gov/UFO and
    scrape the description from the detail panel."""
    seen_descriptions: dict[str, str] = {}
    for i, e in enumerate(entries):
        # The SPA uses #<file_id> as the hash route for detail panels.
        hash_id = e.id
        try:
            page.evaluate(f'window.location.hash = {json.dumps(hash_id)}')
            page.wait_for_timeout(400)
            # Grab any sizable paragraph in the detail panel (heuristic).
            txt = page.evaluate(r"""
                () => {
                    const all = Array.from(document.querySelectorAll('p, .description, [class*="description"]'));
                    const long = all.map(n => (n.textContent || '').trim())
                        .filter(t => t.length > 80 && t.length < 4000);
                    return long.length ? long[0] : null;
                }
            """)
            if txt:
                e.summary_en = txt.strip()
                seen_descriptions[e.id] = e.summary_en
        except Exception as ex:
            log(f"  description fetch failed for {e.id}: {ex}")
        if (i + 1) % 25 == 0:
            log(f"  enriched {i + 1}/{len(entries)} descriptions")


# ---------------------------------------------------------------------------
# Manifest output
# ---------------------------------------------------------------------------

def merge_existing(entries: list[FileEntry], existing: dict[str, dict[str, Optional[str]]]) -> None:
    for e in entries:
        ex = existing.get(e.id) or existing.get(e.filename)
        if not ex:
            continue
        if ex.get("title_he"): e.title_he = ex["title_he"]
        if ex.get("agency_he"): e.agency_he = ex["agency_he"]
        if ex.get("incident_location_he"): e.incident_location_he = ex["incident_location_he"]
        if ex.get("summary_he"): e.summary_he = ex["summary_he"]


def validate_all(entries: list[FileEntry]) -> None:
    log(f"validating {len(entries)} download URLs")
    for i, e in enumerate(entries):
        status, length = validate_url(e.source_url)
        e.url_status = status
        if length is not None and e.size_bytes is None:
            e.size_bytes = length
        if status != 200:
            log(f"  ⚠ {e.source_url} → {status}")
        if (i + 1) % 25 == 0:
            log(f"  validated {i + 1}/{len(entries)}")


def write_manifest(entries: list[FileEntry], path: Path) -> None:
    payload = {
        "release_id": RELEASE_ID,
        "release_date": RELEASE_DATE,
        "source_page_url": UFO_PAGE_URL,
        "total_files": len(entries),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": [asdict(e) for e in entries],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"wrote {path} ({len(entries)} files, {path.stat().st_size} bytes)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-validate", action="store_true",
                        help="skip the HEAD validation step (faster, less safe)")
    parser.add_argument("--no-debug-dump", action="store_true",
                        help="don't write data/_debug/{rendered.html, extracted.json}")
    args = parser.parse_args()

    existing = load_existing(MANIFEST_PATH)
    log(f"existing manifest had {len(existing)} entries with Hebrew translations")

    entries = scrape_with_playwright(debug_html=not args.no_debug_dump)

    if not entries:
        log("scraper returned 0 entries — keeping existing manifest unchanged")
        return 0  # don't fail the CI run; site keeps the old data

    merge_existing(entries, existing)

    if not args.no_validate:
        validate_all(entries)

    write_manifest(entries, MANIFEST_PATH)

    # Stats
    agencies: dict[str, int] = {}
    bad_urls = 0
    with_desc = 0
    with_he = 0
    for e in entries:
        agencies[e.agency] = agencies.get(e.agency, 0) + 1
        if e.url_status not in (200, None): bad_urls += 1
        if e.summary_en: with_desc += 1
        if e.summary_he: with_he += 1
    log(f"agencies:     {agencies}")
    log(f"bad URLs:     {bad_urls}/{len(entries)}")
    log(f"descriptions: {with_desc}/{len(entries)}")
    log(f"hebrew:       {with_he}/{len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
