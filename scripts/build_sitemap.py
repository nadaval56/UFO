#!/usr/bin/env python3
"""Build sitemap.xml from data/manifest.json.

The sitemap lists the landing page plus every file detail page
(file.html?id=...) so search engines can crawl the entire archive.
Run after manifest changes; output committed to repo root.
"""
import json
from pathlib import Path
from urllib.parse import quote
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
SITEMAP = ROOT / "sitemap.xml"
BASE = "https://nadaval56.github.io/UFO"
TODAY = date.today().isoformat()

m = json.loads(MANIFEST.read_text(encoding="utf-8"))
files = m.get("files", [])

entries = [
    (f"{BASE}/", "1.0", "weekly"),
    (f"{BASE}/index.html", "1.0", "weekly"),
]
for f in files:
    fid = f.get("id")
    if not fid:
        continue
    url = f"{BASE}/file.html?id={quote(fid, safe='-_')}"
    entries.append((url, "0.7", "monthly"))

lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for url, priority, freq in entries:
    lines.append("  <url>")
    lines.append(f"    <loc>{url}</loc>")
    lines.append(f"    <lastmod>{TODAY}</lastmod>")
    lines.append(f"    <changefreq>{freq}</changefreq>")
    lines.append(f"    <priority>{priority}</priority>")
    lines.append("  </url>")
lines.append("</urlset>")

SITEMAP.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {SITEMAP} with {len(entries)} URLs")
