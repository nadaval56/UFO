#!/usr/bin/env python3
"""Build the static pages, sitemap.xml and archive.html from data/manifest.json.

Three static artifacts, all regenerated after any manifest change and
committed:

  doc/*.html    one pre-rendered page per document (build_static_pages.py).
  sitemap.xml   the landing page plus every document page.
  archive.html  a plain, JS-free index of every document, each a real link.

archive.html exists because the browser on index.html is built entirely in
JavaScript: with scripts off there are no file cards and no links at all, so
a crawler that does not execute JS sees none of the 375 documents. This page
is the crawlable spine — and it works for readers with JS off too.
"""
import json
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_static_pages import build as build_static_pages, doc_path  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
SITEMAP = ROOT / "sitemap.xml"
ARCHIVE = ROOT / "archive.html"
BASE = "https://pursue.co.il"
TODAY = date.today().isoformat()

build_static_pages()
m = json.loads(MANIFEST.read_text(encoding="utf-8"))
files = m.get("files", [])

def iso_release(d):
    """release_date is Israeli D/M/YY ('18/9/26') -> '2026-09-18'."""
    try:
        day, mon, yr = (int(x) for x in str(d).split("/"))
        return f"{2000 + yr if yr < 100 else yr:04d}-{mon:02d}-{day:02d}"
    except (TypeError, ValueError):
        return None


# lastmod must mean something: a document changes when its release lands,
# and the index pages when the newest release does. Stamping every URL with
# today's date on each rebuild teaches Google to ignore lastmod altogether.
latest = max((iso_release(f.get("release_date")) or "" for f in files), default="") or TODAY
entries = [
    (f"{BASE}/", "1.0", "weekly", latest),
    (f"{BASE}/archive.html", "0.9", "weekly", latest),
]
for f in files:
    fid = f.get("id")
    if not fid:
        continue
    url = f"{BASE}/{doc_path(fid)}"
    entries.append((url, "0.7", "monthly", iso_release(f.get("release_date")) or latest))

lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for url, priority, freq, lastmod in entries:
    lines.append("  <url>")
    lines.append(f"    <loc>{url}</loc>")
    lines.append(f"    <lastmod>{lastmod}</lastmod>")
    lines.append(f"    <changefreq>{freq}</changefreq>")
    lines.append(f"    <priority>{priority}</priority>")
    lines.append("  </url>")
lines.append("</urlset>")

SITEMAP.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {SITEMAP} with {len(entries)} URLs")


# --------------------------------------------------------------------------
# archive.html — static, no JavaScript, one real link per document
# --------------------------------------------------------------------------

def esc(v):
    return (str(v or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


by_release = {}
for f in files:
    by_release.setdefault(f.get("release") or "unknown", []).append(f)

rows = []
for rel in sorted(by_release, reverse=True):
    group = by_release[rel]
    no = rel.replace("release_", "") if rel.startswith("release_") else rel
    date_il = group[0].get("release_date") or ""
    rows.append(f'  <h2 id="{esc(rel)}">מהדורה {esc(no)}'
                + (f' <span class="a-date">{esc(date_il)}</span>' if date_il else "")
                + f' <span class="a-count">{len(group)} קבצים</span></h2>')
    rows.append("  <ul>")
    for f in sorted(group, key=lambda x: (x.get("title") or "")):
        fid = f.get("id")
        if not fid:
            continue
        title = f.get("title_he") or f.get("title") or f.get("filename") or fid
        agency = f.get("agency_he") or f.get("agency") or ""
        href = doc_path(fid)
        rows.append(f'    <li><a href="{esc(href)}">{esc(title)}</a>'
                    + (f' <span class="a-agency">{esc(agency)}</span>' if agency else "")
                    + "</li>")
    rows.append("  </ul>")

archive = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>אינדקס מלא — כל {len(files)} המסמכים — עב"מים</title>
<meta name="description" content="אינדקס מלא של כל {len(files)} המסמכים בארכיון ה-UAP, מסודר לפי מהדורה. ללא JavaScript.">
<link rel="canonical" href="{BASE}/archive.html">
<meta property="og:type" content="website">
<meta property="og:title" content="אינדקס מלא — כל {len(files)} המסמכים">
<meta property="og:url" content="{BASE}/archive.html">
<meta property="og:locale" content="he_IL">
<link rel="stylesheet" href="assets/css/styles.css">
<style>
  .a-wrap {{ max-width: 900px; margin: 0 auto; padding: 32px 20px 64px; }}
  .a-wrap h1 {{ font-size: 1.6rem; margin-bottom: 6px; }}
  .a-lead {{ color: var(--text-muted); font-family: var(--font-sans); margin: 0 0 28px; }}
  .a-wrap h2 {{ font-size: 1rem; font-family: var(--font-mono); color: var(--accent);
               margin: 32px 0 10px; padding-block-end: 6px;
               border-block-end: 1px solid var(--border); }}
  .a-date, .a-count {{ color: var(--text-dim); font-size: 0.75rem; font-weight: 400; }}
  .a-wrap ul {{ list-style: none; padding: 0; margin: 0; }}
  .a-wrap li {{ padding: 6px 0; border-block-end: 1px solid var(--border);
               font-family: var(--font-sans); font-size: 0.92rem;
               /* Titles carry long unbroken document codes; without this they
                  push the page wider than the viewport on a phone. */
               overflow-wrap: anywhere; word-break: break-word; }}
  .a-wrap {{ overflow-x: hidden; }}
  .a-wrap h2 {{ overflow-wrap: anywhere; }}
  .a-agency {{ color: var(--text-dim); font-size: 0.76rem; margin-inline-start: 8px; }}
</style>
</head>
<body>
<div class="a-wrap">
  <h1>אינדקס מלא של הארכיון</h1>
  <p class="a-lead">כל {len(files)} המסמכים, מסודרים לפי מהדורה. עמוד סטטי ללא JavaScript —
  <a href="index.html">לדפדפן עם חיפוש וסינון</a>.</p>
{chr(10).join(rows)}
  <p class="a-lead" style="margin-top:40px">
    תרגום קהילתי בלתי רשמי. למקור:
    <a href="https://www.war.gov/UFO/" rel="noopener">war.gov/UFO</a>.
  </p>
</div>
</body>
</html>
"""
ARCHIVE.write_text(archive, encoding="utf-8")
print(f"Wrote {ARCHIVE} with {len(files)} document links")
